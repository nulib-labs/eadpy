import io
import os
import warnings
import json
import csv
import tempfile
from pathlib import Path
import pytest
from lxml import etree
from eadpy.ead import EAD
import eadpy  # Import the package for testing package-level functions

@pytest.fixture
def sample_xml_path():
    return str(Path(__file__).parent / "sample.xml")

@pytest.fixture
def ead_instance(sample_xml_path):
    # Use the new from_path class method instead of the constructor
    return EAD.from_path(sample_xml_path)

@pytest.fixture
def empty_xml():
    """Create minimal valid EAD XML for testing edge cases"""
    minimal_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test123</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
    temp_file.write(minimal_xml.encode('utf-8'))
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    os.unlink(temp_file.name)

# Test the new package-level API functions
def test_package_level_from_path(sample_xml_path):
    """Test the package-level from_path function"""
    ead = eadpy.from_path(sample_xml_path)
    assert ead is not None
    assert isinstance(ead, EAD)
    assert ead.data is not None
    assert "level" in ead.data
    assert ead.data["level"] == "collection"

def test_package_level_from_string():
    """Test the package-level from_string function"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test123</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    ead = eadpy.from_string(xml_string)
    assert ead is not None
    assert isinstance(ead, EAD)
    assert ead.data["id"] == "test123"
    assert ead.data["title"] == "Test Collection"

def test_package_level_from_bytes():
    """Test the package-level from_bytes function"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test456</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Bytes Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    xml_bytes = xml_string.encode('utf-8')
    ead = eadpy.from_bytes(xml_bytes)
    assert ead is not None
    assert isinstance(ead, EAD)
    assert ead.data["id"] == "test456"
    assert ead.data["title"] == "Bytes Test Collection"

def test_package_level_from_file():
    """Test the package-level from_file function"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test789</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>File Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    file_like = io.StringIO(xml_string)
    ead = eadpy.from_file(file_like)
    assert ead is not None
    assert isinstance(ead, EAD)
    assert ead.data["id"] == "test789"
    assert ead.data["title"] == "File Test Collection"

def test_initialization_and_parsing(ead_instance):
    """Test that EAD object initializes and parses correctly"""
    assert ead_instance is not None
    # Check that the instance has data
    assert ead_instance.data is not None
    assert isinstance(ead_instance.data, dict)
    assert "level" in ead_instance.data
    assert ead_instance.data["level"] == "collection"

def test_parse_empty_xml(empty_xml):
    """Test parsing an empty but valid EAD XML file"""
    ead = EAD.from_path(empty_xml)
    assert ead.data["id"] == "test123"
    assert ead.data["title"] == "Test Collection"
    assert ead.data["level"] == "collection"
    assert "components" in ead.data
    assert isinstance(ead.data["components"], list)
    assert len(ead.data["components"]) == 0

def test_generate_id(ead_instance):
    """Test the ID generation method"""
    # Test with existing reference_id
    ref_id = "ref123"
    parent_id = "parent456"
    generated_id = ead_instance._generate_id(ref_id, parent_id)
    assert generated_id == "parent456_ref123"
    
    # Test without parent_id
    generated_id = ead_instance._generate_id(ref_id)
    assert generated_id == "ref123"
    
    # Test with None reference_id (should generate MD5 hash)
    generated_id = ead_instance._generate_id(None, parent_id)
    assert generated_id.startswith(f"{parent_id}_")
    assert len(generated_id) > len(parent_id) + 1  # Ensure hash is generated

def test_normalize_title(ead_instance):
    """Test title normalization method"""
    title = "Test Collection"
    date_str = "1950-1960"
    normalized = ead_instance._normalize_title(title, date_str)
    assert normalized == "Test Collection, 1950-1960"
    
    # Test with missing date
    normalized = ead_instance._normalize_title(title, None)
    assert normalized == title
    
    # Test with missing title
    normalized = ead_instance._normalize_title(None, date_str)
    assert normalized is None

def test_parse_collection(ead_instance):
    """Test that collection metadata is parsed correctly"""
    collection = ead_instance.data
    assert collection["id"] == "sample.xml"
    assert collection["title"] == "Sample Collection"
    assert collection["level"] == "collection"
    assert collection["unitid"] == "SAMPLE-001"
    assert collection["extent"] == ["4 series, 42 items"]
    assert collection["normalized_date"] == "2023"
    assert collection["normalized_title"] == "Sample Collection, 2023"
    assert "creators" in collection
    assert "notes" in collection

def test_parse_components(ead_instance):
    """Test that components are parsed correctly"""
    assert isinstance(ead_instance.data["components"], list)
    assert len(ead_instance.data["components"]) == 4

    component = ead_instance.data["components"][0]
    assert component["title"] == "Series 1: Personal Papers"
    assert component["level"] == "file"
    assert "id" in component
    assert component["parent_id"] == ead_instance.data["id"]

def test_create_item_chunks(ead_instance):
    """Test creation of item chunks"""
    chunks = ead_instance.create_item_chunks()
    assert isinstance(chunks, list)
    # sample.xml contains 17 item/leaf components
    assert len(chunks) == 17

    chunk = chunks[0]
    assert "text" in chunk
    assert "metadata" in chunk
    assert chunk["metadata"]["title"] == "Teenage performances"
    assert chunk["metadata"]["level"] == "item"
    assert chunk["metadata"]["path"].startswith(
        "Sample Collection > Series 1: Personal Papers"
    )
    assert "id" in chunk["metadata"]

def test_save_chunks_to_json(ead_instance):
    """Test saving chunks to a JSON file"""
    chunks = [{"text": "Test chunk", "metadata": {"id": "test123", "title": "Test"}}]
    
    # Create temp file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        output_path = temp_file.name
    
    # Save chunks to file
    ead_instance.save_chunks_to_json(chunks, output_path)
    
    # Verify file exists and contains correct data
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        loaded_chunks = json.load(f)
        assert loaded_chunks == chunks
    
    # Clean up
    os.unlink(output_path)

def test_create_and_save_chunks(ead_instance):
    """Test the combined create and save functionality"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        output_path = temp_file.name
    
    # Create and save chunks
    created_chunks = ead_instance.create_and_save_chunks(output_path)
    
    # Verify file exists and contains chunks
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        loaded_chunks = json.load(f)
        assert loaded_chunks == created_chunks
    
    # Clean up
    os.unlink(output_path)

def test_parse_notes(ead_instance):
    """Test parsing of notes fields"""
    # Test for collection notes
    assert "notes" in ead_instance.data
    notes = ead_instance.data["notes"]
    
    # Check for valid structure in at least one note type if present
    if notes:
        for note_type, note_content in notes.items():
            if isinstance(note_content, list) and len(note_content) > 0:
                if isinstance(note_content[0], dict):
                    assert "heading" in note_content[0] or "content" in note_content[0]
                else:
                    assert isinstance(note_content[0], str)

def test_parse_digital_objects(ead_instance):
    """Test parsing of digital objects"""
    # Check that digital_objects field exists in collection
    assert "digital_objects" in ead_instance.data
    
    # Test structure of digital objects if any are present
    digital_objects = ead_instance.data["digital_objects"]
    for obj in digital_objects:
        assert "href" in obj

def test_nonexistent_file():
    """Test error handling when file doesn't exist"""
    with pytest.raises(FileNotFoundError) as excinfo:
        EAD.from_path("nonexistent_file.xml")
    assert "EAD file not found" in str(excinfo.value)
    assert "nonexistent_file.xml" in str(excinfo.value)

def test_directory_as_file():
    """Test error handling when a directory is provided instead of a file"""
    with pytest.raises(IsADirectoryError) as excinfo:
        EAD.from_path(str(Path(__file__).parent))
    assert "is a directory, not a file" in str(excinfo.value)

def test_file_permission_error(monkeypatch):
    """Test error handling when file doesn't have read permissions"""

    # Mock the specific methods:
    def mock_access(path, mode):
        # Always return False to simulate "no read permission"
        return False

    def mock_exists(path):
        # Return True so that the code doesn't think the file is missing
        return True

    def mock_isfile(path):
        # Return True so that the code doesn't think it's a directory
        return True

    # Apply partial patches rather than replacing os.path entirely
    monkeypatch.setattr(os, "access", mock_access)
    monkeypatch.setattr(os.path, "exists", mock_exists)
    monkeypatch.setattr(os.path, "isfile", mock_isfile)

    # Now try constructing an EAD instance
    with pytest.raises(PermissionError) as excinfo:
        EAD.from_path("fake_permission_error.xml")  # The code should raise PermissionError
    assert "Permission denied" in str(excinfo.value)

def test_invalid_xml_content():
    """Test error handling for invalid XML content"""
    # Create temp file with invalid XML
    invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ead>
        <unclosed_tag>
    </ead>"""
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
    temp_file.write(invalid_xml.encode('utf-8'))
    temp_file.close()
    
    try:
        with pytest.raises(ValueError) as excinfo:
            EAD.from_path(temp_file.name)
        assert "Invalid XML" in str(excinfo.value)
    finally:
        # Clean up
        os.unlink(temp_file.name)

def test_from_string():
    """Test creating an EAD instance from a string"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test123</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    ead = EAD.from_string(xml_string)
    assert ead.data["id"] == "test123"
    assert ead.data["title"] == "Test Collection"
    assert ead.data["level"] == "collection"

def test_from_bytes():
    """Test creating an EAD instance from bytes"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test123</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    xml_bytes = xml_string.encode('utf-8')
    ead = EAD.from_bytes(xml_bytes)
    assert ead.data["id"] == "test123"
    assert ead.data["title"] == "Test Collection"
    assert ead.data["level"] == "collection"

def test_from_file():
    """Test creating an EAD instance from a file-like object"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test123</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    file_like = io.StringIO(xml_string)
    ead = EAD.from_file(file_like)
    assert ead.data["id"] == "test123"
    assert ead.data["title"] == "Test Collection"
    assert ead.data["level"] == "collection"

def test_from_file_bytesio():
    """Test creating an EAD instance from a BytesIO file-like object"""
    xml_string = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader>
            <eadid>test456</eadid>
        </eadheader>
        <archdesc level="collection">
            <did>
                <unittitle>BytesIO Test Collection</unittitle>
            </did>
            <dsc></dsc>
        </archdesc>
    </ead>"""
    
    # Create a BytesIO object
    file_like = io.BytesIO(xml_string.encode('utf-8'))
    ead = EAD.from_file(file_like)
    assert ead.data["id"] == "test456"
    assert ead.data["title"] == "BytesIO Test Collection"
    assert ead.data["level"] == "collection"

def test_from_file_empty():
    """Test error handling when file-like object is empty"""
    empty_file = io.StringIO("")
    
    with pytest.raises(ValueError) as excinfo:
        EAD.from_file(empty_file)
    assert "Invalid XML" in str(excinfo.value)

def test_from_file_invalid_xml():
    """Test error handling when file-like object contains invalid XML"""
    invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ead>
        <unclosed_tag>
    </ead>"""
    
    file_like = io.StringIO(invalid_xml)
    
    with pytest.raises(ValueError) as excinfo:
        EAD.from_file(file_like)
    assert "Invalid XML" in str(excinfo.value)

def test_create_csv_data(ead_instance):
    """Test creation of CSV data"""
    csv_data = ead_instance.create_csv_data()
    assert isinstance(csv_data, list)
    # collection row + 28 components (4 c01 + 13 c02 + 9 c03 + 2 c04)
    assert len(csv_data) == 29

    row = csv_data[0]
    assert row["level"] == "collection"
    assert row["title"] == "Sample Collection"
    assert row["path"] == "Sample Collection"
    assert row["depth"] == 0
    assert row["has_online_content"] == "No"
    assert "date" in row

    first_component = csv_data[1]
    assert first_component["title"] == "Series 1: Personal Papers"
    assert first_component["depth"] == 1

def test_save_csv_data(ead_instance):
    """Test saving CSV data to a file"""
    csv_data = [
        {"id": "test123", "title": "Test", "level": "item", "depth": 1},
        {"id": "test456", "title": "Another Test", "level": "file", "depth": 2}
    ]
    
    # Create temp file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        output_path = temp_file.name
    
    # Save CSV data to file
    ead_instance.save_csv_data(csv_data, output_path)
    
    # Verify file exists and contains correct data
    assert os.path.exists(output_path)
    with open(output_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "test123"
        assert rows[1]["id"] == "test456"
    
    # Clean up
    os.unlink(output_path)

def test_save_empty_csv_data(ead_instance):
    """Test error handling when saving empty CSV data"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        output_path = temp_file.name
    
    # Try to save empty CSV data
    with pytest.raises(ValueError) as excinfo:
        ead_instance.save_csv_data([], output_path)
    
    assert "No CSV data to save" in str(excinfo.value)
    
    # Clean up
    os.unlink(output_path)

def test_create_and_save_csv(ead_instance):
    """Test the combined create and save CSV functionality"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        output_path = temp_file.name
    
    # Create and save CSV
    created_csv_data = ead_instance.create_and_save_csv(output_path)
    
    # Verify file exists
    assert os.path.exists(output_path)
    
    # Verify data was written correctly
    with open(output_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == len(created_csv_data)
        
        if len(rows) > 0:
            # Check first row keys match
            for key in created_csv_data[0]:
                assert key in reader.fieldnames
    
    # Clean up
    os.unlink(output_path)

def test_type_validation():
    """Test type validation in class methods"""
    # Test from_path with non-string
    with pytest.raises(TypeError):
        EAD.from_path(123)
    
    # Test from_string with non-string
    with pytest.raises(TypeError):
        EAD.from_string(123)
    
    # Test from_bytes with non-bytes
    with pytest.raises(TypeError):
        EAD.from_bytes("not bytes")
    
    # Test from_file with non-file-like object
    with pytest.raises(TypeError):
        EAD.from_file("not a file object")

def test_chunks_include_item_notes_subjects_daos_and_creators():
    """Item-level content of every supported kind reaches the chunk text."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader><eadid>chunk-test</eadid></eadheader>
        <archdesc level="collection">
            <did><unittitle>Test Collection</unittitle></did>
            <dsc>
                <c01 level="item" id="c1">
                    <did>
                        <unittitle>Diary</unittitle>
                        <origination label="creator"><persname>Example, A.</persname></origination>
                        <dao xmlns:xlink="http://www.w3.org/1999/xlink"
                             xlink:href="https://example.org/diary"/>
                    </did>
                    <acqinfo><p>Gift of the family.</p></acqinfo>
                    <controlaccess><subject>Diaries</subject></controlaccess>
                </c01>
            </dsc>
        </archdesc>
    </ead>"""
    chunk = EAD.from_string(xml).create_item_chunks()[0]
    text = chunk["text"]
    assert "Acqinfo: Gift of the family." in text
    assert "Subjects: Diaries" in text
    # A <dao> with no label contributes its bare href
    assert "Digital_objects: https://example.org/diary" in text
    assert "Creators: Example, A. (persname)" in text


def test_entity_reference_after_sibling_element_keeps_tail_text():
    """An entity ref between elements is dropped without losing its tail."""
    xml = """<!DOCTYPE ead [<!ENTITY su_name SYSTEM "su_name.txt">]>
    <ead><eadheader><eadid>t</eadid></eadheader>
    <archdesc level="collection"><did>
        <unittitle>Papers of <emph>A. Example</emph> &su_name; and Others</unittitle>
    </did><dsc/></archdesc></ead>"""
    with pytest.warns(UserWarning, match="su_name"):
        data = EAD.from_string(xml).data
    assert data["title"] == "Papers of A. Example and Others"


def test_unreadable_source_raises_io_error():
    """lxml's own read failures are reported with the source in the message."""
    with pytest.raises(IOError) as excinfo:
        EAD("/nonexistent/directory/file.xml")
    assert "Error reading from" in str(excinfo.value)


def test_unsupported_source_type_raises_runtime_error():
    """Anything lxml cannot parse from at all is a RuntimeError."""
    with pytest.raises(RuntimeError) as excinfo:
        EAD(42)
    assert "Unexpected error parsing EAD input" in str(excinfo.value)


def test_encoding_parameter_is_deprecated():
    """The parameter is ignored; passing it should say so rather than
    silently do nothing (a caller meaning include_internal can land here)."""
    xml = """<ead xmlns="urn:isbn:1-931666-22-9">
        <eadheader><eadid>t</eadid></eadheader>
        <archdesc level="collection"><did><unittitle>T</unittitle></did><dsc/></archdesc>
    </ead>"""
    with pytest.warns(DeprecationWarning, match="'encoding' parameter is deprecated"):
        ead = EAD.from_string(xml, "iso-8859-1")
    assert ead.data["title"] == "T"

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert EAD.from_string(xml).data["title"] == "T"


def test_include_internal_must_be_keyword():
    """Guards against from_string(xml, True) landing on the encoding slot."""
    with pytest.raises(TypeError):
        EAD.from_bytes(b"<ead/>", True)
