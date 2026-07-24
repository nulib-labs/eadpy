"""
Regression tests for content-loss fixes found by auditing real-world
finding aids (Bentley legacy EAD 2002, Princeton/NCSU EAD3, ArchivesSpace
EAD3 exports): descgrp/add note wrappers, nested controlaccess, container
@label, bare origination, physdesc prose, and authority/identifier capture.
"""
import eadpy


def parse(xml_string):
    """Parse an XML string and return the collection data dict."""
    return eadpy.from_string(xml_string).data


def ead2002_doc(did="", archdesc="", dsc="<dsc></dsc>"):
    """Build a minimal EAD 2002 document around the given fragments."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader><eadid>test-2002</eadid></eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
                {did}
            </did>
            {archdesc}
            {dsc}
        </archdesc>
    </ead>"""


def ead3_doc(did="", archdesc="", dsc="<dsc></dsc>", archdesc_attrs="",
             recordid_attrs=""):
    """Build a minimal EAD3 document around the given fragments."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="http://ead3.archivists.org/schema/">
        <control><recordid {recordid_attrs}>test-ead3</recordid></control>
        <archdesc level="collection" {archdesc_attrs}>
            <did>
                <unittitle>Test Collection</unittitle>
                {did}
            </did>
            {archdesc}
            {dsc}
        </archdesc>
    </ead>"""


class TestEad2002NoteWrappers:
    def test_acqinfo_is_captured(self):
        data = parse(ead2002_doc(
            archdesc="<acqinfo><p>Gift of the donor, 1971.</p></acqinfo>"
        ))
        assert data["notes"]["acqinfo"][0]["content"] == ["Gift of the donor, 1971."]

    def test_notes_inside_descgrp(self):
        data = parse(ead2002_doc(archdesc="""
            <descgrp type="admin">
                <acqinfo><p>Received in August 2002.</p></acqinfo>
                <processinfo><p>Processed by staff.</p></processinfo>
            </descgrp>"""))
        assert data["notes"]["acqinfo"][0]["content"] == ["Received in August 2002."]
        assert data["notes"]["processinfo"][0]["content"] == ["Processed by staff."]

    def test_notes_inside_nested_descgrp(self):
        data = parse(ead2002_doc(archdesc="""
            <descgrp><descgrp>
                <custodhist><p>Held by the family.</p></custodhist>
            </descgrp></descgrp>"""))
        assert data["notes"]["custodhist"][0]["content"] == ["Held by the family."]

    def test_notes_inside_add(self):
        data = parse(ead2002_doc(archdesc="""
            <add>
                <bibliography><head>Sources</head>
                    <bibref>Sample, A History.</bibref>
                </bibliography>
            </add>"""))
        assert data["notes"]["bibliography"][0]["content"] == ["Sample, A History."]

    def test_component_notes_inside_descgrp(self):
        data = parse(ead2002_doc(dsc="""<dsc>
            <c01 level="series" id="s1">
                <did><unittitle>Series 1</unittitle></did>
                <descgrp><acqinfo><p>Series gift.</p></acqinfo></descgrp>
            </c01></dsc>"""))
        notes = data["components"][0]["notes"]
        assert notes["acqinfo"][0]["content"] == ["Series gift."]


class TestEad2002AccessTerms:
    def test_geognames_inside_nested_controlaccess(self):
        data = parse(ead2002_doc(archdesc="""
            <controlaccess><head>Access Terms</head>
                <controlaccess><head>Subjects:</head>
                    <geogname source="lcsh">Ann Arbor (Mich.)--History.</geogname>
                    <subject source="lcsh">Commerce.</subject>
                </controlaccess>
            </controlaccess>"""))
        assert data["geo_names"] == ["Ann Arbor (Mich.)--History."]
        assert data["access_subjects"] == ["Commerce."]

    def test_name_access_points_become_terms(self):
        data = parse(ead2002_doc(archdesc="""
            <controlaccess>
                <corpname source="lcnaf" authfilenumber="http://id.loc.gov/authorities/names/n80030709">
                    Ann Arbor Chamber of Commerce.</corpname>
                <persname role="subject">Example, A.</persname>
            </controlaccess>"""))
        terms = data["access_terms"]
        corp = next(t for t in terms if t["type"] == "corpname")
        assert corp["text"] == "Ann Arbor Chamber of Commerce."
        assert corp["source"] == "lcnaf"
        assert corp["identifier"] == "http://id.loc.gov/authorities/names/n80030709"
        pers = next(t for t in terms if t["type"] == "persname")
        assert pers["relator"] == "subject"
        # Names are access terms but not part of the legacy subject strings.
        assert data["access_subjects"] == []

    def test_subject_authority_attributes(self):
        data = parse(ead2002_doc(archdesc="""
            <controlaccess>
                <subject source="lcsh">Photography.</subject>
                <genreform source="aat">Correspondence.</genreform>
            </controlaccess>"""))
        assert data["access_subjects"] == ["Photography.", "Correspondence."]
        assert {"text": "Photography.", "type": "subject", "source": "lcsh"} \
            in data["access_terms"]


class TestEad2002DidFields:
    def test_container_label_fallback(self):
        data = parse(ead2002_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did>
                <unittitle>Correspondence</unittitle>
                <container label="Box">1</container>
            </did></c01></dsc>"""))
        assert data["components"][0]["containers"] == [
            {"type": "Box", "value": "1"}
        ]

    def test_aspace_unitid_becomes_uri_not_unitid(self):
        data = parse(ead2002_doc(
            did="""<unitid>MSS 826</unitid>
                   <unitid type="aspace_uri">/repositories/3/resources/826</unitid>""",
            dsc="""<dsc><c01 level="file" id="c1"><did>
                <unittitle>File 1</unittitle>
                <unitid type="aspace_uri">/repositories/3/archival_objects/9</unitid>
            </did></c01></dsc>"""
        ))
        assert data["unitid"] == "MSS 826"
        assert data["uri"] == "/repositories/3/resources/826"
        component = data["components"][0]
        assert component["unitid"] is None
        assert component["uri"] == "/repositories/3/archival_objects/9"

    def test_container_id_and_parent_chain(self):
        data = parse(ead2002_doc(dsc="""<dsc>
            <c01 level="file" id="c1"><did>
                <unittitle>Correspondence</unittitle>
                <container id="aspace_box2" label="Text" type="box">2</container>
                <container parent="aspace_box2" type="folder">3</container>
            </did></c01></dsc>"""))
        assert data["components"][0]["containers"] == [
            {"type": "box", "value": "2", "containerid": "aspace_box2"},
            {"type": "folder", "value": "3", "parent": "aspace_box2"},
        ]

    def test_bare_origination_text(self):
        data = parse(ead2002_doc(
            did="<origination label='creator'>The University Settlement Project</origination>"
        ))
        assert data["creators"] == [
            {"type": "origination", "name": "The University Settlement Project"}
        ]

    def test_creator_authority_attributes(self):
        data = parse(ead2002_doc(did="""
            <origination label="creator">
                <corpname source="lcnaf" authfilenumber="n79021846">University of Michigan</corpname>
            </origination>"""))
        assert data["creators"] == [{
            "type": "corpname",
            "name": "University of Michigan",
            "source": "lcnaf",
            "identifier": "n79021846",
        }]

    def test_physdesc_prose_fallback(self):
        data = parse(ead2002_doc(dsc="""<dsc>
            <c01 level="item" id="c1"><did>
                <unittitle>Photograph</unittitle>
                <physdesc>1 oversize print</physdesc>
            </did></c01></dsc>"""))
        assert data["components"][0]["extent"] == ["1 oversize print"]

    def test_physfacet_and_dimensions_kept(self):
        data = parse(ead2002_doc(
            did="""<physdesc><extent>2 boxes</extent>
                   <physfacet>gelatin silver prints</physfacet>
                   <dimensions>20 x 25 cm</dimensions></physdesc>"""
        ))
        assert data["extent"] == ["2 boxes", "gelatin silver prints", "20 x 25 cm"]


class TestEad3Completeness:
    def test_acqinfo_is_captured(self):
        data = parse(ead3_doc(
            archdesc="<acqinfo><p>Purchased, 2010.</p></acqinfo>"
        ))
        assert data["notes"]["acqinfo"][0]["content"] == ["Purchased, 2010."]

    def test_creator_identifier_and_relator(self):
        data = parse(ead3_doc(did="""
            <origination label="creator">
                <persname identifier="http://viaf.org/viaf/46888277" source="viaf" relator="col">
                    <part>Brown, Clarence</part>
                </persname>
            </origination>"""))
        assert data["creators"] == [{
            "type": "persname",
            "name": "Brown, Clarence",
            "source": "viaf",
            "identifier": "http://viaf.org/viaf/46888277",
            "relator": "col",
        }]

    def test_subject_identifier_in_access_terms(self):
        data = parse(ead3_doc(archdesc="""
            <controlaccess>
                <subject source="lcsh" identifier="http://id.loc.gov/authorities/subjects/sh85116010">
                    <part>Poets, Russian</part><part>20th century</part>
                </subject>
                <persname source="viaf"><part>Mandelstam, Osip</part></persname>
            </controlaccess>"""))
        subject = next(t for t in data["access_terms"] if t["type"] == "subject")
        assert subject["text"] == "Poets, Russian -- 20th century"
        assert subject["identifier"] == "http://id.loc.gov/authorities/subjects/sh85116010"
        pers = next(t for t in data["access_terms"] if t["type"] == "persname")
        assert pers["text"] == "Mandelstam, Osip"
        assert data["access_subjects"] == ["Poets, Russian -- 20th century"]

    def test_geognames_inside_nested_controlaccess(self):
        data = parse(ead3_doc(archdesc="""
            <controlaccess><controlaccess>
                <geogname source="lcsh"><part>Chicago (Ill.)</part></geogname>
            </controlaccess></controlaccess>"""))
        assert data["geo_names"] == ["Chicago (Ill.)"]

    def test_relations(self):
        data = parse(ead3_doc(archdesc="""
            <relations>
                <relation relationtype="resourcerelation" arcrole="translatorOf"
                          href="http://arks.example.org/ark:/1234">
                    <relationentry>Related Papers (C0539)</relationentry>
                </relation>
            </relations>"""))
        assert data["relations"] == [{
            "text": "Related Papers (C0539)",
            "relationtype": "resourcerelation",
            "href": "http://arks.example.org/ark:/1234",
            "arcrole": "translatorOf",
        }]

    def test_instance_url_and_aspace_uris(self):
        data = parse(ead3_doc(
            recordid_attrs='instanceurl="https://hdl.handle.net/10079/fa/test"',
            archdesc_attrs='altrender="/repositories/15/resources/11101"',
            dsc="""<dsc>
                <c id="c1" level="file" altrender="/repositories/15/archival_objects/1">
                    <did><unittitle>File 1</unittitle></did>
                </c></dsc>"""
        ))
        assert data["instance_url"] == "https://hdl.handle.net/10079/fa/test"
        assert data["uri"] == "/repositories/15/resources/11101"
        assert data["components"][0]["uri"] == "/repositories/15/archival_objects/1"

    def test_presentational_altrender_is_not_a_uri(self):
        data = parse(ead3_doc(dsc="""<dsc>
            <c id="c1" level="file" altrender="bold">
                <did><unittitle>File 1</unittitle></did>
            </c></dsc>"""))
        assert "uri" not in data["components"][0]

    def test_physdesc_prose_fallback(self):
        data = parse(ead3_doc(dsc="""<dsc>
            <c id="c1" level="item">
                <did><unittitle>Thing</unittitle><physdesc>1 thing</physdesc></did>
            </c></dsc>"""))
        assert data["components"][0]["extent"] == ["1 thing"]

    def test_physdescstructured_dimensions(self):
        data = parse(ead3_doc(did="""
            <physdescstructured physdescstructuredtype="spaceoccupied" coverage="whole">
                <quantity>1</quantity><unittype>folder</unittype>
                <dimensions>12x40</dimensions>
            </physdescstructured>"""))
        assert data["extent"] == ["1 folder", "12x40"]

    def test_containerid_captured(self):
        data = parse(ead3_doc(dsc="""<dsc>
            <c id="c1" level="file"><did>
                <unittitle>File 1</unittitle>
                <container localtype="folder" containerid="C1571_i1-f1">1</container>
            </did></c></dsc>"""))
        assert data["components"][0]["containers"] == [
            {"type": "folder", "value": "1", "containerid": "C1571_i1-f1"}
        ]
