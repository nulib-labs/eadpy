import hashlib
import os
import re
import io
import warnings
from lxml import etree
import csv

from eadpy.exceptions import EadParseError

class EAD:
    NAME_ELEMENTS = ["corpname", "famname", "name", "persname"]

    SEARCHABLE_NOTES_FIELDS = [
        "accessrestrict", "accruals", "altformavail", "appraisal", "arrangement",
        "bibliography", "bioghist", "custodhist", "fileplan", "note", "odd",
        "originalsloc", "otherfindaid", "phystech", "prefercite", "processinfo",
        "relatedmaterial", "scopecontent", "separatedmaterial", "userestrict"
    ]

    DID_SEARCHABLE_NOTES_FIELDS = [
        "abstract", "materialspec", "physloc", "note"
    ]

    def __init__(self, ead_source):
        """
        Initializes the EAD object by parsing the EAD source.

        Best practice is to use the class methods `from_path`, `from_string`,
        `from_bytes`, or `from_file` to create instances.

        Parameters
        ----------
        ead_source : str or file-like object
            A file path (string) or a file-like object containing the EAD XML.
            lxml.etree.parse can handle both.
        """
        self.ead_source_repr = repr(ead_source) # For error messages
        self.counter = 0
        self.data = self._parse(ead_source) # Call the parsing logic

    @classmethod
    def from_path(cls, file_path: str):
        """
        Creates an EAD instance from a file path.
        
        Parameters
        ----------
        file_path : str
            Path to the EAD XML file
            
        Returns
        -------
        EAD
            An instance of the EAD class
            
        Raises
        ------
        TypeError
            If file_path is not a string
        FileNotFoundError
            If the file does not exist
        IsADirectoryError
            If the path points to a directory instead of a file
        PermissionError
            If the file cannot be read due to permissions
        """
        if not isinstance(file_path, str):
            raise TypeError("file_path must be a string.")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"EAD file not found: '{file_path}'.")
        if not os.path.isfile(file_path):
            raise IsADirectoryError(f"'{file_path}' is a directory, not a file.")
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"Permission denied: Unable to read '{file_path}'.")
        # Pass the path directly, etree.parse can handle it
        return cls(file_path)

    @classmethod
    def from_string(cls, xml_string: str, encoding: str = 'utf-8'):
        """
        Creates an EAD instance from an XML string.

        Parameters
        ----------
        xml_string : str
            String containing EAD XML content
        encoding : str, optional
            Deprecated and ignored. A Python str carries no byte encoding,
            so the string is always encoded to UTF-8 for parsing.

        Returns
        -------
        EAD
            An instance of the EAD class

        Raises
        ------
        TypeError
            If xml_string is not a string
        ValueError
            If the string cannot be encoded or parsed
        """
        if not isinstance(xml_string, str):
            raise TypeError("xml_string must be a string.")
        # The string is already decoded, so an XML declaration naming some
        # other encoding no longer applies — left in place it would make the
        # parser mis-decode the UTF-8 bytes produced below.
        xml_string = re.sub(r'^\s*<\?xml[^>]*\?>', '', xml_string, count=1)
        try:
            xml_bytes = xml_string.encode('utf-8')
        except Exception as e:
            raise ValueError(f"Error encoding string: {e}")
        return cls(io.BytesIO(xml_bytes))

    @classmethod
    def from_bytes(cls, xml_bytes: bytes):
        """
        Creates an EAD instance from XML bytes.
        
        Parameters
        ----------
        xml_bytes : bytes
            Bytes containing EAD XML content
            
        Returns
        -------
        EAD
            An instance of the EAD class
            
        Raises
        ------
        TypeError
            If xml_bytes is not bytes
        """
        if not isinstance(xml_bytes, bytes):
            raise TypeError("xml_bytes must be bytes.")
        bytes_io = io.BytesIO(xml_bytes)
        return cls(bytes_io) # Pass the file-like object

    @classmethod
    def from_file(cls, file_like_object):
        """
        Creates an EAD instance from an open file-like object.
        
        Parameters
        ----------
        file_like_object : file object
            A file-like object with a 'read' method containing EAD XML content
            
        Returns
        -------
        EAD
            An instance of the EAD class
            
        Raises
        ------
        TypeError
            If the input is not a file-like object with a 'read' method
        """
        if not hasattr(file_like_object, 'read'):
            raise TypeError("Input must be a file-like object with a 'read' method.")
        
        # Check if it's a text-based file object (StringIO)
        if hasattr(file_like_object, 'encoding') or isinstance(file_like_object, io.StringIO):
            # Convert to bytes to avoid encoding declaration issues with StringIO
            content = file_like_object.read()
            # Use from_string which handles the Unicode to bytes conversion
            return cls.from_string(content)
        
        # It's already a binary file-like object (BytesIO or file opened in binary mode)
        return cls(file_like_object) # Pass the file-like object

    def _parse(self, ead_source):
        """
        Internal method to parse the EAD XML source using lxml.
        """
        try:
            # Use a parser that removes blank text for cleaner processing.
            # resolve_entities=False leaves declared entity references (often
            # external boilerplate like <!ENTITY x SYSTEM "x.txt">) unexpanded
            # instead of failing, matching ArchivesSpace's importer behavior
            # and avoiding external file reads (XXE). Undeclared entities are
            # still a hard parse error with recover=False.
            parser = etree.XMLParser(
                remove_blank_text=True, recover=False, resolve_entities=False
            )

            # etree.parse handles both file paths (strings) and file-like objects
            tree = etree.parse(ead_source, parser)

            self._strip_unresolved_entities(tree)

            # Remove namespaces (essential for consistent XPath)
            self._remove_namespaces(tree)
            root = tree.getroot()
            self._check_ead_version(root)

            # Parse the top-level collection
            collection = self._parse_collection(root)

            # Identify all top-level components (c, c01..c12). EAD 2002 allows
            # <dsc> groups nested inside <dsc>, so match components under any
            # dsc; their own nested components are handled recursively.
            component_nodes = root.xpath(
                "/ead/archdesc//dsc/c | "
                + " | ".join(f"/ead/archdesc//dsc/c{i:02d}" for i in range(1, 13))
            )

            # Parse child components under the main collection
            collection["components"] = self._parse_components(component_nodes, collection["id"])

            return collection

        except etree.XMLSyntaxError as e:
            raise EadParseError(
                f"Invalid XML detected in {self.ead_source_repr}: {str(e)}"
            )
        except ValueError:
            raise # Version/root checks above raise EadParseError with a clear message
        # Catch specific expected errors from from_path if they weren't caught there
        # (though they should be). Catching IOErrors is also good here.
        except FileNotFoundError:
            raise # Re-raise specific errors if needed
        except PermissionError:
            raise # Re-raise
        except IOError as e:
            raise IOError(f"Error reading from {self.ead_source_repr}: {e}")
        except Exception as e:
            # Catch-all for other unexpected parsing issues
            raise RuntimeError(
                f"Unexpected error parsing EAD input {self.ead_source_repr}: {str(e)}"
            )

    def create_item_chunks(self):
        """
        Create item-focused chunks that include relevant information
        from their parent hierarchy.
        
        Returns
        -------
        list
            A list of chunks ready for embedding.
        """
        chunks = []

        def process_items(component, ancestors=None):
            if ancestors is None:
                ancestors = []

            current_component = {
                "id": component.get("id", ""),
                "title": component.get("title", ""),
                "level": component.get("level", ""),
                "date": component.get("normalized_date", ""),
                "extent": component.get("extent", [])
            }

            current_ancestors = ancestors + [current_component]
            is_leaf = "components" not in component or not component["components"]
            is_item = component.get("level") == "item"

            if is_leaf or is_item:
                hierarchy_titles = [a.get("title") or "" for a in current_ancestors]
                hierarchy_path = " > ".join(hierarchy_titles)

                ancestor_dates = []
                ancestor_extents = []

                for ancestor in current_ancestors[:-1]:
                    if ancestor["date"] and ancestor["date"] not in ancestor_dates:
                        ancestor_dates.append(ancestor["date"])
                    for extent in ancestor["extent"]:
                        if extent and extent not in ancestor_extents:
                            ancestor_extents.append(extent)

                chunk_data = {
                    "id": current_component["id"],
                    "title": current_component["title"],
                    "path": hierarchy_path,
                    "level": current_component["level"],
                    "date": current_component["date"],
                    "ancestor_dates": ancestor_dates,
                    "ancestor_extents": ancestor_extents,
                    "content": []
                }

                if component.get("notes"):
                    for note_type, notes in component["notes"].items():
                        if isinstance(notes, list):
                            for note in notes:
                                if isinstance(note, dict) and "content" in note:
                                    chunk_data["content"].append({
                                        "type": note_type,
                                        "text": " ".join(note["content"])
                                    })
                                else:
                                    chunk_data["content"].append({
                                        "type": note_type,
                                        "text": str(note)
                                    })

                if current_component["extent"]:
                    chunk_data["content"].append({
                        "type": "extent",
                        "text": ", ".join(current_component["extent"])
                    })

                if component.get("access_subjects"):
                    chunk_data["content"].append({
                        "type": "subjects",
                        "text": ", ".join(component["access_subjects"])
                    })

                if component.get("digital_objects"):
                    digital_texts = []
                    for obj in component["digital_objects"]:
                        if obj.get("label"):
                            digital_texts.append(f"{obj['label']}: {obj.get('href', '')}")
                        else:
                            digital_texts.append(obj.get('href', ''))
                    if digital_texts:
                        chunk_data["content"].append({
                            "type": "digital_objects",
                            "text": "; ".join(digital_texts)
                        })

                if component.get("creators"):
                    creator_texts = []
                    for creator in component["creators"]:
                        if creator.get("name"):
                            creator_texts.append(f"{creator['name']} ({creator.get('type', '')})")
                    if creator_texts:
                        chunk_data["content"].append({
                            "type": "creators",
                            "text": "; ".join(creator_texts)
                        })

                text_parts = [f"Path: {chunk_data['path']}"]
                text_parts.append(f"Title: {chunk_data['title']}")

                if chunk_data["date"]:
                    text_parts.append(f"Date: {chunk_data['date']}")

                if ancestor_dates:
                    text_parts.append(f"Collection Dates: {', '.join(ancestor_dates)}")

                if ancestor_extents:
                    text_parts.append(f"Collection Extent: {', '.join(ancestor_extents)}")

                for content in chunk_data["content"]:
                    text_parts.append(f"{content['type'].capitalize()}: {content['text']}")

                chunks.append({
                    "text": "\n".join(text_parts),
                    "metadata": {
                        "id": chunk_data["id"],
                        "title": chunk_data["title"],
                        "level": chunk_data["level"],
                        "path": hierarchy_path,
                        "date": chunk_data["date"],
                        "ancestors": [a["id"] for a in current_ancestors[:-1]],
                        "ancestor_titles": hierarchy_titles[:-1]
                    }
                })

            if "components" in component:
                for child in component["components"]:
                    process_items(child, current_ancestors)

        process_items(self.data)
        return chunks

    def save_chunks_to_json(self, chunks, output_file):
        """
        Save chunks to a JSON file.

        Parameters
        ----------
        chunks : list
            List of chunks to save
        output_file : str
            Path to the output JSON file
        """
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

    def create_and_save_chunks(self, output_file):
        """
        Create item-focused chunks and save them to a JSON file.

        Parameters
        ----------
        output_file : str
            Path to the output JSON file

        Returns
        -------
        list
            The chunks that were created and saved
        """
        chunks = self.create_item_chunks()
        self.save_chunks_to_json(chunks, output_file)
        return chunks

    def create_csv_data(self):
        """
        Create flattened data suitable for CSV export.
        Returns a list of dictionaries, each representing a row in the CSV.
        """
        csv_data = []

        def process_component(component, ancestors=None, depth=0):
            if ancestors is None:
                ancestors = []

            row = {
                "id": component.get("id", ""),
                "ref_id": component.get("ref_id", ""),
                "parent_id": component.get("parent_id", ""),
                "level": component.get("level", ""),
                "depth": depth,
                "title": component.get("title", ""),
                "normalized_title": component.get("normalized_title", ""),
                "date": component.get("normalized_date", ""),
                "unitid": component.get("unitid", ""),
                "has_online_content": "Yes" if component.get("has_online_content") else "No",
                "path": " > ".join([(a.get("title") or "") for a in ancestors]
                                   + [(component.get("title") or "")])
            }

            if component.get("extent"):
                row["extent"] = ", ".join([(item or "") for item in component["extent"]])
            else:
                row["extent"] = ""

            if component.get("creators"):
                creators = []
                for creator in component["creators"]:
                    if creator.get("name"):
                        creators.append(f"{creator['name']} ({creator.get('type', '')})")
                row["creators"] = "; ".join(creators)
            else:
                row["creators"] = ""

            if component.get("containers"):
                containers = []
                for container in component["containers"]:
                    if container.get("type") and container.get("value"):
                        containers.append(f"{container['type']}: {container['value']}")
                row["containers"] = "; ".join(containers)
            else:
                row["containers"] = ""

            if component.get("notes"):
                notes_text = []
                for note_type, notes in component["notes"].items():
                    if isinstance(notes, list):
                        for note in notes:
                            if isinstance(note, dict) and "content" in note:
                                content_items = [(item or "") for item in note["content"]]
                                notes_text.append(f"{note_type.upper()}: {' '.join(content_items)}")
                            else:
                                notes_text.append(f"{note_type.upper()}: {str(note or '')}")
                row["notes"] = " | ".join(notes_text)
            else:
                row["notes"] = ""

            if component.get("access_subjects"):
                row["subjects"] = ", ".join([(item or "") for item in component["access_subjects"]])
            else:
                row["subjects"] = ""

            csv_data.append(row)

            current_ancestors = ancestors + [component]
            if "components" in component:
                for child in component["components"]:
                    process_component(child, current_ancestors, depth + 1)

        process_component(self.data)
        return csv_data

    def save_csv_data(self, csv_data, output_file):
        """
        Save CSV data to a file.

        Parameters
        ----------
        csv_data : list
            List of dictionaries representing CSV rows
        output_file : str
            Path to the output CSV file
        """
        if not csv_data:
            raise ValueError("No CSV data to save")

        fieldnames = list(csv_data[0].keys())

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)

    def create_and_save_csv(self, output_file):
        """
        Create flattened CSV data and save it to a file.

        Parameters
        ----------
        output_file : str
            Path to the output CSV file

        Returns
        -------
        list
            The CSV data that was created and saved
        """
        csv_data = self.create_csv_data()
        self.save_csv_data(csv_data, output_file)
        return csv_data

    def _strip_unresolved_entities(self, tree):
        """
        Remove entity references left unexpanded by resolve_entities=False,
        so the literal '&name;' text doesn't leak into extracted text. Their
        content (typically institutional boilerplate pulled in via external
        entities) is omitted from output; a warning reports what was dropped.
        """
        names = set()
        for node in list(tree.getroot().iter(etree.Entity)):
            names.add(node.name)
            parent = node.getparent()
            tail = node.tail or ""
            prev = node.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + tail
            else:
                parent.text = (parent.text or "") + tail
            parent.remove(node)
        if names:
            warnings.warn(
                f"Unresolved entity reference(s) in {self.ead_source_repr}: "
                f"{', '.join(sorted(names))}. eadpy does not load external "
                "entities; their text is omitted from parsed output.",
                UserWarning,
                stacklevel=2,
            )

    def _remove_namespaces(self, tree):
        """
        Remove namespaces in-place from an lxml ElementTree.
        """
        for elem in tree.getiterator():
            if elem.tag and isinstance(elem.tag, str) and elem.tag.startswith("{"):
                elem.tag = elem.tag.split("}", 1)[1]
        etree.cleanup_namespaces(tree)

    def _check_ead_version(self, root):
        """
        Verify the document is EAD 2002. EAD3 shares the <ead> root element
        but replaces <eadheader> with <control>, and would otherwise parse
        'successfully' into an empty collection.
        """
        if root.tag != "ead":
            raise EadParseError(
                f"Unexpected root element <{root.tag}>; expected <ead> (EAD 2002)."
            )
        if root.find("control") is not None and root.find("eadheader") is None:
            raise EadParseError(
                "This appears to be an EAD3 document (<control> instead of "
                "<eadheader>); eadpy supports EAD 2002 only."
            )

    def _generate_id(self, reference_id, parent_id=None):
        """
        Generate an identifier if reference_id is None,
        otherwise prepend parent_id if present.
        """
        if reference_id:
            return f"{parent_id}_{reference_id}" if parent_id else reference_id
        else:
            # Deterministic per-parse fallback: hash a counter scoped to this
            # instance so repeat parses of the same document yield stable ids.
            self.counter += 1
            md5_hash = hashlib.md5(
                f"{parent_id}_{self.counter}".encode("utf-8")
            ).hexdigest()[:9]
            return f"{parent_id}_{md5_hash}" if parent_id else md5_hash

    def _parse_collection(self, root):
        """
        Parse the top-level <archdesc> as a 'collection'.
        """
        ead_id_node = root.xpath("//eadheader/eadid")
        ead_id = (ead_id_node[0].text or "").strip() or None if ead_id_node else None

        title = self._parse_title(root)
        dates = self._parse_dates(root, "//archdesc/did/")
        normalized_date = self._format_normalized_date(dates)
        repository_nodes = root.xpath("//repository")

        collection = {
            "id": ead_id,
            "level": "collection",
            "title": title,
            "normalized_title": self._normalize_title(title, normalized_date),
            "dates": dates,
            "normalized_date": normalized_date,
            "creators": self._parse_creators(root, "//archdesc/did/"),
            "extent": self._parse_extent(root, "//archdesc/did/"),
            "language": self._parse_language(root),
            "physdesc": self._parse_physdesc(root),
            "repository": self._joined_text(repository_nodes[0]) if repository_nodes else None,
            "unitid": self._first_text(root.xpath("//archdesc/did/unitid")),
            "notes": self._parse_notes(root, "//archdesc/"),
            "access_subjects": self._parse_access_subjects(root, "//archdesc/"),
            "geo_names": self._texts(root.xpath("//archdesc/controlaccess/geogname")),
            "digital_objects": self._parse_digital_objects(
                root.xpath("//archdesc/did/dao | //archdesc/dao")
            ),
            # Deliberately document-wide: a <dao> anywhere, including inside
            # components, means the collection has online content.
            "has_online_content": len(root.xpath("//dao")) > 0
        }
        return collection

    def _parse_language(self, root):
        """
        Languages of the material. Standard EAD 2002 wraps each language in a
        <language> child of <langmaterial>; fall back to the langmaterial
        prose when no <language> children exist.
        """
        language_nodes = root.xpath("//archdesc/did/langmaterial//language")
        if language_nodes:
            return self._texts(language_nodes)
        return self._texts(root.xpath("//archdesc/did/langmaterial"))

    def _parse_components(self, component_nodes, parent_id):
        """
        Recursively parse all <cXX> child components.
        """
        components = []
        for node in component_nodes:
            ref_id = node.get("id")
            if not ref_id:
                self.counter += 1
                fallback = f"{parent_id}_{self.counter}"
                ref_id = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:9]

            component_id = self._generate_id(ref_id, parent_id)
            title = self._first_text(node.xpath("./did/unittitle"))
            dates = self._parse_dates(node, "./did/")
            normalized_date = self._format_normalized_date(dates)

            component = {
                "id": component_id,
                "ref_id": ref_id,
                "parent_id": parent_id,
                "level": self._parse_level(node),
                "title": title,
                "normalized_title": self._normalize_title(title, normalized_date),
                "dates": dates,
                "normalized_date": normalized_date,
                "unitid": self._first_text(node.xpath("./did/unitid")),
                "creators": self._parse_creators(node, "./did/"),
                "extent": self._parse_extent(node, "./did/"),
                "notes": self._parse_notes(node, "./"),
                "containers": self._parse_containers(node),
                "access_subjects": self._parse_access_subjects(node, "./"),
                "digital_objects": self._parse_digital_objects(
                    node.xpath("./dao | ./did/dao")
                ),
                # Descendant daos deliberately count, so ancestors of
                # digitized material are also flagged as online content.
                "has_online_content": len(node.xpath(".//dao")) > 0,
            }

            # Recursively parse children
            child_selector = "./c" + "".join(f"|./c{i:02d}" for i in range(1, 13))
            child_nodes = node.xpath(child_selector)
            if child_nodes:
                component["components"] = self._parse_components(child_nodes, component_id)

            components.append(component)
        return components

    def _normalize_title(self, title, date_str):
        """
        If both title and date_str exist, combine them.
        """
        if not title or not date_str:
            return title
        return f"{title}, {date_str}"

    def _parse_title(self, root):
        """
        Extract the collection-level title (unittitle).
        """
        return self._first_text(root.xpath("//archdesc/did/unittitle"))

    def _parse_dates(self, node, prefix):
        """
        Return a dict of unitdate display values grouped by type, plus any
        machine-readable @normal attribute values.
        """
        return {
            "inclusive": self._texts(node.xpath(f'{prefix}unitdate[@type="inclusive"]')),
            "bulk": self._texts(node.xpath(f'{prefix}unitdate[@type="bulk"]')),
            "other": self._texts(node.xpath(f'{prefix}unitdate[not(@type)]')),
            "normal": [str(v) for v in node.xpath(f'{prefix}unitdate/@normal')]
        }

    def _format_normalized_date(self, dates):
        """
        Concatenate inclusive, bulk, and other dates into a single display string.
        """
        normalized = list(dates["inclusive"])
        if dates["bulk"]:
            normalized.append(f"bulk {', '.join(dates['bulk'])}")
        normalized.extend(dates["other"])
        return ", ".join(normalized) if normalized else None

    def _parse_extent(self, node, prefix):
        """
        Collect <extent> under a <physdesc>.
        """
        return self._texts(node.xpath(f'{prefix}physdesc/extent'))

    def _parse_physdesc(self, root):
        """
        Extract textual content from <physdesc> for the collection-level.
        """
        entries = []
        for pnode in root.xpath('//archdesc/did/physdesc'):
            joined_text = self._joined_text(pnode)
            if joined_text:
                entries.append(joined_text)
        return entries

    def _parse_creators(self, node, prefix):
        """
        Collect <origination> name elements.
        """
        creators = []
        for name_el in self.NAME_ELEMENTS:
            for el in node.xpath(f"{prefix}origination/{name_el}"):
                name = self._collapse_text(el)
                if name:
                    creators.append({"type": name_el, "name": name})
        return creators

    def _parse_level(self, node):
        """
        Return the component's level, falling back to 'otherlevel' if appropriate.
        """
        level = node.get("level")
        other_level = node.get("otherlevel")
        if level == "otherlevel" and other_level:
            return other_level
        return level

    def _parse_containers(self, node):
        """
        Collect all <container> info for a given component.
        """
        containers = []
        container_nodes = node.xpath('./did/container')
        for c in container_nodes:
            containers.append({
                "type": c.get("type"),
                "value": self._collapse_text(c)
            })
        return containers

    def _parse_notes(self, node, prefix):
        """
        Parse note fields. Some are direct children of <archdesc>/<cXX>,
        some live under the <did>.
        """
        notes = {}
        for field in self.SEARCHABLE_NOTES_FIELDS:
            content_nodes = node.xpath(f"{prefix}{field}")
            if content_nodes:
                field_values = []
                for cnode in content_nodes:
                    head_nodes = cnode.xpath('./head')
                    heading = (self._collapse_text(head_nodes[0]) or "") if head_nodes else ""
                    field_values.append({
                        "heading": heading,
                        "content": self._note_content(cnode)
                    })
                notes[field] = field_values

        for field in self.DID_SEARCHABLE_NOTES_FIELDS:
            values = self._texts(node.xpath(f"{prefix}did/{field}"))
            if values:
                notes[field] = values
        return notes

    def _note_content(self, node):
        """
        Text blocks of a note element: direct text plus one entry per child
        element (excluding <head>), so block structure survives as separate
        list entries.
        """
        texts = []

        def add_raw(raw):
            if raw and raw.strip():
                texts.append(re.sub(r"\s+", " ", raw).strip())

        add_raw(node.text)
        for child in node:
            if child.tag != "head":
                block = self._block_text(child)
                if block:
                    texts.append(block)
            add_raw(child.tail)
        return texts

    def _block_text(self, node):
        """
        Text of a block element inside a note. Prose blocks keep their inline
        spacing; element-only blocks (chronlist, list, table, ...) get their
        pieces space-separated so adjacent values don't run together.
        """
        has_own_text = bool(node.text and node.text.strip()) or any(
            child.tail and child.tail.strip() for child in node
        )
        if len(node) == 0 or has_own_text:
            return self._collapse_text(node)
        return self._joined_text(node)

    def _parse_access_subjects(self, node, prefix):
        """
        Collect subject, function, occupation, genreform under <controlaccess>.
        """
        subjects = []
        for canode in node.xpath(f"{prefix}controlaccess"):
            for selector in ["subject", "function", "occupation", "genreform"]:
                subjects.extend(self._texts(canode.xpath(f".//{selector}")))
        return subjects

    def _parse_digital_objects(self, dao_nodes):
        """
        Collect digital object references from <dao> or <did/dao>.
        """
        digital_objects = []
        for dao in dao_nodes:
            label = dao.get("title")
            if not label:
                label = self._first_text(dao.xpath("./daodesc/p"))

            href = dao.get("href")
            if not href:
                href = dao.get("{http://www.w3.org/1999/xlink}href")

            if href:
                digital_objects.append({"label": label, "href": href})

        return digital_objects

    def _collapse_text(self, node):
        """
        Full text of an element with whitespace runs collapsed. Suitable for
        prose and mixed content, where inline markup (persname, title, emph,
        ...) interrupts the text but natural spacing surrounds it.
        """
        if node is None:
            return None
        text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
        return text or None

    def _joined_text(self, node):
        """
        Text of an element joined piece-by-piece with spaces. Suitable for
        element-only content (e.g. physdesc, repository) whose children are
        discrete values that would otherwise run together.
        """
        if node is None:
            return None
        parts = [p.strip() for p in node.itertext() if p.strip()]
        return " ".join(parts) or None

    def _first_text(self, nodes):
        """
        Collapsed text of the first element in an XPath result, else None.
        """
        return self._collapse_text(nodes[0]) if nodes else None

    def _texts(self, nodes):
        """
        Collapsed text of each element in an XPath result, empties dropped.
        """
        return [t for t in (self._collapse_text(n) for n in nodes) if t]