"""
Regression tests for EAD 2002 parsing edge cases: mixed content, language
encoding, note structure, document detection, and hierarchy variants.
"""
import pytest
import eadpy
from eadpy import parsers


def parse(xml_string):
    """Parse an XML string and return the collection data dict."""
    return eadpy.from_string(xml_string).data


def ead_doc(did="", archdesc="", dsc="<dsc></dsc>"):
    """Build a minimal EAD 2002 document around the given fragments."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader><eadid>test-doc</eadid></eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
                {did}
            </did>
            {archdesc}
            {dsc}
        </archdesc>
    </ead>"""


class TestMixedContent:
    def test_collection_title_with_inline_elements(self):
        xml = """<ead><eadheader><eadid>t</eadid></eadheader>
        <archdesc level="collection"><did>
            <unittitle>Papers of <persname>A. Example</persname>, author</unittitle>
        </did><dsc/></archdesc></ead>"""
        assert parse(xml)["title"] == "Papers of A. Example, author"

    def test_component_title_with_inline_elements(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did>
                <unittitle>Letters to <title render="italic">The Times</title> editor</unittitle>
            </did></c01></dsc>"""))
        assert data["components"][0]["title"] == "Letters to The Times editor"

    def test_unitid_with_inline_elements(self):
        data = parse(ead_doc(did="<unitid>MSS <num>123</num></unitid>"))
        assert data["unitid"] == "MSS 123"

    def test_abstract_with_inline_elements(self):
        data = parse(ead_doc(
            did="<abstract>Papers of <persname>A. Example</persname> from Chicago.</abstract>"
        ))
        assert data["notes"]["abstract"] == ["Papers of A. Example from Chicago."]

    def test_creator_with_inline_elements(self):
        data = parse(ead_doc(
            did="<origination label='creator'><persname>Example, <emph>A.</emph></persname></origination>"
        ))
        assert data["creators"] == [{"type": "persname", "name": "Example, A."}]


class TestLanguage:
    def test_language_elements(self):
        data = parse(ead_doc(
            did="""<langmaterial>Materials in <language langcode="eng">English</language>
                   and <language langcode="fre">French</language>.</langmaterial>"""
        ))
        assert data["language"] == ["English", "French"]

    def test_langmaterial_prose_fallback(self):
        data = parse(ead_doc(did="<langmaterial>Collection is in English.</langmaterial>"))
        assert data["language"] == ["Collection is in English."]


class TestFromStringEncoding:
    def test_non_utf8_declaration_does_not_corrupt(self):
        xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <ead><eadheader><eadid>t</eadid></eadheader>
        <archdesc level="collection"><did>
            <unittitle>Café Ménière</unittitle>
        </did><dsc/></archdesc></ead>"""
        assert parse(xml)["title"] == "Café Ménière"


class TestNotes:
    def test_note_direct_text_is_kept(self):
        data = parse(ead_doc(
            archdesc="<scopecontent><head>Scope</head>Direct text, no p element.</scopecontent>"
        ))
        note = data["notes"]["scopecontent"][0]
        assert note["heading"] == "Scope"
        assert note["content"] == ["Direct text, no p element."]

    def test_note_paragraphs_are_separate_entries(self):
        data = parse(ead_doc(
            archdesc="<bioghist><head>Bio</head><p>First para.</p><p>Second para.</p></bioghist>"
        ))
        assert data["notes"]["bioghist"][0]["content"] == ["First para.", "Second para."]

    def test_comments_inside_notes_are_ignored(self):
        data = parse(ead_doc(
            archdesc="<scopecontent><!-- editorial comment --><p>Real text.</p></scopecontent>"
        ))
        assert data["notes"]["scopecontent"][0]["content"] == ["Real text."]

    def test_chronlist_values_do_not_run_together(self):
        data = parse(ead_doc(archdesc="""<bioghist><chronlist>
            <chronitem><date>1950</date><event>Moved to Chicago</event></chronitem>
            <chronitem><date>1955</date><event>Married</event></chronitem>
        </chronlist></bioghist>"""))
        assert data["notes"]["bioghist"][0]["content"] == [
            "1950 Moved to Chicago 1955 Married"
        ]

    def test_component_notes(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did><unittitle>Series</unittitle></did>
                <accessrestrict><p>Restricted until 2050.</p></accessrestrict>
            </c01></dsc>"""))
        note = data["components"][0]["notes"]["accessrestrict"][0]
        assert note["content"] == ["Restricted until 2050."]


class TestDocumentDetection:
    def test_ead2002_namespace_is_detected(self):
        ead = eadpy.from_string(ead_doc())
        assert ead.ead_version == "2002"
        assert ead.data["title"] == "Test Collection"

    def test_ead3_namespace_is_detected(self):
        ead3 = """<ead xmlns="http://ead3.archivists.org/schema/">
            <control><recordid>x</recordid></control>
            <archdesc level="collection"><did><unittitle>T</unittitle></did></archdesc>
        </ead>"""
        ead = eadpy.from_string(ead3)
        assert ead.ead_version == "ead3"
        assert ead.data["id"] == "x"
        assert ead.data["title"] == "T"

    def test_ead4_namespace_is_detected(self):
        ead4 = """<ead xmlns="https://standards.openpreservation.org/ead/v4">
            <control><recordId>x</recordId></control>
            <archDesc level="collection">
                <identificationData><unitTitle>T</unitTitle></identificationData>
            </archDesc>
        </ead>"""
        ead = eadpy.from_string(ead4)
        assert ead.ead_version == "ead4"
        assert ead.data["id"] == "x"
        assert ead.data["title"] == "T"

    def test_namespaceless_eadheader_is_ead2002(self):
        ead = eadpy.from_string(
            "<ead><eadheader><eadid>t</eadid></eadheader>"
            "<archdesc level='collection'><did/><dsc/></archdesc></ead>"
        )
        assert ead.ead_version == "2002"

    def test_namespaceless_control_is_ead3(self):
        ead = eadpy.from_string(
            "<ead><control><recordid>t</recordid></control>"
            "<archdesc level='collection'><did/></archdesc></ead>"
        )
        assert ead.ead_version == "ead3"
        assert ead.data["id"] == "t"

    def test_namespaceless_camelcase_archdesc_is_ead4(self):
        ead = eadpy.from_string(
            "<ead><control><recordId>t</recordId></control>"
            "<archDesc level='collection'><identificationData/></archDesc></ead>"
        )
        assert ead.ead_version == "ead4"
        assert ead.data["id"] == "t"

    def test_unknown_namespace_is_rejected(self):
        with pytest.raises(ValueError, match="namespace"):
            eadpy.from_string('<ead xmlns="urn:example:not-ead"></ead>')

    def test_unexpected_root_is_rejected(self):
        with pytest.raises(ValueError, match="root element"):
            eadpy.from_string("<mets></mets>")

    def test_namespaceless_ead_without_header_defaults_to_ead2002(self):
        # No namespace and no version-identifying child element: EAD 2002 is
        # the safe default, since it is by far the most common in the wild.
        ead = eadpy.from_string("""<ead>
            <archdesc level="collection"><did>
                <unittitle>Test Collection</unittitle>
            </did><dsc/></archdesc></ead>""")
        assert ead.ead_version == "2002"
        assert ead.data["title"] == "Test Collection"


class TestHierarchy:
    def test_nested_dsc_components_are_found(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="series" id="a"><did><unittitle>Outer</unittitle></did></c01>
            <dsc><c01 level="series" id="b"><did><unittitle>Inner</unittitle></did></c01></dsc>
        </dsc>"""))
        assert [c["title"] for c in data["components"]] == ["Outer", "Inner"]

    def test_unnumbered_c_elements(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c level="series" id="s1"><did><unittitle>S1</unittitle></did>
                <c level="item" id="i1"><did><unittitle>I1</unittitle></did></c>
            </c></dsc>"""))
        series = data["components"][0]
        assert series["title"] == "S1"
        assert series["components"][0]["title"] == "I1"

    def test_otherlevel_attribute(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="otherlevel" otherlevel="binder" id="b1">
                <did><unittitle>Binder 1</unittitle></did>
            </c01></dsc>"""))
        assert data["components"][0]["level"] == "binder"


class TestDidDetails:
    def test_containers(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did><unittitle>F</unittitle>
                <container type="box">1</container>
                <container type="folder">2</container>
            </did></c01></dsc>"""))
        assert data["components"][0]["containers"] == [
            {"type": "box", "value": "1"},
            {"type": "folder", "value": "2"},
        ]

    def test_dao_xlink_href_and_online_content_propagation(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="series" id="s1"><did><unittitle>S</unittitle></did>
                <c02 level="item" id="i1"><did><unittitle>I</unittitle>
                    <dao xmlns:xlink="http://www.w3.org/1999/xlink"
                         xlink:href="https://example.org/item" title="View item"/>
                </did></c02>
            </c01></dsc>"""))
        series = data["components"][0]
        item = series["components"][0]
        assert item["digital_objects"] == [
            {"label": "View item", "href": "https://example.org/item"}
        ]
        # dao presence propagates up to ancestors and the collection
        assert item["has_online_content"] is True
        assert series["has_online_content"] is True
        assert data["has_online_content"] is True

    def test_dao_label_from_daodesc(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="item" id="i1"><did><unittitle>I</unittitle>
                <dao href="https://example.org/x"><daodesc><p>Digitized view</p></daodesc></dao>
            </did></c01></dsc>"""))
        assert data["components"][0]["digital_objects"] == [
            {"label": "Digitized view", "href": "https://example.org/x"}
        ]


class TestDates:
    def test_bulk_date_formatting(self):
        data = parse(ead_doc(
            did="""<unitdate type="inclusive">1950-1960</unitdate>
                   <unitdate type="bulk">1955-1958</unitdate>"""
        ))
        assert data["normalized_date"] == "1950-1960, bulk 1955-1958"
        assert data["normalized_title"] == "Test Collection, 1950-1960, bulk 1955-1958"

    def test_normal_attribute_is_captured(self):
        data = parse(ead_doc(
            did='<unitdate type="inclusive" normal="1950/1960">1950-1960</unitdate>'
        ))
        assert data["dates"]["normal"] == ["1950/1960"]
        assert data["dates"]["inclusive"] == ["1950-1960"]


class TestEntityHandling:
    """External entities (common in institutional EAD boilerplate) parse with
    their references dropped, matching ArchivesSpace's importer; undeclared
    entities remain a hard error."""

    EXTERNAL_ENTITY_DOC = """<!DOCTYPE ead [
        <!ENTITY su_name SYSTEM "su_name.txt">
    ]>
    <ead>
        <eadheader><eadid>t</eadid>
            <filedesc><titlestmt><titleproper>T</titleproper></titlestmt>
            <publicationstmt><publisher>&su_name;</publisher></publicationstmt>
            </filedesc>
        </eadheader>
        <archdesc level="collection"><did>
            <unittitle>Papers of &su_name; Faculty</unittitle>
        </did><dsc/></archdesc>
    </ead>"""

    def test_declared_external_entity_parses(self):
        with pytest.warns(UserWarning, match="su_name"):
            data = parse(self.EXTERNAL_ENTITY_DOC)
        assert data["id"] == "t"

    def test_unresolved_entity_text_is_dropped(self):
        with pytest.warns(UserWarning):
            data = parse(self.EXTERNAL_ENTITY_DOC)
        # The reference is omitted entirely, never a literal '&su_name;'
        assert data["title"] == "Papers of Faculty"

    def test_undeclared_entity_raises_parse_error(self):
        xml = """<ead><eadheader><eadid>t</eadid></eadheader>
        <archdesc level="collection"><did>
            <unittitle>Sample &amp; Example &undeclared; Papers</unittitle>
        </did><dsc/></archdesc></ead>"""
        with pytest.raises(eadpy.EadParseError):
            parse(xml)

    def test_parse_error_is_a_value_error(self):
        # Backward compatibility: callers catching ValueError still work
        with pytest.raises(ValueError):
            parse("<notead></notead>")

    def test_bare_ead3_document_parses(self):
        # Formerly rejected; EAD3 is now detected and parsed.
        xml = "<ead><control><recordid>t</recordid></control></ead>"
        ead = eadpy.from_string(xml)
        assert ead.ead_version == "ead3"
        assert ead.data["id"] == "t"


class TestTextHelpers:
    def test_helpers_return_none_for_missing_nodes(self):
        # Callers pass optional nodes; both helpers guard against None.
        assert parsers.collapse_text(None) is None
        assert parsers.joined_text(None) is None


class TestControlAccess:
    def test_empty_access_terms_are_skipped(self):
        data = parse(ead_doc(archdesc="""
            <controlaccess><subject/><subject>  </subject>
            <subject>Real Subject</subject></controlaccess>"""))
        assert data["access_subjects"] == ["Real Subject"]
        assert [t["text"] for t in data["access_terms"]] == ["Real Subject"]


class TestWhitespaceNormalization:
    """Hand-edited finding aids hard-wrap prose with newlines and tabs;
    remove_blank_text only drops whitespace-only nodes, so the wrapping
    survives inside text and must be collapsed on extraction."""

    def test_repository_wrapping_is_collapsed(self):
        data = parse(ead_doc(did="<repository>University at Buffalo. University\n\t\t\t Archives</repository>"))
        assert data["repository"] == "University at Buffalo. University Archives"

    def test_extent_wrapping_is_collapsed(self):
        data = parse(ead_doc(did="""<physdesc>
            <extent>34\n\t\t  manuscript boxes (14.40 linear\n\t\t  feet)</extent>
        </physdesc>"""))
        assert data["extent"] == ["34 manuscript boxes (14.40 linear feet)"]

    def test_element_only_note_block_wrapping_is_collapsed(self):
        data = parse(ead_doc(archdesc="""<bioghist>
            <p><emph render="bold">Lyman received the\n\t\t\t adult services award</emph></p>
        </bioghist>"""))
        assert data["notes"]["bioghist"][0]["content"] == [
            "Lyman received the adult services award"
        ]

    def test_runs_of_spaces_in_note_blocks_are_collapsed(self):
        data = parse(ead_doc(archdesc="""<scopecontent>
            <p><emph>Series I:  Business Records, 1888-1947 </emph></p>
        </scopecontent>"""))
        assert data["notes"]["scopecontent"][0]["content"] == [
            "Series I: Business Records, 1888-1947"
        ]


class TestInternalAudience:
    """Content marked audience="internal" is staff-only description —
    unpublished ArchivesSpace records and internal-use links export this
    way — and is excluded unless the caller opts in."""

    INTERNAL_DOC = ead_doc(
        did="""<dao xmlns:xlink="http://www.w3.org/1999/xlink"
                    xlink:href="https://example.org/staff" audience="internal"/>""",
        archdesc="""<scopecontent><p>Public description.</p></scopecontent>
            <processinfo audience="internal"><p>Staff only.</p></processinfo>""",
        dsc="""<dsc>
            <c01 level="file" id="c1"><did><unittitle>Public file</unittitle></did></c01>
            <c01 level="file" id="c2" audience="internal">
                <did><unittitle>Donor correspondence</unittitle></did></c01>
        </dsc>""")

    def test_internal_component_is_excluded_by_default(self):
        data = parse(self.INTERNAL_DOC)
        assert [c["title"] for c in data["components"]] == ["Public file"]

    def test_internal_note_is_excluded_by_default(self):
        data = parse(self.INTERNAL_DOC)
        assert "scopecontent" in data["notes"]
        assert "processinfo" not in data["notes"]

    def test_internal_dao_is_excluded_by_default(self):
        data = parse(self.INTERNAL_DOC)
        assert data["digital_objects"] == []
        assert data["has_online_content"] is False

    def test_include_internal_keeps_everything(self):
        data = eadpy.from_string(self.INTERNAL_DOC, include_internal=True).data
        assert [c["title"] for c in data["components"]] == [
            "Public file", "Donor correspondence"
        ]
        assert data["notes"]["processinfo"][0]["content"] == ["Staff only."]
        assert data["has_online_content"] is True

    def test_internal_eadheader_is_never_dropped(self):
        # A common convention for the finding aid's own metadata; dropping it
        # would take the record identifier with it.
        xml = """<ead xmlns="urn:isbn:1-931666-22-9">
            <eadheader audience="internal"><eadid>keep-me</eadid></eadheader>
            <archdesc level="collection"><did>
                <unittitle>Test Collection</unittitle>
            </did><dsc/></archdesc></ead>"""
        assert parse(xml)["id"] == "keep-me"

    def test_removing_internal_inline_element_keeps_surrounding_text(self):
        data = parse(ead_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did><unittitle>Letters from
                <persname audience="internal">A donor</persname> and others</unittitle>
            </did></c01></dsc>"""))
        assert data["components"][0]["title"] == "Letters from and others"

    def test_wholly_internal_description_warns(self):
        # An empty record is a confusing result to get silently.
        xml = """<ead xmlns="urn:isbn:1-931666-22-9">
            <eadheader><eadid>t</eadid></eadheader>
            <archdesc level="collection" audience="internal">
                <did><unittitle>Staff-only collection</unittitle></did><dsc/>
            </archdesc></ead>"""
        with pytest.warns(UserWarning, match="archival description"):
            data = parse(xml)
        assert data["title"] is None
        assert eadpy.from_string(xml, include_internal=True).data["title"] == (
            "Staff-only collection"
        )
