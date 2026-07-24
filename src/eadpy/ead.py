import itertools
import os
import re
import io
import warnings
import csv
from typing import Optional

from lxml import etree

from eadpy import parsers
from eadpy.exceptions import EadParseError

class EAD:
    #: Header sections, never dropped by the audience="internal" filter.
    HEADER_TAGS = frozenset({"eadheader", "control"})

    #: Archival description roots, whose removal leaves nothing to parse.
    DESCRIPTION_TAGS = frozenset({"archdesc", "archDesc"})

    def __init__(self, ead_source, include_internal: bool = False) -> None:
        """
        Initializes the EAD object by parsing the EAD source.

        Best practice is to use the class methods `from_path`, `from_string`,
        `from_bytes`, or `from_file` to create instances.

        Parameters
        ----------
        ead_source : str or file-like object
            A file path (string) or a file-like object containing the EAD XML.
            lxml.etree.parse can handle both.
        include_internal : bool, optional
            Keep content marked audience="internal" (staff-only description,
            such as unpublished ArchivesSpace records). Excluded by default.
        """
        self.ead_source_repr = repr(ead_source) # For error messages
        self._id_counter = itertools.count(1)
        self._ead_version = None
        self.include_internal = include_internal
        self.data = self._parse(ead_source)

    @property
    def ead_version(self) -> Optional[str]:
        """
        The detected EAD version of the parsed document: "2002", "ead3",
        or "ead4". None if parsing has not completed.
        """
        return self._ead_version

    @classmethod
    def from_path(cls, file_path: str, *, include_internal: bool = False) -> "EAD":
        """
        Creates an EAD instance from a file path.
        
        Parameters
        ----------
        file_path : str
            Path to the EAD XML file
        include_internal : bool, optional
            Keep content marked audience="internal" (staff-only description).
            Excluded by default.

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
        return cls(file_path, include_internal)

    @classmethod
    def from_string(cls, xml_string: str, encoding: Optional[str] = None, *,
                    include_internal: bool = False) -> "EAD":
        """
        Creates an EAD instance from an XML string.

        Parameters
        ----------
        xml_string : str
            String containing EAD XML content
        encoding : str, optional
            Deprecated and ignored; passing it raises a DeprecationWarning.
            A Python str carries no byte encoding, so the string is always
            encoded to UTF-8 for parsing.
        include_internal : bool, optional
            Keep content marked audience="internal" (staff-only description).
            Excluded by default.

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
        if encoding is not None:
            warnings.warn(
                "The 'encoding' parameter is deprecated and ignored: a Python "
                "str is already decoded, so it is always encoded to UTF-8 for "
                "parsing. Pass bytes to from_bytes() to control decoding.",
                DeprecationWarning,
                stacklevel=2,
            )
        # The string is already decoded, so an XML declaration naming some
        # other encoding no longer applies — left in place it would make the
        # parser mis-decode the UTF-8 bytes produced below.
        xml_string = re.sub(r'^\s*<\?xml[^>]*\?>', '', xml_string, count=1)
        try:
            xml_bytes = xml_string.encode('utf-8')
        except Exception as e:  # pragma: no cover - encoding a str to UTF-8 cannot fail
            raise ValueError(f"Error encoding string: {e}")
        return cls(io.BytesIO(xml_bytes), include_internal)

    @classmethod
    def from_bytes(cls, xml_bytes: bytes, *, include_internal: bool = False) -> "EAD":
        """
        Creates an EAD instance from XML bytes.
        
        Parameters
        ----------
        xml_bytes : bytes
            Bytes containing EAD XML content
        include_internal : bool, optional
            Keep content marked audience="internal" (staff-only description).
            Excluded by default.

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
        return cls(bytes_io, include_internal)

    @classmethod
    def from_file(cls, file_like_object, *, include_internal: bool = False) -> "EAD":
        """
        Creates an EAD instance from an open file-like object.
        
        Parameters
        ----------
        file_like_object : file object
            A file-like object with a 'read' method containing EAD XML content
        include_internal : bool, optional
            Keep content marked audience="internal" (staff-only description).
            Excluded by default.

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
            # from_string re-encodes to UTF-8, avoiding the encoding
            # declaration issues a decoded StringIO would otherwise hit.
            return cls.from_string(file_like_object.read(),
                                   include_internal=include_internal)
        
        # It's already a binary file-like object (BytesIO or file opened in binary mode)
        return cls(file_like_object, include_internal)

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

            # The schema namespace identifies the EAD version, so detect it
            # before namespaces are stripped for consistent XPath.
            root = tree.getroot()
            self._ead_version = parsers.detect_version(root)
            self._remove_namespaces(tree)

            if not self.include_internal:
                self._strip_internal_audience(root)

            version_parser = parsers.PARSERS[self._ead_version]()
            return version_parser.parse(root)

        except etree.XMLSyntaxError as e:
            raise EadParseError(
                f"Invalid XML detected in {self.ead_source_repr}: {str(e)}"
            )
        except ValueError:
            raise # Version/root checks above raise EadParseError with a clear message
        # from_path pre-checks both of these and lxml reports read failures as
        # plain OSError, so these only catch a file-like source whose read() raises.
        except FileNotFoundError:  # pragma: no cover
            raise
        except PermissionError:  # pragma: no cover
            raise
        except IOError as e:
            raise IOError(f"Error reading from {self.ead_source_repr}: {e}")
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error parsing EAD input {self.ead_source_repr}: {str(e)}"
            )

    def create_item_chunks(self) -> list:
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

                subject_texts = [
                    t["text"] for t in component.get("access_terms", [])
                ] or component.get("access_subjects", [])
                if subject_texts:
                    chunk_data["content"].append({
                        "type": "subjects",
                        "text": ", ".join(subject_texts)
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

    def save_chunks_to_json(self, chunks: list, output_file: str) -> None:
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

    def create_and_save_chunks(self, output_file: str) -> list:
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

    def create_csv_data(self) -> list:
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

            subject_texts = [
                (t.get("text") or "") for t in component.get("access_terms", [])
            ] or [(item or "") for item in component.get("access_subjects", [])]
            row["subjects"] = ", ".join(subject_texts)

            csv_data.append(row)

            current_ancestors = ancestors + [component]
            if "components" in component:
                for child in component["components"]:
                    process_component(child, current_ancestors, depth + 1)

        process_component(self.data)
        return csv_data

    def save_csv_data(self, csv_data: list, output_file: str) -> None:
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

    def create_and_save_csv(self, output_file: str) -> list:
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

    @staticmethod
    def _detach(node):
        """
        Remove a node from its tree, reattaching its tail text to whatever
        preceded it so surrounding prose keeps its spacing.
        """
        parent = node.getparent()
        tail = node.tail or ""
        prev = node.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail
        parent.remove(node)

    def _strip_internal_audience(self, element):
        """
        Remove elements marked audience="internal" — content the describing
        institution flagged as staff-only (unpublished ArchivesSpace records
        export this way, as do internal-use <dao> links).

        The header sections are exempt: <eadheader audience="internal"> is a
        common convention for the finding aid's own metadata, and dropping it
        would take the record identifier with it.
        """
        for child in list(element):
            if not isinstance(child.tag, str) or child.tag in self.HEADER_TAGS:
                continue
            if child.get("audience") == "internal":
                if child.tag in self.DESCRIPTION_TAGS:
                    # Removing this empties the record entirely; say so, rather
                    # than leaving the caller to wonder why output is blank.
                    warnings.warn(
                        f"The archival description in {self.ead_source_repr} is "
                        'marked audience="internal", so the parsed record is '
                        "empty. Pass include_internal=True to keep it.",
                        UserWarning,
                        stacklevel=2,
                    )
                self._detach(child)
            else:
                self._strip_internal_audience(child)

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
            self._detach(node)
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

    def _generate_id(self, reference_id, parent_id=None):
        """
        Generate an identifier if reference_id is None,
        otherwise prepend parent_id if present.
        """
        return parsers.generate_id(reference_id, parent_id, self._id_counter)

    def _normalize_title(self, title, date_str):
        """
        If both title and date_str exist, combine them.
        """
        return parsers.normalize_title(title, date_str)
