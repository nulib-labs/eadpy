"""
Regression tests for EAD 2002 parsing edge cases: mixed content, language
encoding, note structure, document detection, and hierarchy variants.
"""
import pytest
import eadpy


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
            <unittitle>Papers of <persname>Jane Doe</persname>, author</unittitle>
        </did><dsc/></archdesc></ead>"""
        assert parse(xml)["title"] == "Papers of Jane Doe, author"

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
            did="<abstract>Papers of <persname>Jane Doe</persname> from Chicago.</abstract>"
        ))
        assert data["notes"]["abstract"] == ["Papers of Jane Doe from Chicago."]

    def test_creator_with_inline_elements(self):
        data = parse(ead_doc(
            did="<origination label='creator'><persname>Doe, <emph>Jane</emph></persname></origination>"
        ))
        assert data["creators"] == [{"type": "persname", "name": "Doe, Jane"}]


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
    def test_ead3_is_rejected(self):
        ead3 = """<ead xmlns="http://ead3.archivists.org/schema/">
            <control><recordid>x</recordid></control>
            <archdesc level="collection"><did><unittitle>T</unittitle></did></archdesc>
        </ead>"""
        with pytest.raises(ValueError, match="EAD3"):
            eadpy.from_string(ead3)

    def test_unexpected_root_is_rejected(self):
        with pytest.raises(ValueError, match="root element"):
            eadpy.from_string("<mets></mets>")


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
            <unittitle>Smith &amp; Jones &undeclared; Papers</unittitle>
        </did><dsc/></archdesc></ead>"""
        with pytest.raises(eadpy.EadParseError):
            parse(xml)

    def test_parse_error_is_a_value_error(self):
        # Backward compatibility: callers catching ValueError still work
        with pytest.raises(ValueError):
            parse("<notead></notead>")

    def test_ead3_document_raises_parse_error(self):
        xml = "<ead><control><recordid>t</recordid></control></ead>"
        with pytest.raises(eadpy.EadParseError, match="EAD3"):
            parse(xml)
