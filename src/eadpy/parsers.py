"""
Version-specific EAD parsers.

Each parser turns a namespace-stripped lxml element tree into the same
normalized collection dict, so downstream consumers (chunks, CSV) are
version-agnostic. The three parser classes are deliberately independent —
EAD3 and EAD 4.0 are separate standards, not variations on a base class —
and share only the version-neutral helpers defined at module level.
"""
import hashlib
import itertools
import re

from lxml import etree

from eadpy.exceptions import EadParseError

#: Schema namespace URIs mapped to eadpy version identifiers.
NAMESPACE_VERSIONS = {
    "urn:isbn:1-931666-22-9": "2002",
    "http://ead3.archivists.org/schema/": "ead3",
    "http://ead3.archivists.org/schema/undeprecated/": "ead3",
    "https://standards.openpreservation.org/ead/v4": "ead4",
}

#: Component element names, shared by all EAD versions.
COMPONENT_TAGS = frozenset(["c"] + [f"c{i:02d}" for i in range(1, 13)])


def detect_version(root):
    """
    Identify the EAD version of a parsed document from its root element.

    Must be called before namespaces are stripped: the schema namespace is
    the authoritative signal. Documents without a namespace fall back to
    structural heuristics on the root's child elements.

    Parameters
    ----------
    root : lxml.etree._Element
        Root element of the parsed document, namespaces intact.

    Returns
    -------
    str
        One of "2002", "ead3", or "ead4".

    Raises
    ------
    EadParseError
        If the root element is not <ead> or carries an unrecognized namespace.
    """
    qname = etree.QName(root.tag)
    if qname.localname != "ead":
        raise EadParseError(
            f"Unexpected root element <{qname.localname}>; expected <ead>."
        )
    if qname.namespace is not None:
        try:
            return NAMESPACE_VERSIONS[qname.namespace]
        except KeyError:
            raise EadParseError(
                f"Unrecognized namespace '{qname.namespace}' on <ead> root; "
                "expected EAD 2002, EAD3, or EAD 4.0."
            )
    child_tags = {
        child.tag.split("}", 1)[-1]
        for child in root
        if isinstance(child.tag, str)
    }
    if "eadheader" in child_tags:
        return "2002"
    if "archDesc" in child_tags or "findAidDesc" in child_tags:
        return "ead4"
    if "control" in child_tags:
        return "ead3"
    return "2002"


def collapse_text(node):
    """
    Full text of an element with whitespace runs collapsed. Suitable for
    prose and mixed content, where inline markup (persname, title, emph,
    ...) interrupts the text but natural spacing surrounds it.
    """
    if node is None:
        return None
    text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
    return text or None


def joined_text(node):
    """
    Text of an element joined piece-by-piece with spaces. Suitable for
    element-only content (e.g. physdesc, repository) whose children are
    discrete values that would otherwise run together.
    """
    if node is None:
        return None
    # Pieces are collapsed as well as stripped: hand-edited finding aids
    # hard-wrap prose, and remove_blank_text drops only whitespace-only nodes.
    parts = [re.sub(r"\s+", " ", p).strip() for p in node.itertext()]
    return " ".join(p for p in parts if p) or None


def first_text(nodes):
    """
    Collapsed text of the first element in an XPath result, else None.
    """
    return collapse_text(nodes[0]) if nodes else None


def first_of(values):
    """
    First item of an XPath result (e.g. an attribute query), else None.
    """
    return str(values[0]) if values else None


def texts(nodes):
    """
    Collapsed text of each element in an XPath result, empties dropped.
    """
    return [t for t in (collapse_text(n) for n in nodes) if t]


def normalize_title(title, date_str):
    """
    If both title and date_str exist, combine them.
    """
    if not title or not date_str:
        return title
    return f"{title}, {date_str}"


def generate_id(reference_id, parent_id, counter):
    """
    Generate an identifier if reference_id is None,
    otherwise prepend parent_id if present.

    counter is an iterator (e.g. itertools.count) advanced only when a
    fallback hash is needed, so repeat parses yield stable ids.
    """
    if reference_id:
        return f"{parent_id}_{reference_id}" if parent_id else reference_id
    md5_hash = hashlib.md5(
        f"{parent_id}_{next(counter)}".encode("utf-8")
    ).hexdigest()[:9]
    return f"{parent_id}_{md5_hash}" if parent_id else md5_hash


def add_authority(term, el, attr_map):
    """
    Copy any authority-control attributes present on el into term, using
    attr_map pairs of (attribute name, output key). Keys are added only
    when the attribute exists, so plain terms stay minimal.
    """
    for attr, key in attr_map:
        value = el.get(attr)
        if value:
            term[key] = value


def aspace_uri(value):
    """
    The repository-relative record URI that ArchivesSpace stashes in
    @altrender on <archdesc> and <c> in its EAD3 exports; any other use of
    @altrender is a presentational hint and returns None.
    """
    if value and value.startswith("/repositories/"):
        return value
    return None


def format_normalized_date(dates):
    """
    Concatenate inclusive, bulk, and other dates into a single display string.
    """
    normalized = list(dates["inclusive"])
    if dates["bulk"]:
        normalized.append(f"bulk {', '.join(dates['bulk'])}")
    normalized.extend(dates["other"])
    return ", ".join(normalized) if normalized else None


def note_content(node):
    """
    Text blocks of a note element: direct text plus one entry per child
    element (excluding <head>), so block structure survives as separate
    list entries.
    """
    entries = []

    def add_raw(raw):
        if raw and raw.strip():
            entries.append(re.sub(r"\s+", " ", raw).strip())

    add_raw(node.text)
    for child in node:
        # Skip comments and processing instructions (their .tag is not a
        # string), but keep any text trailing them.
        if isinstance(child.tag, str) and child.tag != "head":
            block = block_text(child)
            if block:
                entries.append(block)
        add_raw(child.tail)
    return entries


def block_text(node):
    """
    Text of a block element inside a note. Prose blocks keep their inline
    spacing; element-only blocks (chronlist, list, table, ...) get their
    pieces space-separated so adjacent values don't run together.
    """
    has_own_text = bool(node.text and node.text.strip()) or any(
        child.tail and child.tail.strip() for child in node
    )
    if len(node) == 0 or has_own_text:
        return collapse_text(node)
    return joined_text(node)


def _note_heading(node):
    """
    Collapsed text of a note's <head> child, else empty string.
    """
    head_nodes = node.xpath("./head")
    return (collapse_text(head_nodes[0]) or "") if head_nodes else ""


class EAD2002Parser:
    """
    Parser for EAD 2002 documents (namespace urn:isbn:1-931666-22-9).
    """

    NAME_ELEMENTS = ["corpname", "famname", "name", "persname"]

    SEARCHABLE_NOTES_FIELDS = [
        "accessrestrict", "accruals", "acqinfo", "altformavail", "appraisal",
        "arrangement", "bibliography", "bioghist", "custodhist", "fileplan",
        "note", "odd", "originalsloc", "otherfindaid", "phystech", "prefercite",
        "processinfo", "relatedmaterial", "scopecontent", "separatedmaterial",
        "userestrict"
    ]

    DID_SEARCHABLE_NOTES_FIELDS = [
        "abstract", "materialspec", "physloc", "note"
    ]

    # Every <controlaccess> child treated as an access term: the topical
    # elements plus names and titles used as access points.
    ACCESS_TERM_ELEMENTS = [
        "subject", "function", "occupation", "genreform", "geogname",
        "persname", "corpname", "famname", "name", "title"
    ]

    # The subset reported in the legacy access_subjects string list.
    SUBJECT_ELEMENTS = ["subject", "function", "occupation", "genreform"]

    #: Authority-control attributes → normalized output keys.
    AUTHORITY_ATTRS = (
        ("source", "source"),
        ("authfilenumber", "identifier"),
        ("role", "relator"),
    )

    def __init__(self):
        self._counter = itertools.count(1)

    def parse(self, root):
        """
        Parse a namespace-stripped document into the collection dict.
        """
        collection = self._parse_collection(root)

        # Identify all top-level components (c, c01..c12). EAD 2002 allows
        # <dsc> groups nested inside <dsc>, so match components under any
        # dsc; their own nested components are handled recursively.
        component_nodes = root.xpath(
            "/ead/archdesc//dsc/c | "
            + " | ".join(f"/ead/archdesc//dsc/c{i:02d}" for i in range(1, 13))
        )
        collection["components"] = self._parse_components(
            component_nodes, collection["id"]
        )
        return collection

    def _parse_collection(self, root):
        """
        Parse the top-level <archdesc> as a 'collection'.
        """
        ead_id_node = root.xpath("//eadheader/eadid")
        ead_id = (ead_id_node[0].text or "").strip() or None if ead_id_node else None

        title = first_text(root.xpath("//archdesc/did/unittitle"))
        dates = self._parse_dates(root, "//archdesc/did/")
        normalized_date = format_normalized_date(dates)
        repository_nodes = root.xpath("//repository")
        access_terms = self._parse_access_terms(root, "//archdesc/")

        collection = {
            "id": ead_id,
            "level": "collection",
            "title": title,
            "normalized_title": normalize_title(title, normalized_date),
            "dates": dates,
            "normalized_date": normalized_date,
            "creators": self._parse_creators(root, "//archdesc/did/"),
            "extent": self._parse_extent(root, "//archdesc/did/"),
            "language": self._parse_language(root),
            "physdesc": self._parse_physdesc(root),
            "repository": joined_text(repository_nodes[0]) if repository_nodes else None,
            "unitid": self._parse_unitid(root, "//archdesc/did/"),
            "notes": self._parse_notes(root, "//archdesc/"),
            "access_subjects": self._subject_texts(access_terms),
            "access_terms": access_terms,
            "geo_names": texts(root.xpath("//archdesc/controlaccess//geogname")),
            "digital_objects": self._parse_digital_objects(
                root.xpath("//archdesc/did/dao | //archdesc/dao")
            ),
            # Deliberately document-wide: a <dao> anywhere, including inside
            # components, means the collection has online content.
            "has_online_content": len(root.xpath("//dao")) > 0
        }
        uri = self._parse_aspace_unitid(root, "//archdesc/did/")
        if uri:
            collection["uri"] = uri
        return collection

    def _parse_unitid(self, node, prefix):
        """
        The record's call number: the first <unitid> that isn't the
        ArchivesSpace record URI its EAD exports add as a sibling.
        """
        return first_text(
            node.xpath(f'{prefix}unitid[not(@type="aspace_uri")]')
        )

    def _parse_aspace_unitid(self, node, prefix):
        """
        The ArchivesSpace repository-relative record URI, exported as
        <unitid type="aspace_uri">, else None.
        """
        return first_text(node.xpath(f'{prefix}unitid[@type="aspace_uri"]'))

    def _parse_components(self, component_nodes, parent_id):
        """
        Recursively parse all <cXX> child components.
        """
        components = []
        for node in component_nodes:
            ref_id = node.get("id")
            if not ref_id:
                fallback = f"{parent_id}_{next(self._counter)}"
                ref_id = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:9]

            component_id = generate_id(ref_id, parent_id, self._counter)
            title = first_text(node.xpath("./did/unittitle"))
            dates = self._parse_dates(node, "./did/")
            normalized_date = format_normalized_date(dates)
            access_terms = self._parse_access_terms(node, "./")

            component = {
                "id": component_id,
                "ref_id": ref_id,
                "parent_id": parent_id,
                "level": self._parse_level(node),
                "title": title,
                "normalized_title": normalize_title(title, normalized_date),
                "dates": dates,
                "normalized_date": normalized_date,
                "unitid": self._parse_unitid(node, "./did/"),
                "creators": self._parse_creators(node, "./did/"),
                "extent": self._parse_extent(node, "./did/"),
                "notes": self._parse_notes(node, "./"),
                "containers": self._parse_containers(node),
                "access_subjects": self._subject_texts(access_terms),
                "access_terms": access_terms,
                "digital_objects": self._parse_digital_objects(
                    node.xpath("./dao | ./did/dao")
                ),
                # Descendant daos deliberately count, so ancestors of
                # digitized material are also flagged as online content.
                "has_online_content": len(node.xpath(".//dao")) > 0,
            }
            uri = self._parse_aspace_unitid(node, "./did/")
            if uri:
                component["uri"] = uri

            child_selector = "./c" + "".join(f"|./c{i:02d}" for i in range(1, 13))
            child_nodes = node.xpath(child_selector)
            if child_nodes:
                component["components"] = self._parse_components(
                    child_nodes, component_id
                )

            components.append(component)
        return components

    def _parse_language(self, root):
        """
        Languages of the material. Standard EAD 2002 wraps each language in a
        <language> child of <langmaterial>; fall back to the langmaterial
        prose when no <language> children exist.
        """
        language_nodes = root.xpath("//archdesc/did/langmaterial//language")
        if language_nodes:
            return texts(language_nodes)
        return texts(root.xpath("//archdesc/did/langmaterial"))

    def _parse_dates(self, node, prefix):
        """
        Return a dict of unitdate display values grouped by type, plus any
        machine-readable @normal attribute values.
        """
        return {
            "inclusive": texts(node.xpath(f'{prefix}unitdate[@type="inclusive"]')),
            "bulk": texts(node.xpath(f'{prefix}unitdate[@type="bulk"]')),
            "other": texts(node.xpath(f'{prefix}unitdate[not(@type)]')),
            "normal": [str(v) for v in node.xpath(f'{prefix}unitdate/@normal')]
        }

    def _parse_extent(self, node, prefix):
        """
        Collect <extent> under a <physdesc>, along with any <physfacet>
        and <dimensions> qualifiers. A <physdesc> without <extent>
        children carries its description as prose.
        """
        extents = []
        for pd in node.xpath(f"{prefix}physdesc"):
            extent_texts = texts(pd.xpath("./extent"))
            if extent_texts:
                extents.extend(extent_texts)
                extents.extend(texts(pd.xpath("./physfacet | ./dimensions")))
            else:
                joined = joined_text(pd)
                if joined:
                    extents.append(joined)
        return extents

    def _parse_physdesc(self, root):
        """
        Extract textual content from <physdesc> for the collection-level.
        """
        entries = []
        for pnode in root.xpath('//archdesc/did/physdesc'):
            joined = joined_text(pnode)
            if joined:
                entries.append(joined)
        return entries

    def _parse_creators(self, node, prefix):
        """
        Collect <origination> name elements, keeping any authority
        attributes. An <origination> with no name-element children
        carries its creator as bare text.
        """
        creators = []
        for orig in node.xpath(f"{prefix}origination"):
            named = False
            for name_el in self.NAME_ELEMENTS:
                for el in orig.xpath(f"./{name_el}"):
                    name = collapse_text(el)
                    if name:
                        named = True
                        creator = {"type": name_el, "name": name}
                        add_authority(creator, el, self.AUTHORITY_ATTRS)
                        creators.append(creator)
            if not named:
                name = collapse_text(orig)
                if name:
                    creators.append({"type": "origination", "name": name})
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
        for c in node.xpath('./did/container'):
            container = {
                # Older files (e.g. Bentley legacy EAD) put the container
                # kind in @label rather than @type.
                "type": c.get("type") or c.get("label"),
                "value": collapse_text(c)
            }
            # ArchivesSpace chains sub-containers ("Folder 3") to their
            # parent ("Box 2") through @id/@parent.
            if c.get("id"):
                container["containerid"] = c.get("id")
            if c.get("parent"):
                container["parent"] = c.get("parent")
            containers.append(container)
        return containers

    def _parse_notes(self, node, prefix):
        """
        Parse note fields. Some are direct children of <archdesc>/<cXX>,
        some live under the <did>, and legacy files group them inside
        <descgrp> (one level of nesting allowed) or <add> wrappers.
        """
        notes = {}
        for field in self.SEARCHABLE_NOTES_FIELDS:
            content_nodes = node.xpath(
                f"{prefix}{field}"
                f" | {prefix}descgrp/{field}"
                f" | {prefix}descgrp/descgrp/{field}"
                f" | {prefix}add/{field}"
            )
            if content_nodes:
                notes[field] = [
                    {"heading": _note_heading(cnode), "content": note_content(cnode)}
                    for cnode in content_nodes
                ]

        for field in self.DID_SEARCHABLE_NOTES_FIELDS:
            values = texts(node.xpath(f"{prefix}did/{field}"))
            if values:
                notes[field] = values
        return notes

    def _parse_access_terms(self, node, prefix):
        """
        Collect every access term under <controlaccess> — including terms
        inside nested <controlaccess> groups — as a dict of text, source
        element type, and any authority attributes present.
        """
        terms = []
        for canode in node.xpath(f"{prefix}controlaccess"):
            for selector in self.ACCESS_TERM_ELEMENTS:
                for el in canode.xpath(f".//{selector}"):
                    text = collapse_text(el)
                    if not text:
                        continue
                    term = {"text": text, "type": selector}
                    add_authority(term, el, self.AUTHORITY_ATTRS)
                    terms.append(term)
        return terms

    def _subject_texts(self, terms):
        """
        The legacy access_subjects view of a term list: topical texts only.
        """
        return [t["text"] for t in terms if t["type"] in self.SUBJECT_ELEMENTS]

    def _parse_digital_objects(self, dao_nodes):
        """
        Collect digital object references from <dao> or <did/dao>.
        """
        digital_objects = []
        for dao in dao_nodes:
            label = dao.get("title")
            if not label:
                label = first_text(dao.xpath("./daodesc/p"))

            href = dao.get("href")
            if not href:
                href = dao.get("{http://www.w3.org/1999/xlink}href")

            if href:
                digital_objects.append({"label": label, "href": href})

        return digital_objects


class EAD3Parser:
    """
    Parser for EAD3 documents (namespace http://ead3.archivists.org/schema/).

    EAD3 keeps the EAD 2002 skeleton (<archdesc>, <did>, <dsc>, <c>/<cXX>,
    <controlaccess>) but replaces <eadheader> with <control>, wraps name and
    subject text in <part> children, and adds structured alternatives that
    ArchivesSpace exports alongside the legacy forms: <unitdatestructured>
    next to <unitdate>, <physdescstructured> next to <physdesc>, and
    <daoset> grouping multiple <dao>.
    """

    NAME_ELEMENTS = ["corpname", "famname", "name", "persname"]

    # EAD3 dropped the generic <note> section element; the rest of the
    # EAD 2002 note vocabulary is unchanged.
    SEARCHABLE_NOTES_FIELDS = [
        "accessrestrict", "accruals", "acqinfo", "altformavail", "appraisal",
        "arrangement", "bibliography", "bioghist", "custodhist", "fileplan",
        "odd", "originalsloc", "otherfindaid", "phystech", "prefercite",
        "processinfo", "relatedmaterial", "scopecontent", "separatedmaterial",
        "userestrict"
    ]

    ACCESS_TERM_ELEMENTS = [
        "subject", "function", "occupation", "genreform", "geogname",
        "persname", "corpname", "famname", "name", "title"
    ]

    SUBJECT_ELEMENTS = ["subject", "function", "occupation", "genreform"]

    # Name-like terms join their <part> children with ', '; heading-like
    # terms join subdivisions with ' -- '.
    NAME_TERM_ELEMENTS = {"persname", "corpname", "famname", "name", "title"}

    #: Authority-control attributes → normalized output keys.
    AUTHORITY_ATTRS = (
        ("source", "source"),
        ("identifier", "identifier"),
        ("relator", "relator"),
    )

    # <did>-level notes: <note> became <didnote>, reported under the same
    # output key so downstream consumers see a stable schema.
    DID_NOTES_FIELDS = {
        "abstract": "abstract",
        "materialspec": "materialspec",
        "physloc": "physloc",
        "didnote": "note",
    }

    def __init__(self):
        self._counter = itertools.count(1)

    def parse(self, root):
        """
        Parse a namespace-stripped document into the collection dict.
        """
        collection = self._parse_collection(root)
        component_nodes = root.xpath(
            "/ead/archdesc//dsc/c | "
            + " | ".join(f"/ead/archdesc//dsc/c{i:02d}" for i in range(1, 13))
        )
        collection["components"] = self._parse_components(
            component_nodes, collection["id"]
        )
        return collection

    def _parse_collection(self, root):
        ead_id_node = root.xpath("//control/recordid")
        ead_id = (ead_id_node[0].text or "").strip() or None if ead_id_node else None

        title = first_text(root.xpath("//archdesc/did/unittitle"))
        dates = self._parse_dates(root, "//archdesc/did/")
        normalized_date = format_normalized_date(dates)
        repository_nodes = root.xpath("//archdesc/did/repository")
        access_terms = self._parse_access_terms(root, "//archdesc/")

        collection = {
            "id": ead_id,
            "level": "collection",
            "title": title,
            "normalized_title": normalize_title(title, normalized_date),
            "dates": dates,
            "normalized_date": normalized_date,
            "creators": self._parse_creators(root, "//archdesc/did/"),
            "extent": self._parse_extent(root, "//archdesc/did/"),
            "language": self._parse_language(root),
            "physdesc": self._parse_physdesc(root),
            "repository": self._repository_text(repository_nodes),
            "unitid": first_text(root.xpath("//archdesc/did/unitid")),
            "notes": self._parse_notes(root, "//archdesc/"),
            "access_subjects": self._subject_texts(access_terms),
            "access_terms": access_terms,
            "geo_names": self._part_texts(
                root.xpath("//archdesc/controlaccess//geogname"), sep=" -- "
            ),
            "digital_objects": self._parse_digital_objects(
                root.xpath("//archdesc/did/dao | //archdesc/did/daoset/dao")
            ),
            "has_online_content": len(root.xpath("//dao")) > 0
        }

        instance_url = first_of(root.xpath("//control/recordid/@instanceurl"))
        if instance_url:
            collection["instance_url"] = instance_url
        uri = aspace_uri(first_of(root.xpath("//archdesc/@altrender")))
        if uri:
            collection["uri"] = uri
        relations = self._parse_relations(root)
        if relations:
            collection["relations"] = relations
        return collection

    def _parse_components(self, component_nodes, parent_id):
        components = []
        for node in component_nodes:
            ref_id = node.get("id")
            if not ref_id:
                fallback = f"{parent_id}_{next(self._counter)}"
                ref_id = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:9]

            component_id = generate_id(ref_id, parent_id, self._counter)
            title = first_text(node.xpath("./did/unittitle"))
            dates = self._parse_dates(node, "./did/")
            normalized_date = format_normalized_date(dates)
            access_terms = self._parse_access_terms(node, "./")

            component = {
                "id": component_id,
                "ref_id": ref_id,
                "parent_id": parent_id,
                "level": self._parse_level(node),
                "title": title,
                "normalized_title": normalize_title(title, normalized_date),
                "dates": dates,
                "normalized_date": normalized_date,
                "unitid": first_text(node.xpath("./did/unitid")),
                "creators": self._parse_creators(node, "./did/"),
                "extent": self._parse_extent(node, "./did/"),
                "notes": self._parse_notes(node, "./"),
                "containers": self._parse_containers(node),
                "access_subjects": self._subject_texts(access_terms),
                "access_terms": access_terms,
                "digital_objects": self._parse_digital_objects(
                    node.xpath("./did/dao | ./did/daoset/dao")
                ),
                "has_online_content": len(node.xpath(".//dao")) > 0,
            }
            uri = aspace_uri(node.get("altrender"))
            if uri:
                component["uri"] = uri

            child_selector = "./c" + "".join(f"|./c{i:02d}" for i in range(1, 13))
            child_nodes = node.xpath(child_selector)
            if child_nodes:
                component["components"] = self._parse_components(
                    child_nodes, component_id
                )

            components.append(component)
        return components

    def _name_text(self, el, sep=", "):
        """
        Text of an EAD3 name or access element, joining <part> children —
        collapsing the raw text would run parts together because the parser
        strips inter-element whitespace. Names join with ', '; subject-style
        headings pass ' -- ' for their subdivisions.
        """
        parts = texts(el.xpath("./part"))
        if parts:
            return sep.join(parts)
        return collapse_text(el)

    def _part_texts(self, nodes, sep=", "):
        """
        Part-joined text of each element in an XPath result, empties dropped.
        """
        return [t for t in (self._name_text(n, sep) for n in nodes) if t]

    def _repository_text(self, repository_nodes):
        """
        Repository name: part-joined text of the first name element child,
        else the repository's joined prose.
        """
        if not repository_nodes:
            return None
        repository = repository_nodes[0]
        for name_el in self.NAME_ELEMENTS:
            names = repository.xpath(f"./{name_el}")
            if names:
                return self._name_text(names[0])
        return joined_text(repository)

    def _parse_language(self, root):
        """
        Languages of the material, from <language> descendants of
        <langmaterial> (covers <languageset> nesting).
        """
        return texts(root.xpath("//archdesc/did/langmaterial//language"))

    def _parse_dates(self, node, prefix):
        """
        Combine legacy <unitdate> values with <unitdatestructured> content.
        ArchivesSpace EAD3 exports emit both; display text is grouped by
        date type and machine values collect under 'normal'.
        """
        dates = {
            "inclusive": texts(node.xpath(f'{prefix}unitdate[@type="inclusive"]')),
            "bulk": texts(node.xpath(f'{prefix}unitdate[@type="bulk"]')),
            "other": texts(node.xpath(f'{prefix}unitdate[not(@type)]')),
            "normal": [str(v) for v in node.xpath(f'{prefix}unitdate/@normal')]
        }
        for uds in node.xpath(f"{prefix}unitdatestructured"):
            bucket = uds.get("unitdatetype")
            if bucket not in ("inclusive", "bulk"):
                bucket = "other"
            display, normals = self._structured_date(uds)
            if display:
                dates[bucket].append(display)
            dates["normal"].extend(normals)
        return dates

    def _structured_date(self, node):
        """
        Display string and machine values of a <unitdatestructured> (or
        nested <dateset>): <datesingle> text or <fromdate>-<todate> ranges,
        with @standarddate values joined '/' for ranges.
        """
        displays = []
        normals = []
        for child in node:
            if child.tag == "datesingle":
                display = collapse_text(child)
                if display:
                    displays.append(display)
                standard = child.get("standarddate")
                if standard:
                    normals.append(standard)
            elif child.tag == "daterange":
                from_node = child.find("fromdate")
                to_node = child.find("todate")
                display = "-".join(
                    t for t in (collapse_text(from_node), collapse_text(to_node)) if t
                )
                if display:
                    displays.append(display)
                standards = [
                    d.get("standarddate")
                    for d in (from_node, to_node)
                    if d is not None and d.get("standarddate")
                ]
                if standards:
                    normals.append("/".join(standards))
            elif child.tag == "dateset":
                display, nested_normals = self._structured_date(child)
                if display:
                    displays.append(display)
                normals.extend(nested_normals)
        return ", ".join(displays) if displays else None, normals

    def _parse_extent(self, node, prefix):
        """
        Combine legacy <physdesc>/<extent> with <physdescstructured>
        (directly in the <did> or grouped under <physdescset>), rendered
        as '<quantity> <unittype>'. A <physdesc> without <extent> children
        (the schema-preferred EAD3 form is plain prose) contributes its
        prose; <physfacet> and <dimensions> qualifiers are kept.
        """
        extents = []
        for pd in node.xpath(f"{prefix}physdesc"):
            extent_texts = texts(pd.xpath("./extent"))
            if extent_texts:
                extents.extend(extent_texts)
                extents.extend(texts(pd.xpath("./physfacet | ./dimensions")))
            else:
                joined = joined_text(pd)
                if joined:
                    extents.append(joined)
        extents.extend(self._structured_extents(node, prefix))
        return extents

    def _structured_extents(self, node, prefix):
        rendered = []
        for pds in node.xpath(
            f"{prefix}physdescstructured | {prefix}physdescset/physdescstructured"
        ):
            pieces = [
                first_text(pds.xpath("./quantity")),
                first_text(pds.xpath("./unittype")),
            ]
            text = " ".join(p for p in pieces if p)
            if text:
                rendered.append(text)
            rendered.extend(texts(pds.xpath("./dimensions | ./physfacet")))
        return rendered

    def _parse_physdesc(self, root):
        entries = []
        for pnode in root.xpath('//archdesc/did/physdesc'):
            joined = joined_text(pnode)
            if joined:
                entries.append(joined)
        entries.extend(self._structured_extents(root, "//archdesc/did/"))
        return entries

    def _parse_creators(self, node, prefix):
        """
        Collect <origination> name elements, keeping any authority
        attributes. An <origination> with no name-element children
        carries its creator as bare text.
        """
        creators = []
        for orig in node.xpath(f"{prefix}origination"):
            named = False
            for name_el in self.NAME_ELEMENTS:
                for el in orig.xpath(f"./{name_el}"):
                    name = self._name_text(el)
                    if name:
                        named = True
                        creator = {"type": name_el, "name": name}
                        add_authority(creator, el, self.AUTHORITY_ATTRS)
                        creators.append(creator)
            if not named:
                name = collapse_text(orig)
                if name:
                    creators.append({"type": "origination", "name": name})
        return creators

    def _parse_level(self, node):
        level = node.get("level")
        other_level = node.get("otherlevel")
        if level == "otherlevel" and other_level:
            return other_level
        return level

    def _parse_containers(self, node):
        """
        Collect all <container> info; EAD3 renamed @type to @localtype.
        """
        containers = []
        for c in node.xpath('./did/container'):
            container = {
                "type": c.get("localtype") or c.get("type"),
                "value": collapse_text(c)
            }
            if c.get("containerid"):
                container["containerid"] = c.get("containerid")
            if c.get("parent"):
                container["parent"] = c.get("parent")
            containers.append(container)
        return containers

    def _parse_notes(self, node, prefix):
        notes = {}
        for field in self.SEARCHABLE_NOTES_FIELDS:
            # EAD3 dropped the <descgrp> and <add> wrappers, but files
            # mechanically re-namespaced from EAD 2002 still contain them;
            # traversing them costs nothing on valid EAD3.
            content_nodes = node.xpath(
                f"{prefix}{field}"
                f" | {prefix}descgrp/{field}"
                f" | {prefix}descgrp/descgrp/{field}"
                f" | {prefix}add/{field}"
            )
            if content_nodes:
                notes[field] = [
                    {"heading": _note_heading(cnode), "content": note_content(cnode)}
                    for cnode in content_nodes
                ]

        for field, key in self.DID_NOTES_FIELDS.items():
            values = texts(node.xpath(f"{prefix}did/{field}"))
            if values:
                notes.setdefault(key, []).extend(values)
        return notes

    def _parse_access_terms(self, node, prefix):
        """
        Collect every access term under <controlaccess> — including terms
        inside nested <controlaccess> groups — as a dict of text, source
        element type, and any authority attributes present.
        """
        terms = []
        for canode in node.xpath(f"{prefix}controlaccess"):
            for selector in self.ACCESS_TERM_ELEMENTS:
                sep = ", " if selector in self.NAME_TERM_ELEMENTS else " -- "
                for el in canode.xpath(f".//{selector}"):
                    text = self._name_text(el, sep)
                    if not text:
                        continue
                    term = {"text": text, "type": selector}
                    add_authority(term, el, self.AUTHORITY_ATTRS)
                    terms.append(term)
        return terms

    def _subject_texts(self, terms):
        """
        The legacy access_subjects view of a term list: topical texts only.
        """
        return [t["text"] for t in terms if t["type"] in self.SUBJECT_ELEMENTS]

    def _parse_relations(self, root):
        """
        Collect <relations>/<relation> entries — EAD3's typed links from
        the described materials to related resources, agents, functions,
        and events — keeping the display text and linking attributes.
        """
        relations = []
        for rel in root.xpath("//archdesc/relations/relation"):
            entry = {}
            text = first_text(rel.xpath("./relationentry")) or collapse_text(rel)
            if text:
                entry["text"] = text
            for attr in ("relationtype", "href", "arcrole"):
                if rel.get(attr):
                    entry[attr] = rel.get(attr)
            if entry:
                relations.append(entry)
        return relations

    def _parse_digital_objects(self, dao_nodes):
        """
        Collect digital object references from <dao>, including those
        grouped in a <daoset>. EAD3 uses @linktitle for the display label
        and a <descriptivenote> for longer descriptions.
        """
        digital_objects = []
        for dao in dao_nodes:
            label = dao.get("linktitle")
            if not label:
                label = first_text(dao.xpath("./descriptivenote/p"))
            if not label:
                label = dao.get("title")

            href = dao.get("href")
            if not href:
                href = dao.get("{http://www.w3.org/1999/xlink}href")

            if href:
                digital_objects.append({"label": label, "href": href})

        return digital_objects


class EAD4Parser:
    """
    EXPERIMENTAL parser for draft EAD 4.0 documents
    (namespace https://standards.openpreservation.org/ead/v4).

    EAD 4.0 restructures the document model: camelCase element names,
    <identificationData> instead of <did>, <descriptionOfComponents>
    instead of <dsc>, <agents> instead of <origination>, and
    <subjectHeadings> instead of <controlaccess>. Digital objects have no
    <dao> equivalent; links are <reference href="..."> elements, which this
    parser reports as digital objects. There is no repository element, so
    'repository' is always None. The schema is unreleased and mappings may
    change before EAD 4.0.0 is final.
    """

    # Section notes: camelCase sources mapped onto the EAD 2002 output keys
    # so the notes dict looks the same regardless of input version.
    NOTES_FIELD_MAP = {
        "accessConditions": "accessrestrict",
        "accruals": "accruals",
        "appraisal": "appraisal",
        "arrangement": "arrangement",
        "biogHist": "bioghist",
        "custodHist": "custodhist",
        "filePlan": "fileplan",
        "otherDescriptiveInfo": "odd",
        "otherDescription": "odd",
        "preferCite": "prefercite",
        "processInfo": "processinfo",
        "publicationNote": "note",
        "relatedMaterial": "relatedmaterial",
        "scopeContent": "scopecontent",
        "separatedMaterial": "separatedmaterial",
        "sourceOfAcquisition": "acqinfo",
        "useConditions": "userestrict",
    }

    #: Authority-control attributes → normalized output keys (draft schema;
    #: EAD 4.0 has no @authfilenumber/@relator equivalents settled yet).
    AUTHORITY_ATTRS = (
        ("source", "source"),
        ("identifier", "identifier"),
    )

    def __init__(self):
        self._counter = itertools.count(1)

    def parse(self, root):
        """
        Parse a namespace-stripped document into the collection dict.
        """
        collection = self._parse_collection(root)
        component_nodes = root.xpath(
            "/ead/archDesc/descriptionOfComponents/c | "
            + " | ".join(
                f"/ead/archDesc/descriptionOfComponents/c{i:02d}"
                for i in range(1, 13)
            )
        )
        collection["components"] = self._parse_components(
            component_nodes, collection["id"]
        )
        return collection

    def _parse_collection(self, root):
        ead_id_node = root.xpath("//control/recordId")
        ead_id = (ead_id_node[0].text or "").strip() or None if ead_id_node else None

        arch_desc_nodes = root.xpath("/ead/archDesc")
        arch_desc = arch_desc_nodes[0] if arch_desc_nodes else root

        title = first_text(arch_desc.xpath("./identificationData/unitTitle"))
        dates = self._parse_dates(arch_desc, "./identificationData/")
        normalized_date = format_normalized_date(dates)
        extents = self._parse_extent(arch_desc, "./identificationData/")

        collection = {
            "id": ead_id,
            "level": "collection",
            "title": title,
            "normalized_title": normalize_title(title, normalized_date),
            "dates": dates,
            "normalized_date": normalized_date,
            "creators": self._parse_creators(arch_desc),
            "extent": extents,
            "language": self._parse_language(arch_desc),
            # EAD 4.0 has no free-text physdesc; reuse the rendered extents.
            "physdesc": list(extents),
            # EAD 4.0 has no repository element (maintenanceAgency describes
            # the record's maintainer, not the holding institution).
            "repository": None,
            "unitid": first_text(arch_desc.xpath("./identificationData/unitId")),
            "notes": self._parse_notes(arch_desc),
            "access_subjects": self._parse_access_subjects(arch_desc),
            "access_terms": self._parse_access_terms(arch_desc),
            "geo_names": texts(arch_desc.xpath("./places//placeName")),
            "digital_objects": self._parse_digital_objects(arch_desc),
            "has_online_content": len(root.xpath("//reference[@href]")) > 0,
        }
        return collection

    def _parse_components(self, component_nodes, parent_id):
        components = []
        for node in component_nodes:
            ref_id = node.get("id")
            if not ref_id:
                fallback = f"{parent_id}_{next(self._counter)}"
                ref_id = hashlib.md5(fallback.encode("utf-8")).hexdigest()[:9]

            component_id = generate_id(ref_id, parent_id, self._counter)
            title = first_text(node.xpath("./identificationData/unitTitle"))
            dates = self._parse_dates(node, "./identificationData/")
            normalized_date = format_normalized_date(dates)

            component = {
                "id": component_id,
                "ref_id": ref_id,
                "parent_id": parent_id,
                # EAD 4.0 dropped the otherlevel attribute; @level is free text.
                "level": node.get("level"),
                "title": title,
                "normalized_title": normalize_title(title, normalized_date),
                "dates": dates,
                "normalized_date": normalized_date,
                "unitid": first_text(node.xpath("./identificationData/unitId")),
                "creators": self._parse_creators(node),
                "extent": self._parse_extent(node, "./identificationData/"),
                "notes": self._parse_notes(node),
                "containers": self._parse_containers(node),
                "access_subjects": self._parse_access_subjects(node),
                "access_terms": self._parse_access_terms(node),
                "digital_objects": self._parse_digital_objects(node),
                "has_online_content": len(node.xpath(".//reference[@href]")) > 0,
            }

            child_selector = "./c" + "".join(f"|./c{i:02d}" for i in range(1, 13))
            child_nodes = node.xpath(child_selector)
            if child_nodes:
                component["components"] = self._parse_components(
                    child_nodes, component_id
                )

            components.append(component)
        return components

    def _parse_language(self, node):
        return texts(
            node.xpath("./identificationData/languageOfMaterial//language")
        )

    def _parse_dates(self, node, prefix):
        """
        Group <unitDate> display values by @unitDateType. Display text comes
        from <textualDate> when present, else from the structured <date>,
        <dateRange>, or <dateSet> content; machine values collect from
        @standardDate (falling back to @notBefore/@notAfter).
        """
        dates = {"inclusive": [], "bulk": [], "other": [], "normal": []}
        for unit_date in node.xpath(f"{prefix}unitDate"):
            bucket = unit_date.get("unitDateType")
            if bucket not in ("inclusive", "bulk"):
                bucket = "other"
            display, normals = self._date_content(unit_date)
            textual = first_text(unit_date.xpath("./textualDate"))
            if textual:
                display = textual
            if display:
                dates[bucket].append(display)
            dates["normal"].extend(normals)
        return dates

    def _date_content(self, node):
        """
        Display string and machine values from <date>, <dateRange>, and
        <dateSet> children.
        """
        displays = []
        normals = []
        for child in node:
            if child.tag == "date":
                display = collapse_text(child)
                if display:
                    displays.append(display)
                standard = self._standard_date(child)
                if standard:
                    normals.append(standard)
            elif child.tag == "dateRange":
                from_node = child.find("fromDate")
                to_node = child.find("toDate")
                display = "-".join(
                    t for t in (collapse_text(from_node), collapse_text(to_node)) if t
                )
                if display:
                    displays.append(display)
                standards = [
                    self._standard_date(d)
                    for d in (from_node, to_node)
                    if d is not None and self._standard_date(d)
                ]
                if standards:
                    normals.append("/".join(standards))
            elif child.tag == "dateSet":
                display, nested_normals = self._date_content(child)
                if display:
                    displays.append(display)
                normals.extend(nested_normals)
        return ", ".join(displays) if displays else None, normals

    def _standard_date(self, node):
        return (
            node.get("standardDate")
            or node.get("notBefore")
            or node.get("notAfter")
        )

    def _parse_extent(self, node, prefix):
        """
        Render each <extent> as '<quantity> <unitOfMeasurement>'.
        """
        extents = []
        for extent in node.xpath(f"{prefix}extent"):
            pieces = [
                first_text(extent.xpath("./quantity")),
                first_text(extent.xpath("./unitOfMeasurement")),
            ]
            text = " ".join(p for p in pieces if p)
            if text:
                extents.append(text)
        return extents

    def _parse_creators(self, node):
        """
        Collect <agents>/<agent> entries; the display name comes from the
        agent's <label> children and the type from @agentType.
        """
        creators = []
        for agent in node.xpath("./agents/agent"):
            name = ", ".join(texts(agent.xpath("./label")))
            if name:
                creator = {
                    "type": agent.get("agentType") or "name",
                    "name": name,
                }
                add_authority(creator, agent, self.AUTHORITY_ATTRS)
                creators.append(creator)
        return creators

    def _parse_containers(self, node):
        containers = []
        for c in node.xpath('./identificationData/container'):
            containers.append({
                "type": c.get("localType"),
                "value": collapse_text(c)
            })
        return containers

    def _parse_notes(self, node):
        """
        Map camelCase EAD 4.0 note elements onto the EAD 2002 output keys.
        <legalStatus> and the identificationData <descriptiveNote> stand in
        for the retired did-level note fields.
        """
        notes = {}
        for field, key in self.NOTES_FIELD_MAP.items():
            content_nodes = node.xpath(f"./{field}")
            if content_nodes:
                notes.setdefault(key, []).extend(
                    {"heading": _note_heading(cnode), "content": note_content(cnode)}
                    for cnode in content_nodes
                )

        did_fields = {
            "legalStatus": "legalstatus",
            "descriptiveNote": "note",
        }
        for field, key in did_fields.items():
            values = texts(node.xpath(f"./identificationData/{field}"))
            if values:
                notes.setdefault(key, []).extend(values)
        return notes

    def _parse_access_subjects(self, node):
        """
        Collect access terms from <subjectHeadings> (subject terms joined
        ' -- ' as heading facets), <functions>, and identificationData
        <genreForm> elements.
        """
        subjects = []
        for subject in node.xpath("./subjectHeadings/subject"):
            heading = " -- ".join(texts(subject.xpath("./term")))
            if heading:
                subjects.append(heading)
        for function in node.xpath("./functions/function"):
            label = first_text(function.xpath("./label"))
            if label:
                subjects.append(label)
        subjects.extend(texts(node.xpath("./identificationData/genreForm")))
        return subjects

    def _parse_access_terms(self, node):
        """
        The access_subjects sources plus <places>/<placeName>, as term
        dicts with any authority attributes present.
        """
        terms = []
        for subject in node.xpath("./subjectHeadings/subject"):
            heading = " -- ".join(texts(subject.xpath("./term")))
            if heading:
                term = {"text": heading, "type": "subject"}
                add_authority(term, subject, self.AUTHORITY_ATTRS)
                terms.append(term)
        for function in node.xpath("./functions/function"):
            label = first_text(function.xpath("./label"))
            if label:
                term = {"text": label, "type": "function"}
                add_authority(term, function, self.AUTHORITY_ATTRS)
                terms.append(term)
        for gf in node.xpath("./identificationData/genreForm"):
            text = collapse_text(gf)
            if text:
                term = {"text": text, "type": "genreform"}
                add_authority(term, gf, self.AUTHORITY_ATTRS)
                terms.append(term)
        for place in node.xpath("./places//placeName"):
            text = collapse_text(place)
            if text:
                term = {"text": text, "type": "geogname"}
                add_authority(term, place, self.AUTHORITY_ATTRS)
                terms.append(term)
        return terms

    def _parse_digital_objects(self, node):
        """
        Report <reference href="..."> links in this node's own description
        (not those belonging to nested components) as digital objects. This
        is a heuristic: EAD 4.0 has no dedicated digital-object element.
        """
        digital_objects = []
        for ref in node.iter("reference"):
            href = ref.get("href")
            if not href or not self._is_own_descendant(ref, node):
                continue
            digital_objects.append({"label": collapse_text(ref), "href": href})
        return digital_objects

    def _is_own_descendant(self, element, node):
        """
        True if no component element sits between element and node, so
        element belongs to node's own description rather than a child's.
        """
        ancestor = element.getparent()
        while ancestor is not None and ancestor is not node:
            if ancestor.tag in COMPONENT_TAGS:
                return False
            ancestor = ancestor.getparent()
        return ancestor is node


#: Version identifiers mapped to parser classes.
PARSERS = {
    "2002": EAD2002Parser,
    "ead3": EAD3Parser,
    "ead4": EAD4Parser,
}
