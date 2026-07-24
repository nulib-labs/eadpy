"""
EAD 4.0-specific parsing tests (EXPERIMENTAL — the schema is an unreleased
draft): <identificationData> instead of <did>, <descriptionOfComponents>
instead of <dsc>, <agents>, <subjectHeadings>, camelCase note elements
mapped onto the EAD 2002 output keys, and <reference href> digital objects.
"""
from pathlib import Path

import pytest
import eadpy


def parse(xml_string):
    """Parse an XML string and return the collection data dict."""
    return eadpy.from_string(xml_string).data


def ead4_doc(identification="", archdesc="", components=""):
    """Build a minimal EAD 4.0 document around the given fragments."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="https://standards.openpreservation.org/ead/v4">
        <control><recordId>test-ead4-doc</recordId></control>
        <archDesc level="collection">
            <identificationData>
                <unitTitle>Test Collection</unitTitle>
                {identification}
            </identificationData>
            {archdesc}
            <descriptionOfComponents>{components}</descriptionOfComponents>
        </archDesc>
    </ead>"""


@pytest.fixture(scope="module")
def ead_instance():
    return eadpy.from_path(str(Path(__file__).parent / "sample_ead4.xml"))


class TestCollectionLevel:
    def test_version_and_record_id(self, ead_instance):
        assert ead_instance.ead_version == "ead4"
        assert ead_instance.data["id"] == "sample_ead4.xml"

    def test_identification_data_fields(self, ead_instance):
        data = ead_instance.data
        assert data["title"] == "Sample Collection"
        assert data["unitid"] == "SAMPLE-001"
        assert data["normalized_date"] == "2023"
        assert data["normalized_title"] == "Sample Collection, 2023"
        assert data["dates"]["normal"] == ["2023"]

    def test_extent_quantity_and_unit(self, ead_instance):
        assert ead_instance.data["extent"] == ["42 items"]
        assert ead_instance.data["physdesc"] == ["42 items"]

    def test_agents_as_creators(self, ead_instance):
        assert ead_instance.data["creators"] == [
            {"type": "person", "name": "Example, A., 1900-1980"}
        ]

    def test_repository_is_none(self, ead_instance):
        # EAD 4.0 has no repository element
        assert ead_instance.data["repository"] is None

    def test_language(self, ead_instance):
        assert ead_instance.data["language"] == ["English"]

    def test_subject_terms_and_genreform(self, ead_instance):
        assert ead_instance.data["access_subjects"] == [
            "Photography -- History",
            "photographs",
        ]

    def test_places_as_geonames(self, ead_instance):
        assert ead_instance.data["geo_names"] == ["Chicago (Ill.)"]

    def test_camelcase_notes_map_to_2002_keys(self, ead_instance):
        notes = ead_instance.data["notes"]
        scope = notes["scopecontent"][0]
        assert scope["heading"] == "Scope and Contents"
        assert scope["content"] == ["Personal and professional papers of A. Example."]
        assert notes["accessrestrict"][0]["content"] == ["Open for research."]
        assert notes["legalstatus"] == ["Public records"]


class TestComponents:
    def test_date_range(self, ead_instance):
        teenage = ead_instance.data["components"][0]["components"][0]
        assert teenage["title"] == "Teenage performances"
        assert teenage["normalized_date"] == "1950-1955"
        assert teenage["dates"]["normal"] == ["1950/1955"]

    def test_extent(self, ead_instance):
        teenage = ead_instance.data["components"][0]["components"][0]
        assert teenage["extent"] == ["5 photographs"]

    def test_containers_use_localtype(self, ead_instance):
        letter = ead_instance.data["components"][0]["components"][1]["components"][0]
        assert letter["title"] == "Letter from C. Placeholder"
        assert letter["containers"] == [
            {"type": "box", "value": "1"},
            {"type": "folder", "value": "2"},
        ]

    def test_textual_date_preferred_for_display(self, ead_instance):
        mother = ead_instance.data["components"][0]["components"][1][
            "components"][1]["components"][0]
        assert mother["title"] == "Letter from Mother"
        assert mother["normalized_date"] == "May 1962"
        assert mother["dates"]["normal"] == ["1962-05-20"]

    def test_reference_href_as_digital_object(self, ead_instance):
        mother = ead_instance.data["components"][0]["components"][1][
            "components"][1]["components"][0]
        assert mother["digital_objects"] == [
            {"label": "Letter page 1", "href": "https://example.org/letters/mother-1.jpg"}
        ]
        assert mother["has_online_content"] is True

    def test_online_content_propagates_to_ancestors(self, ead_instance):
        series1 = ead_instance.data["components"][0]
        assert series1["has_online_content"] is True
        assert ead_instance.data["has_online_content"] is True
        assert ead_instance.data["components"][1]["has_online_content"] is False

    def test_references_stay_with_their_component(self, ead_instance):
        # The reference belongs to 'Letter from Mother', not its ancestors'
        # own digital_objects lists
        series1 = ead_instance.data["components"][0]
        assert series1["digital_objects"] == []
        assert ead_instance.data["digital_objects"] == []


class TestOutputSchema:
    def test_collection_keys_match_2002_output(self, ead_instance):
        ead2002 = eadpy.from_path(str(Path(__file__).parent / "sample.xml"))
        assert set(ead_instance.data.keys()) == set(ead2002.data.keys())

    def test_component_keys_match_2002_output(self, ead_instance):
        ead2002 = eadpy.from_path(str(Path(__file__).parent / "sample.xml"))
        component_ead4 = ead_instance.data["components"][0]
        component_2002 = ead2002.data["components"][0]
        assert set(component_ead4.keys()) == set(component_2002.keys())

    def test_chunks_and_csv_generate(self, ead_instance, tmp_path):
        chunks = ead_instance.create_item_chunks()
        assert len(chunks) == 17  # same tree as sample.xml
        csv_data = ead_instance.create_and_save_csv(str(tmp_path / "out.csv"))
        assert (tmp_path / "out.csv").exists()
        assert csv_data[0]["title"] == "Sample Collection"


class TestDates:
    def test_dateset_recursion(self):
        data = parse(ead4_doc(identification="""
            <unitDate>
                <dateSet>
                    <date standardDate="1940">1940</date>
                    <dateRange>
                        <fromDate standardDate="1950">1950</fromDate>
                        <toDate standardDate="1960">1960</toDate>
                    </dateRange>
                </dateSet>
            </unitDate>"""))
        assert data["dates"]["other"] == ["1940, 1950-1960"]
        assert data["dates"]["normal"] == ["1940", "1950/1960"]

    def test_not_before_fallback(self):
        data = parse(ead4_doc(identification="""
            <unitDate>
                <date notBefore="1900" notAfter="1910">circa 1905</date>
            </unitDate>"""))
        assert data["dates"]["other"] == ["circa 1905"]
        assert data["dates"]["normal"] == ["1900"]


class TestNotes:
    def test_both_odd_sources_merge(self):
        data = parse(ead4_doc(archdesc="""
            <otherDescriptiveInfo><p>First note.</p></otherDescriptiveInfo>
            <otherDescription><p>Second note.</p></otherDescription>"""))
        contents = [note["content"] for note in data["notes"]["odd"]]
        assert ["First note."] in contents
        assert ["Second note."] in contents

    def test_use_conditions_map_to_userestrict(self):
        data = parse(ead4_doc(archdesc="""
            <useConditions><p>No reproduction.</p></useConditions>"""))
        assert data["notes"]["userestrict"][0]["content"] == ["No reproduction."]


class TestFunctions:
    def test_function_labels_become_access_terms(self):
        data = parse(ead4_doc(archdesc="""
            <functions><function source="local"><label>Teaching</label></function>
            <function><label/></function></functions>"""))
        assert data["access_subjects"] == ["Teaching"]
        assert data["access_terms"] == [
            {"text": "Teaching", "type": "function", "source": "local"}
        ]


class TestInternalAudience:
    def test_internal_content_is_excluded_by_default(self):
        doc = ead4_doc(
            archdesc="<processInfo audience='internal'><p>Staff only.</p></processInfo>",
            components="""
                <c01 level="file" id="c1">
                    <identificationData><unitTitle>Public file</unitTitle></identificationData>
                </c01>
                <c01 level="file" id="c2" audience="internal">
                    <identificationData><unitTitle>Restricted file</unitTitle></identificationData>
                </c01>""")
        data = parse(doc)
        assert [c["title"] for c in data["components"]] == ["Public file"]
        assert "processinfo" not in data["notes"]
        assert len(eadpy.from_string(doc, include_internal=True).data["components"]) == 2
