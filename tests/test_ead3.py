"""
EAD3-specific parsing tests: <control>/<recordid>, <part>-wrapped names,
structured dates and extents, <daoset>, <didnote>, and @localtype containers.
"""
from pathlib import Path

import pytest
import eadpy


def parse(xml_string):
    """Parse an XML string and return the collection data dict."""
    return eadpy.from_string(xml_string).data


def ead3_doc(did="", archdesc="", dsc="<dsc></dsc>"):
    """Build a minimal EAD3 document around the given fragments."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="http://ead3.archivists.org/schema/">
        <control><recordid>test-ead3-doc</recordid></control>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
                {did}
            </did>
            {archdesc}
            {dsc}
        </archdesc>
    </ead>"""


@pytest.fixture(scope="module")
def ead_instance():
    return eadpy.from_path(str(Path(__file__).parent / "sample_ead3.xml"))


class TestCollectionLevel:
    def test_version_and_record_id(self, ead_instance):
        assert ead_instance.ead_version == "ead3"
        assert ead_instance.data["id"] == "sample_ead3.xml"

    def test_title_and_structured_single_date(self, ead_instance):
        data = ead_instance.data
        assert data["title"] == "Sample Collection"
        assert data["normalized_date"] == "2023"
        assert data["normalized_title"] == "Sample Collection, 2023"
        assert data["dates"]["inclusive"] == ["2023"]
        assert data["dates"]["normal"] == ["2023"]

    def test_legacy_and_structured_extents_combine(self, ead_instance):
        assert ead_instance.data["extent"] == ["4 series", "42 items"]
        assert ead_instance.data["physdesc"] == ["4 series", "42 items"]

    def test_creator_parts_are_joined(self, ead_instance):
        assert ead_instance.data["creators"] == [
            {"type": "persname", "name": "Example, A., 1900-1980"}
        ]

    def test_repository(self, ead_instance):
        assert ead_instance.data["repository"] == "Sample University Archives"

    def test_language(self, ead_instance):
        assert ead_instance.data["language"] == ["English"]

    def test_subject_parts_join_as_heading(self, ead_instance):
        assert ead_instance.data["access_subjects"] == ["Photography -- History"]

    def test_geognames(self, ead_instance):
        assert ead_instance.data["geo_names"] == ["Chicago (Ill.)"]

    def test_scopecontent_note(self, ead_instance):
        note = ead_instance.data["notes"]["scopecontent"][0]
        assert note["heading"] == "Scope and Contents"
        assert note["content"] == ["Personal and professional papers of A. Example."]


class TestComponents:
    def test_structured_date_range(self, ead_instance):
        teenage = ead_instance.data["components"][0]["components"][0]
        assert teenage["title"] == "Teenage performances"
        assert teenage["normalized_date"] == "1950-1955"
        assert teenage["dates"]["normal"] == ["1950/1955"]

    def test_structured_extent(self, ead_instance):
        teenage = ead_instance.data["components"][0]["components"][0]
        assert teenage["extent"] == ["5 photographs"]

    def test_containers_use_localtype(self, ead_instance):
        letter = ead_instance.data["components"][0]["components"][1]["components"][0]
        assert letter["title"] == "Letter from C. Placeholder"
        assert letter["containers"] == [
            {"type": "box", "value": "1"},
            {"type": "folder", "value": "2"},
        ]

    def test_legacy_unitdate_normal_attribute(self, ead_instance):
        letter = ead_instance.data["components"][0]["components"][1]["components"][0]
        assert letter["dates"]["normal"] == ["1960-01-15"]

    def test_daoset_digital_objects(self, ead_instance):
        mother = ead_instance.data["components"][0]["components"][1][
            "components"][1]["components"][0]
        assert mother["title"] == "Letter from Mother"
        assert mother["digital_objects"] == [
            {"label": "Letter page 1", "href": "https://example.org/letters/mother-1.jpg"},
            {"label": "Letter page 2", "href": "https://example.org/letters/mother-2.jpg"},
        ]
        assert mother["has_online_content"] is True

    def test_didnote_maps_to_note(self, ead_instance):
        mother = ead_instance.data["components"][0]["components"][1][
            "components"][1]["components"][0]
        assert mother["notes"]["note"] == ["Digitized in 2020."]

    def test_online_content_propagates_to_ancestors(self, ead_instance):
        series1 = ead_instance.data["components"][0]
        assert series1["has_online_content"] is True
        assert ead_instance.data["has_online_content"] is True
        # A branch without daos stays offline
        assert ead_instance.data["components"][1]["has_online_content"] is False


class TestStructuredDates:
    def test_legacy_and_structured_dates_coexist(self):
        # ArchivesSpace EAD3 exports emit both forms side by side
        data = parse(ead3_doc(did="""
            <unitdate normal="1950/1960" type="inclusive">1950-1960</unitdate>
            <unitdatestructured unitdatetype="inclusive">
                <daterange>
                    <fromdate standarddate="1950">1950</fromdate>
                    <todate standarddate="1960">1960</todate>
                </daterange>
            </unitdatestructured>"""))
        assert data["dates"]["inclusive"] == ["1950-1960", "1950-1960"]
        assert data["dates"]["normal"] == ["1950/1960", "1950/1960"]

    def test_bulk_structured_date(self):
        data = parse(ead3_doc(did="""
            <unitdatestructured unitdatetype="bulk">
                <datesingle standarddate="1955">1955</datesingle>
            </unitdatestructured>"""))
        assert data["dates"]["bulk"] == ["1955"]
        assert data["normalized_date"] == "bulk 1955"

    def test_dateset_recursion(self):
        data = parse(ead3_doc(did="""
            <unitdatestructured>
                <dateset>
                    <datesingle standarddate="1940">1940</datesingle>
                    <daterange>
                        <fromdate standarddate="1950">1950</fromdate>
                        <todate standarddate="1960">1960</todate>
                    </daterange>
                </dateset>
            </unitdatestructured>"""))
        assert data["dates"]["other"] == ["1940, 1950-1960"]
        assert data["dates"]["normal"] == ["1940", "1950/1960"]

    def test_open_ended_range(self):
        data = parse(ead3_doc(did="""
            <unitdatestructured unitdatetype="inclusive">
                <daterange>
                    <fromdate standarddate="1990">1990</fromdate>
                </daterange>
            </unitdatestructured>"""))
        assert data["dates"]["inclusive"] == ["1990"]
        assert data["dates"]["normal"] == ["1990"]


class TestPartHandling:
    def test_multiple_creators_with_parts(self):
        data = parse(ead3_doc(did="""
            <origination>
                <corpname><part>Acme Corporation</part></corpname>
                <persname><part>Placeholder, C.</part><part>1920-1990</part></persname>
            </origination>"""))
        assert {"type": "corpname", "name": "Acme Corporation"} in data["creators"]
        assert {"type": "persname", "name": "Placeholder, C., 1920-1990"} in data["creators"]

    def test_partless_name_still_collapses(self):
        # Lenient handling for non-conformant documents without <part>
        data = parse(ead3_doc(did="""
            <origination><persname>Example, A.</persname></origination>"""))
        assert data["creators"] == [{"type": "persname", "name": "Example, A."}]


class TestPhysdescStructured:
    def test_physdescset_grouping(self):
        data = parse(ead3_doc(did="""
            <physdescset>
                <physdescstructured coverage="whole" physdescstructuredtype="carrier">
                    <quantity>10</quantity>
                    <unittype>boxes</unittype>
                </physdescstructured>
                <physdescstructured coverage="whole" physdescstructuredtype="spaceoccupied">
                    <quantity>12</quantity>
                    <unittype>linear feet</unittype>
                </physdescstructured>
            </physdescset>"""))
        assert data["extent"] == ["10 boxes", "12 linear feet"]


class TestEad3EdgeCases:
    def test_repository_without_name_element_falls_back_to_text(self):
        data = parse(ead3_doc(did="<repository>University Archives</repository>"))
        assert data["repository"] == "University Archives"

    def test_origination_without_name_element_uses_bare_text(self):
        data = parse(ead3_doc(did="<origination>Example, A.</origination>"))
        assert data["creators"] == [{"type": "origination", "name": "Example, A."}]

    def test_otherlevel_attribute(self):
        data = parse(ead3_doc(dsc="""<dsc>
            <c level="otherlevel" otherlevel="subseries" id="c1"><did>
                <unittitle>Correspondence</unittitle>
            </did></c></dsc>"""))
        assert data["components"][0]["level"] == "subseries"

    def test_container_parent_chain(self):
        data = parse(ead3_doc(dsc="""<dsc>
            <c level="file" id="c1"><did>
                <unittitle>Letters</unittitle>
                <container localtype="box" containerid="b2">2</container>
                <container localtype="folder" parent="b2">3</container>
            </did></c></dsc>"""))
        containers = data["components"][0]["containers"]
        assert containers[0] == {"type": "box", "value": "2", "containerid": "b2"}
        assert containers[1] == {"type": "folder", "value": "3", "parent": "b2"}

    def test_empty_access_terms_are_skipped(self):
        data = parse(ead3_doc(archdesc="""
            <controlaccess><subject/><subject><part>Real Subject</part></subject>
            </controlaccess>"""))
        assert [t["text"] for t in data["access_terms"]] == ["Real Subject"]

    def test_dao_title_and_xlink_href_fallbacks(self):
        data = parse(ead3_doc(did="""
            <dao xmlns:xlink="http://www.w3.org/1999/xlink"
                 title="Scanned diary" xlink:href="https://example.org/diary"/>"""))
        assert data["digital_objects"] == [
            {"label": "Scanned diary", "href": "https://example.org/diary"}
        ]


class TestInternalAudience:
    def test_internal_content_is_excluded_by_default(self):
        doc = ead3_doc(
            archdesc="<processinfo audience='internal'><p>Staff only.</p></processinfo>",
            dsc="""<dsc>
                <c level="file" id="c1"><did><unittitle>Public file</unittitle></did></c>
                <c level="file" id="c2" audience="internal">
                    <did><unittitle>Restricted file</unittitle>
                    <dao href="https://example.org/staff"/></did></c>
            </dsc>""")
        data = parse(doc)
        assert [c["title"] for c in data["components"]] == ["Public file"]
        assert "processinfo" not in data["notes"]
        assert data["has_online_content"] is False

        kept = eadpy.from_string(doc, include_internal=True).data
        assert len(kept["components"]) == 2
        assert kept["has_online_content"] is True

    def test_internal_control_section_is_never_dropped(self):
        xml = """<ead xmlns="http://ead3.archivists.org/schema/">
            <control audience="internal"><recordid>keep-me</recordid></control>
            <archdesc level="collection"><did><unittitle>T</unittitle></did></archdesc>
        </ead>"""
        assert parse(xml)["id"] == "keep-me"
