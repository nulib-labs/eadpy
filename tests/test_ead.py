import os
import json
import csv
import tempfile
import pytest
from lxml import etree
from eadpy.ead import Ead

@pytest.fixture
def sample_xml_path():
    return "tests/sample.xml"

@pytest.fixture
def ead_instance(sample_xml_path):
    return Ead(sample_xml_path)

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

def test_initialization_and_parsing(ead_instance):
    """Test that Ead object initializes and parses correctly"""
    assert ead_instance is not None
    assert ead_instance.file_path is not None
    assert ead_instance.data is not None
    assert isinstance(ead_instance.data, dict)
    assert "level" in ead_instance.data
    assert ead_instance.data["level"] == "collection"

def test_parse_empty_xml(empty_xml):
    """Test parsing an empty but valid EAD XML file"""
    ead = Ead(empty_xml)
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
    assert "id" in collection
    assert "title" in collection
    assert "level" in collection
    assert collection["level"] == "collection"
    assert "normalized_title" in collection
    assert "dates" in collection
    assert "creators" in collection
    assert "notes" in collection

def test_parse_components(ead_instance):
    """Test that components are parsed correctly"""
    # Test that components exist and have the right structure
    assert "components" in ead_instance.data
    assert isinstance(ead_instance.data["components"], list)
    
    # Assuming sample.xml has at least one component
    if len(ead_instance.data["components"]) > 0:
        component = ead_instance.data["components"][0]
        assert "id" in component
        assert "level" in component
        assert "title" in component
        assert "parent_id" in component
        assert component["parent_id"] == ead_instance.data["id"]

def test_create_item_chunks(ead_instance):
    """Test creation of item chunks"""
    chunks = ead_instance.create_item_chunks()
    assert isinstance(chunks, list)
    
    # Test that chunks have the right structure
    if len(chunks) > 0:
        chunk = chunks[0]
        assert "text" in chunk
        assert "metadata" in chunk
        assert "id" in chunk["metadata"]
        assert "title" in chunk["metadata"]
        assert "path" in chunk["metadata"]
        assert "level" in chunk["metadata"]

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
        Ead("nonexistent_file.xml")
    assert "EAD file not found" in str(excinfo.value)
    assert "nonexistent_file.xml" in str(excinfo.value)

def test_directory_as_file():
    """Test error handling when a directory is provided instead of a file"""
    with pytest.raises(IsADirectoryError) as excinfo:
        Ead("tests")  # Assuming 'tests' directory exists
    assert "is a directory, not a file" in str(excinfo.value)

def test_file_permission_error(monkeypatch):
    """Test error handling when file doesn't have read permissions"""
    # Create a temporary mock function to simulate permission error
    def mock_access(*args, **kwargs):
        return False
    
    # Create a temporary mock function that makes the file appear to exist
    def mock_exists(*args, **kwargs):
        return True
    
    def mock_isfile(*args, **kwargs):
        return True
    
    # Apply the monkeypatch to os.access to simulate permission error
    monkeypatch.setattr(os, "access", mock_access)
    monkeypatch.setattr(os, "path", 
        type('MockPath', (), {
            'exists': mock_exists,
            'isfile': mock_isfile,
        })()
    )
    
    with pytest.raises(PermissionError) as excinfo:
        Ead("fake_permission_error.xml")
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
            Ead(temp_file.name)
        assert "Invalid XML" in str(excinfo.value)
    finally:
        # Clean up
        os.unlink(temp_file.name)

def test_create_csv_data(ead_instance):
    """Test creation of CSV data"""
    csv_data = ead_instance.create_csv_data()
    assert isinstance(csv_data, list)
    
    # Test that CSV data has the right structure
    if len(csv_data) > 0:
        row = csv_data[0]
        assert "id" in row
        assert "title" in row
        assert "level" in row
        assert "path" in row
        assert "depth" in row
        assert "date" in row
        assert "has_online_content" in row
        assert isinstance(row["depth"], int)

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
