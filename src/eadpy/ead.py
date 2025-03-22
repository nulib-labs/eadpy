import hashlib
import time
import os
from lxml import etree
import csv

class Ead:
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
    
    def __init__(self, file_path):
        """
        Initialize an Ead object with a file path and parse it immediately.
        
        Parameters:
        file_path (str): Path to the EAD XML file
        """
        self.file_path = file_path
        # A simple counter for generating fallback MD5 IDs
        self.counter = 0
        # Parse the file immediately
        self.data = self.parse()
    
    def parse(self):
        """
        Parse the EAD XML file and return a dictionary representing
        the parsed structure.
        """
        # Check if the file exists
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"EAD file not found: '{self.file_path}'. Please provide a valid file path.")
            
        if not os.path.isfile(self.file_path):
            raise IsADirectoryError(f"'{self.file_path}' is a directory, not a file. Please provide a valid XML file.")
            
        # Check if the file is readable
        if not os.access(self.file_path, os.R_OK):
            raise PermissionError(f"Permission denied: Unable to read '{self.file_path}'.")
            
        try:
            # Parse XML and strip namespaces
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(self.file_path, parser)
            self._remove_namespaces(tree)
            
            # We will use the root element for subsequent xpath queries
            root = tree.getroot()
            
            # Parse the top-level collection
            collection = self._parse_collection(root)
            
            # Identify all top-level components (c, c01..c12)
            component_nodes = root.xpath(
                "//archdesc/dsc/c | " + " | ".join(f"//archdesc/dsc/c{i:02d}" for i in range(1, 13))
            )
            
            # Parse child components under the main collection
            collection["components"] = self._parse_components(component_nodes, collection["id"])
            
            return collection
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Invalid XML in '{self.file_path}': {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error parsing EAD file '{self.file_path}': {str(e)}")
    
    def create_item_chunks(self):
        """
        Create item-focused chunks that include relevant information from their parent hierarchy.
        Returns a list of chunks ready for embedding.
        """
        chunks = []
        
        def process_items(component, ancestors=None):
            if ancestors is None:
                ancestors = []
                
            # Build current component info with relevant details
            current_component = {
                "id": component.get("id", ""),
                "title": component.get("title", ""),
                "level": component.get("level", ""),
                "date": component.get("normalized_date", ""),
                "extent": component.get("extent", [])
            }
            
            # Current hierarchy including this component
            current_ancestors = ancestors + [current_component]
            
            # For leaf items or any item-level component, create detailed chunks
            is_leaf = "components" not in component or not component["components"]
            is_item = component.get("level") == "item"
            
            if is_leaf or is_item:
                # Start with hierarchical path
                hierarchy_titles = [a.get("title") or "" for a in current_ancestors]
                hierarchy_path = " > ".join(hierarchy_titles)
                
                # Gather important dates and extent info from ancestors
                ancestor_dates = []
                ancestor_extents = []
                
                for ancestor in current_ancestors[:-1]:  # Exclude current component
                    if ancestor["date"] and ancestor["date"] not in ancestor_dates:
                        ancestor_dates.append(ancestor["date"])
                    
                    for extent in ancestor["extent"]:
                        if extent and extent not in ancestor_extents:
                            ancestor_extents.append(extent)
                
                # Create chunk data
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
                
                # Add notes from the current component
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
                
                # Add extent info from current component
                if current_component["extent"]:
                    chunk_data["content"].append({
                        "type": "extent",
                        "text": ", ".join(current_component["extent"])
                    })
                
                # Add subjects
                if component.get("access_subjects"):
                    chunk_data["content"].append({
                        "type": "subjects",
                        "text": ", ".join(component["access_subjects"])
                    })
                
                # Include digital objects if any
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
                    
                # Add creators if available
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
                
                # Generate final text for embedding
                text_parts = [f"Path: {chunk_data['path']}"]
                text_parts.append(f"Title: {chunk_data['title']}")
                
                if chunk_data["date"]:
                    text_parts.append(f"Date: {chunk_data['date']}")
                
                # Include ancestor dates if different from item date
                if ancestor_dates:
                    text_parts.append(f"Collection Dates: {', '.join(ancestor_dates)}")
                
                # Include ancestor extents
                if ancestor_extents:
                    text_parts.append(f"Collection Extent: {', '.join(ancestor_extents)}")
                
                # Add all content elements
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
            
            # Recursively process children
            if "components" in component:
                for child in component["components"]:
                    process_items(child, current_ancestors)
        
        # Start with the collection (self.data is the parsed EAD)
        process_items(self.data)
        
        return chunks

    def save_chunks_to_json(self, chunks, output_file):
        """
        Save chunks to a JSON file.
        
        Parameters:
        chunks (list): List of chunks to save
        output_file (str): Path to the output JSON file
        """
        import json
        
        with open(output_file, 'w') as f:
            json.dump(chunks, f, indent=2)

    def create_and_save_chunks(self, output_file):
        """
        Create item-focused chunks and save them to a JSON file.
        
        Parameters:
        output_file (str): Path to the output JSON file
        
        Returns:
        list: The chunks that were created and saved
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
                
            # Create a row for this component
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
                "path": " > ".join([(a.get("title") or "") for a in ancestors] + [(component.get("title") or "")])
            }
            
            # Add extent information
            if component.get("extent"):
                row["extent"] = ", ".join([(item or "") for item in component["extent"]])
            else:
                row["extent"] = ""
                
            # Add creators information
            if component.get("creators"):
                creators = []
                for creator in component["creators"]:
                    if creator.get("name"):
                        creators.append(f"{creator['name']} ({creator.get('type', '')})")
                row["creators"] = "; ".join(creators)
            else:
                row["creators"] = ""
                
            # Add container information if available
            if component.get("containers"):
                containers = []
                for container in component["containers"]:
                    if container.get("type") and container.get("value"):
                        containers.append(f"{container['type']}: {container['value']}")
                row["containers"] = "; ".join(containers)
            else:
                row["containers"] = ""
                
            # Add notes
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
                
            # Add subjects
            if component.get("access_subjects"):
                row["subjects"] = ", ".join([(item or "") for item in component["access_subjects"]])
            else:
                row["subjects"] = ""
                
            # Add row to results
            csv_data.append(row)
            
            # Process children recursively
            current_ancestors = ancestors + [component]
            if "components" in component:
                for child in component["components"]:
                    process_component(child, current_ancestors, depth + 1)
        
        # Start with the collection (self.data is the parsed EAD)
        process_component(self.data)
        
        return csv_data
    
    def save_csv_data(self, csv_data, output_file):
        """
        Save CSV data to a file.
        
        Parameters:
        csv_data (list): List of dictionaries representing CSV rows
        output_file (str): Path to the output CSV file
        """
        if not csv_data:
            raise ValueError("No CSV data to save")
            
        # Get fieldnames from the first row
        fieldnames = list(csv_data[0].keys())
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)
    
    def create_and_save_csv(self, output_file):
        """
        Create flattened CSV data and save it to a file.
        
        Parameters:
        output_file (str): Path to the output CSV file
        
        Returns:
        list: The CSV data that was created and saved
        """
        csv_data = self.create_csv_data()
        self.save_csv_data(csv_data, output_file)
        return csv_data
    
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
        Generate unique identifier if reference_id is None, otherwise
        prepend parent_id if present.
        """
        if reference_id:
            return f"{parent_id}_{reference_id}" if parent_id else reference_id
        else:
            # fallback to random hash
            random_str = str(time.time())
            md5_hash = hashlib.md5(random_str.encode("utf-8")).hexdigest()[:9]
            return f"{parent_id}_{md5_hash}" if parent_id else md5_hash
    
    def _parse_collection(self, root):
        """
        Parse the top-level <archdesc> as a 'collection'.
        """
        ead_id_node = root.xpath("//eadheader/eadid")
        ead_id = ead_id_node[0].text.strip() if ead_id_node else None
        
        title = self._parse_title(root)
        normalized_date = self._parse_normalized_date(root)
        
        collection = {
            "id": ead_id,
            "level": "collection",
            "title": title,
            "normalized_title": self._normalize_title(title, normalized_date),
            "dates": self._parse_dates(root),
            "normalized_date": normalized_date,
            "creators": self._parse_creators(root),
            "extent": self._parse_extent(root),
            "language": [x.strip() for x in root.xpath("//archdesc/did/langmaterial/text()")],
            "physdesc": self._parse_physdesc(root),
            "repository": self._extract_all_text(root.xpath("//repository")),
            "unitid": self._safe_strip(root.xpath("//archdesc/did/unitid/text()")),
            "notes": self._parse_notes(root),
            "access_subjects": self._parse_access_subjects(root),
            "geo_names": [x.strip() for x in root.xpath("//archdesc/controlaccess/geogname/text()")],
            "digital_objects": self._parse_digital_objects(
                root.xpath("//archdesc/did/dao | //archdesc/dao")
            ),
            "has_online_content": len(root.xpath("//dao")) > 0
        }
        return collection
    
    def _parse_components(self, component_nodes, parent_id):
        """
        Recursively parse all <cXX> child components.
        """
        components = []
        for node in component_nodes:
            ref_id = node.get("id")
            if not ref_id:
                # fallback for missing @id in the node
                self.counter += 1
                fallback = f"{parent_id}_{self.counter}"
                ref_id = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:9]
            
            component_id = self._generate_id(ref_id, parent_id)
            
            title = self._safe_strip(node.xpath("./did/unittitle/text()"))
            normalized_date = self._parse_normalized_component_date(node)
            
            component = {
                "id": component_id,
                "ref_id": ref_id,
                "parent_id": parent_id,
                "level": self._parse_level(node),
                "title": title,
                "normalized_title": self._normalize_title(title, normalized_date),
                "dates": self._parse_component_dates(node),
                "normalized_date": normalized_date,
                "unitid": self._safe_strip(node.xpath("./did/unitid/text()")),
                "creators": self._parse_component_creators(node),
                "extent": self._parse_component_extent(node),
                "notes": self._parse_component_notes(node),
                "containers": self._parse_containers(node),
                "access_subjects": self._parse_component_access_subjects(node),
                "digital_objects": self._parse_digital_objects(
                    node.xpath("./dao | ./did/dao")
                ),
                "has_online_content": len(node.xpath(".//dao")) > 0,
            }
            
            # Recursively parse children of this node
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
        title_node = root.xpath("//archdesc/did/unittitle/text()")
        return title_node[0].strip() if title_node else None
    
    def _parse_dates(self, root):
        """
        Return a dict of date types: inclusive, bulk, and other at the collection level.
        """
        return {
            "inclusive": [x.strip() for x in root.xpath('//archdesc/did/unitdate[@type="inclusive"]/text()')],
            "bulk": [x.strip() for x in root.xpath('//archdesc/did/unitdate[@type="bulk"]/text()')],
            "other": [x.strip() for x in root.xpath('//archdesc/did/unitdate[not(@type)]/text()')]
        }
    
    def _parse_component_dates(self, node):
        """
        Return a dict of date types: inclusive, bulk, and other for a component.
        """
        return {
            "inclusive": [x.strip() for x in node.xpath('./did/unitdate[@type="inclusive"]/text()')],
            "bulk": [x.strip() for x in node.xpath('./did/unitdate[@type="bulk"]/text()')],
            "other": [x.strip() for x in node.xpath('./did/unitdate[not(@type)]/text()')]
        }
    
    def _parse_normalized_date(self, root):
        """
        Concatenate inclusive, bulk, other collection-level dates into a single string.
        """
        inclusive = [x.strip() for x in root.xpath('//archdesc/did/unitdate[@type="inclusive"]/text()')]
        bulk = [x.strip() for x in root.xpath('//archdesc/did/unitdate[@type="bulk"]/text()')]
        other = [x.strip() for x in root.xpath('//archdesc/did/unitdate[not(@type)]/text()')]
        
        normalized = []
        if inclusive:
            normalized.extend(inclusive)
        if bulk:
            normalized.append(f"bulk {', '.join(bulk)}")
        if other:
            normalized.extend(other)
        
        return ", ".join(normalized) if normalized else None
    
    def _parse_normalized_component_date(self, node):
        """
        Concatenate inclusive, bulk, other component-level dates into a single string.
        """
        inclusive = [x.strip() for x in node.xpath('./did/unitdate[@type="inclusive"]/text()')]
        bulk = [x.strip() for x in node.xpath('./did/unitdate[@type="bulk"]/text()')]
        other = [x.strip() for x in node.xpath('./did/unitdate[not(@type)]/text()')]
        
        normalized = []
        if inclusive:
            normalized.extend(inclusive)
        if bulk:
            normalized.append(f"bulk {', '.join(bulk)}")
        if other:
            normalized.extend(other)
        
        return ", ".join(normalized) if normalized else None
    
    def _parse_extent(self, root):
        """
        Collect <extent> under the collection-level <physdesc>.
        """
        return [x.strip() for x in root.xpath('//archdesc/did/physdesc/extent/text()')]
    
    def _parse_component_extent(self, node):
        """
        Collect <extent> for a component-level <physdesc>.
        """
        return [x.strip() for x in node.xpath('./did/physdesc/extent/text()')]
    
    def _parse_physdesc(self, root):
        """
        Extract textual content from <physdesc> for the collection-level.
        """
        entries = []
        physdesc_nodes = root.xpath('//archdesc/did/physdesc')
        for pnode in physdesc_nodes:
            # Join all non-element child text
            text_parts = []
            for child in pnode.itertext():
                if child.strip():
                    text_parts.append(child.strip())
            joined_text = " ".join(text_parts).strip()
            if joined_text:
                entries.append(joined_text)
        return entries
    
    def _parse_creators(self, root):
        """
        Collect <origination> name elements for the collection.
        """
        creators = []
        for name_el in self.NAME_ELEMENTS:
            path = f"//archdesc/did/origination/{name_el}/text()"
            for text_node in root.xpath(path):
                creators.append({"type": name_el, "name": text_node.strip()})
        return creators
    
    def _parse_component_creators(self, node):
        """
        Collect <origination> name elements for a component.
        """
        creators = []
        for name_el in self.NAME_ELEMENTS:
            path = f"./did/origination/{name_el}/text()"
            for text_node in node.xpath(path):
                creators.append({"type": name_el, "name": text_node.strip()})
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
                "value": c.text.strip() if c.text else None
            })
        return containers
    
    def _parse_notes(self, root):
        """
        Parse <archdesc> notes. Some are directly under <archdesc>, 
        some are under <archdesc>/did.
        """
        notes = {}
        
        # Parse top-level (archdesc) notes
        for field in self.SEARCHABLE_NOTES_FIELDS:
            content_nodes = root.xpath(f"//archdesc/{field}")
            if content_nodes:
                field_values = []
                for node in content_nodes:
                    heading = "".join(node.xpath('./head/text()')).strip()
                    content_texts = []
                    # gather all text except <head>
                    for child in node.xpath('./*[local-name()!="head"]'):
                        content_texts.append("".join(child.itertext()).strip())
                    
                    field_values.append({
                        "heading": heading,
                        "content": content_texts
                    })
                notes[field] = field_values
        
        # Parse <did> notes fields
        for field in self.DID_SEARCHABLE_NOTES_FIELDS:
            content_nodes = root.xpath(f"//archdesc/did/{field}/text()")
            if content_nodes:
                notes[field] = [c.strip() for c in content_nodes if c.strip()]
        
        return notes
    
    def _parse_component_notes(self, node):
        """
        Parse notes for a particular component node (e.g. <cXX>).
        """
        notes = {}
        
        for field in self.SEARCHABLE_NOTES_FIELDS:
            content_nodes = node.xpath(f"./{field}")
            if content_nodes:
                field_values = []
                for cnode in content_nodes:
                    heading = "".join(cnode.xpath('./head/text()')).strip()
                    content_texts = []
                    for child in cnode.xpath('./*[local-name()!="head"]'):
                        content_texts.append("".join(child.itertext()).strip())
                    
                    field_values.append({
                        "heading": heading,
                        "content": content_texts
                    })
                notes[field] = field_values
        
        for field in self.DID_SEARCHABLE_NOTES_FIELDS:
            content_nodes = node.xpath(f"./did/{field}/text()")
            if content_nodes:
                notes[field] = [c.strip() for c in content_nodes if c.strip()]
        
        return notes
    
    def _parse_access_subjects(self, root):
        """
        Collect subject, function, occupation, genreform under <controlaccess> at collection-level.
        """
        subjects = []
        control_access_nodes = root.xpath("//archdesc/controlaccess")
        for canode in control_access_nodes:
            for selector in ["subject", "function", "occupation", "genreform"]:
                for text_node in canode.xpath(f".//{selector}/text()"):
                    if text_node.strip():
                        subjects.append(text_node.strip())
        return subjects
    
    def _parse_component_access_subjects(self, node):
        """
        Collect subject, function, occupation, genreform under <controlaccess> at component-level.
        """
        subjects = []
        control_access_nodes = node.xpath("./controlaccess")
        for canode in control_access_nodes:
            for selector in ["subject", "function", "occupation", "genreform"]:
                for text_node in canode.xpath(f".//{selector}/text()"):
                    if text_node.strip():
                        subjects.append(text_node.strip())
        return subjects
    
    def _parse_digital_objects(self, dao_nodes):
        """
        Collect digital object references from <dao> or <did/dao>.
        """
        digital_objects = []
        for dao in dao_nodes:
            # Look for @title attribute or nested <daodesc><p> text
            label = dao.get("title")
            if not label:
                # fallback: look for <daodesc><p> text
                label_candidate = dao.xpath("daodesc/p/text()")
                label = label_candidate[0].strip() if label_candidate else None
            
            # Check for href or xlink:href
            href = dao.get("href")
            if not href:
                href = dao.get("{http://www.w3.org/1999/xlink}href")
            
            if href:
                digital_objects.append({"label": label, "href": href})
        
        return digital_objects
    
    def _safe_strip(self, nodes):
        """
        Return the first node as stripped text if present, else None.
        """
        if not nodes:
            return None
        if isinstance(nodes, list):
            # lxml returns a list from xpath
            return nodes[0].strip() if nodes[0] else None
        return nodes.strip() if nodes else None

    def _extract_all_text(self, nodes):
        """
        Extract all text content from an element including nested elements.
        """
        if not nodes:
            return None
            
        node = nodes[0] if isinstance(nodes, list) else nodes
        return " ".join(node.itertext()).strip() if node is not None else None
