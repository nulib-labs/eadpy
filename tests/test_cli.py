import os
import sys
import glob
import tempfile
import unittest.mock as mock
import pytest
from pathlib import Path

from eadpy.cli import process_file, process_directory, main
# Import the top-level functions from eadpy to mock them in tests
from eadpy import from_path, EAD

@pytest.fixture
def sample_xml_path():
    return "tests/sample.xml"

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

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    
    # Cleanup
    # We use shutil.rmtree safely by wrapping in a try/except
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except:
        pass

class TestProcessFile:
    """Tests for the process_file function"""
    
    def test_process_file_json(self, sample_xml_path, temp_dir):
        """Test processing a file to JSON format"""
        output_file = os.path.join(temp_dir, "output.json")
        success, result = process_file(sample_xml_path, output_file, "json", False)
        
        assert success is True
        assert result == output_file
        assert os.path.exists(output_file)
        
    def test_process_file_csv(self, sample_xml_path, temp_dir):
        """Test processing a file to CSV format"""
        output_file = os.path.join(temp_dir, "output.csv")
        success, result = process_file(sample_xml_path, output_file, "csv", False)
        
        assert success is True
        assert result == output_file
        assert os.path.exists(output_file)
        
    def test_process_file_infer_json_format(self, sample_xml_path, temp_dir):
        """Test inferring JSON format from file extension"""
        output_file = os.path.join(temp_dir, "output.json")
        success, result = process_file(sample_xml_path, output_file, None, False)
        
        assert success is True
        assert os.path.exists(output_file)
        
    def test_process_file_infer_csv_format(self, sample_xml_path, temp_dir):
        """Test inferring CSV format from file extension"""
        output_file = os.path.join(temp_dir, "output.csv")
        success, result = process_file(sample_xml_path, output_file, None, False)
        
        assert success is True
        assert os.path.exists(output_file)
        
    def test_process_file_auto_output(self, sample_xml_path, temp_dir):
        """Test auto-generating output filename"""
        # Copy the sample file to the temp directory
        import shutil
        temp_sample = os.path.join(temp_dir, os.path.basename(sample_xml_path))
        shutil.copy(sample_xml_path, temp_sample)
        
        # Change working directory to temp_dir since that's where process_file
        # will create the output when no output path is specified
        old_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            success, result = process_file(temp_sample, None, "json", False)
            
            assert success is True
            # The result should be just the filename or a path in the temp directory
            expected_basename = "sample.json"
            assert os.path.basename(result) == expected_basename
            
            # Check if the file exists - either as relative to current dir (temp_dir)
            # or as an absolute path if that's what was returned
            if os.path.isabs(result):
                assert os.path.exists(result)
            else:
                assert os.path.exists(os.path.join(temp_dir, result))
        finally:
            # Restore working directory
            os.chdir(old_cwd)
            
    def test_process_file_nonexistent(self, temp_dir):
        """Test processing a nonexistent file"""
        success, result = process_file("nonexistent.xml", None, "json", False)
        
        assert success is False
        assert "does not exist" in result
        
    def test_process_file_directory(self, temp_dir):
        """Test processing a directory as a file"""
        success, result = process_file(temp_dir, None, "json", False)
        
        assert success is False
        assert "not a file" in result
        
    def test_process_file_error(self, temp_dir):
        """Test handling of parsing errors"""
        # Create an invalid XML file
        invalid_file = os.path.join(temp_dir, "invalid.xml")
        with open(invalid_file, "w") as f:
            f.write("<invalid>")
        
        success, result = process_file(invalid_file, None, "json", False)
        
        assert success is False
        assert "Invalid XML" in result or "Premature end of data" in result

class TestProcessDirectory:
    """Tests for the process_directory function"""
    
    def setup_test_files(self, dir_path, count=3, invalid=0):
        """Helper to set up test files in a directory"""
        valid_template = """<?xml version="1.0" encoding="UTF-8"?>
        <ead xmlns="urn:isbn:1-931666-22-9">
            <eadheader>
                <eadid>test{}</eadid>
            </eadheader>
            <archdesc level="collection">
                <did>
                    <unittitle>Test Collection {}</unittitle>
                </did>
                <dsc></dsc>
            </archdesc>
        </ead>"""
        
        invalid_xml = "<invalid>"
        
        # Create valid files
        for i in range(count - invalid):
            file_path = os.path.join(dir_path, f"valid_{i}.xml")
            with open(file_path, "w") as f:
                f.write(valid_template.format(i, i))
                
        # Create invalid files
        for i in range(invalid):
            file_path = os.path.join(dir_path, f"invalid_{i}.xml")
            with open(file_path, "w") as f:
                f.write(invalid_xml)
                
        # Create a subdirectory with files if needed
        subdir = os.path.join(dir_path, "subdir")
        os.makedirs(subdir, exist_ok=True)
        
        for i in range(2):
            file_path = os.path.join(subdir, f"sub_{i}.xml")
            with open(file_path, "w") as f:
                f.write(valid_template.format(f"sub_{i}", f"sub_{i}"))
    
    def test_process_directory_basic(self, temp_dir):
        """Test basic directory processing"""
        self.setup_test_files(temp_dir, count=3)
        
        success_count, failure_count, errors = process_directory(
            temp_dir, None, "json", False, False
        )
        
        assert success_count == 3
        assert failure_count == 0
        assert len(errors) == 0
        
        # Check that output files were created
        json_files = glob.glob(os.path.join(temp_dir, "*.json"))
        assert len(json_files) == 3
        
    def test_process_directory_with_output_dir(self, temp_dir):
        """Test directory processing with custom output directory"""
        self.setup_test_files(temp_dir, count=3)
        output_dir = os.path.join(temp_dir, "output")
        
        success_count, failure_count, errors = process_directory(
            temp_dir, output_dir, "json", False, False
        )
        
        assert success_count == 3
        assert failure_count == 0
        
        # Check that output files were created in the correct directory
        json_files = glob.glob(os.path.join(output_dir, "*.json"))
        assert len(json_files) == 3
        
    def test_process_directory_csv_format(self, temp_dir):
        """Test directory processing with CSV format"""
        self.setup_test_files(temp_dir, count=3)
        
        success_count, failure_count, errors = process_directory(
            temp_dir, None, "csv", False, False
        )
        
        assert success_count == 3
        assert failure_count == 0
        
        # Check that output files were created with CSV extension
        csv_files = glob.glob(os.path.join(temp_dir, "*.csv"))
        assert len(csv_files) == 3
        
    def test_process_directory_recursive(self, temp_dir):
        """Test recursive directory processing"""
        self.setup_test_files(temp_dir, count=3)
        
        success_count, failure_count, errors = process_directory(
            temp_dir, None, "json", True, False
        )
        
        # Should find 3 in main dir + 2 in subdir = 5 files
        assert success_count == 5
        assert failure_count == 0
        
    def test_process_directory_with_failures(self, temp_dir):
        """Test directory processing with some failing files"""
        self.setup_test_files(temp_dir, count=5, invalid=2)
        
        success_count, failure_count, errors = process_directory(
            temp_dir, None, "json", False, False
        )
        
        assert success_count == 3
        assert failure_count == 2
        assert len(errors) == 2
        
    def test_process_nonexistent_directory(self):
        """Test processing a nonexistent directory"""
        success_count, failure_count, errors = process_directory(
            "nonexistent_dir", None, "json", False, False
        )
        
        assert success_count == 0
        assert failure_count == 1
        assert len(errors) == 1
        assert "does not exist" in errors[0]
        
    def test_process_file_as_directory(self, sample_xml_path):
        """Test processing a file as a directory"""
        success_count, failure_count, errors = process_directory(
            sample_xml_path, None, "json", False, False
        )
        
        assert success_count == 0
        assert failure_count == 1
        assert len(errors) == 1
        assert "not a directory" in errors[0]
        
    def test_process_empty_directory(self, temp_dir):
        """Test processing an empty directory"""
        success_count, failure_count, errors = process_directory(
            temp_dir, None, "json", False, False
        )
        
        assert success_count == 0
        assert failure_count == 0
        assert len(errors) == 1
        assert "No XML files found" in errors[0]

class TestMainCLI:
    """Tests for the main CLI function"""
    
    @pytest.fixture
    def mock_argparse(self):
        """Mock argparse to test the main function"""
        with mock.patch("argparse.ArgumentParser") as mock_parser:
            # Create mock for the parser
            parser = mock.MagicMock()
            mock_parser.return_value = parser
            
            # Create mock for subparsers
            subparsers = mock.MagicMock()
            parser.add_subparsers.return_value = subparsers
            
            # Create mocks for subcommand parsers
            file_parser = mock.MagicMock()
            dir_parser = mock.MagicMock()
            subparsers.add_parser.side_effect = [file_parser, dir_parser]
            
            yield {
                'parser': parser,
                'subparsers': subparsers,
                'file_parser': file_parser,
                'dir_parser': dir_parser
            }
    
    @mock.patch("eadpy.cli.process_file")
    def test_main_file_command(self, mock_process_file, mock_argparse):
        """Test the main function with file command"""
        # Setup mock
        mock_process_file.return_value = (True, "output.json")
        
        # Setup args
        args = mock.MagicMock()
        args.command = "file"
        args.input = "test.xml"
        args.output = "output.json"
        args.format = "json"
        args.verbose = False
        mock_argparse['parser'].parse_args.return_value = args
        
        # Call main function
        with mock.patch.object(sys, 'argv', ['eadpy', 'file', 'test.xml']):
            with mock.patch('sys.exit') as mock_exit:
                main()
                
                # Assert process_file was called with correct args
                mock_process_file.assert_called_once_with(
                    "test.xml", "output.json", "json", False
                )
                
                # Assert we didn't exit with error
                mock_exit.assert_not_called()
                
    @mock.patch("eadpy.cli.process_file")
    def test_main_file_command_error(self, mock_process_file, mock_argparse):
        """Test the main function with file command that errors"""
        # Setup mock to return an error
        mock_process_file.return_value = (False, "Error message")
        
        # Setup args
        args = mock.MagicMock()
        args.command = "file"
        args.input = "nonexistent.xml"
        args.output = None
        args.format = None
        args.verbose = False
        mock_argparse['parser'].parse_args.return_value = args
        
        # Call main function
        with mock.patch.object(sys, 'argv', ['eadpy', 'file', 'nonexistent.xml']):
            with mock.patch('sys.exit') as mock_exit:
                with mock.patch('builtins.print') as mock_print:
                    main()
                    
                    # Assert process_file was called
                    mock_process_file.assert_called_once()
                    
                    # Assert we exited with error code 1
                    mock_exit.assert_called_once_with(1)
                    
                    # Assert error was printed
                    mock_print.assert_any_call("Error: Error message")
                    
    @mock.patch("eadpy.cli.process_directory")
    def test_main_dir_command(self, mock_process_directory, mock_argparse):
        """Test the main function with dir command"""
        # Setup mock
        mock_process_directory.return_value = (3, 0, [])
        
        # Setup args
        args = mock.MagicMock()
        args.command = "dir"
        args.input_dir = "test_dir"
        args.output_dir = "output_dir"
        args.format = "json"
        args.recursive = True
        args.verbose = False
        mock_argparse['parser'].parse_args.return_value = args
        
        # Call main function
        with mock.patch.object(sys, 'argv', ['eadpy', 'dir', 'test_dir']):
            with mock.patch('sys.exit') as mock_exit:
                main()
                
                # Assert process_directory was called with correct args
                mock_process_directory.assert_called_once_with(
                    "test_dir", "output_dir", "json", True, False
                )
                
                # Assert we didn't exit with error
                mock_exit.assert_not_called()
                
    @mock.patch("eadpy.cli.process_directory")
    def test_main_dir_command_with_failures(self, mock_process_directory, mock_argparse):
        """Test the main function with dir command that has failures"""
        # Setup mock with failures
        mock_process_directory.return_value = (2, 1, ["Error with file1.xml"])
        
        # Setup args
        args = mock.MagicMock()
        args.command = "dir"
        args.input_dir = "test_dir"
        args.output_dir = None
        args.format = "json"
        args.recursive = False
        args.verbose = True
        mock_argparse['parser'].parse_args.return_value = args
        
        # Call main function
        with mock.patch.object(sys, 'argv', ['eadpy', 'dir', 'test_dir']):
            with mock.patch('sys.exit') as mock_exit:
                with mock.patch('builtins.print') as mock_print:
                    main()
                    
                    # Assert process_directory was called
                    mock_process_directory.assert_called_once()
                    
                    # Assert we exited with error code 1
                    mock_exit.assert_called_once_with(1)
                    
                    # Assert summary was printed
                    mock_print.assert_any_call("Processed 3 files:")
                    mock_print.assert_any_call("  - Successfully processed: 2")
                    mock_print.assert_any_call("  - Failed to process: 1")
                    
                    # Assert errors were printed in verbose mode
                    mock_print.assert_any_call("\nErrors:")
                    mock_print.assert_any_call("  - Error with file1.xml")
                    
    def test_main_no_command(self, mock_argparse):
        """Test the main function with no command"""
        # Setup args with no command
        args = mock.MagicMock()
        args.command = None
        mock_argparse['parser'].parse_args.return_value = args
        
        # Call main function
        with mock.patch.object(sys, 'argv', ['eadpy']):
            with mock.patch('sys.exit') as mock_exit:
                main()
                
                # Assert help was shown and we exited
                mock_argparse['parser'].print_help.assert_called_once()
                mock_exit.assert_called_once_with(1)