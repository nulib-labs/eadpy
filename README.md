# EADPy

![PyPI - Version](https://img.shields.io/pypi/v/eadpy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for working with Encoded Archival Description (EAD) XML documents.

## Features

- Parse and manipulate EAD XML documents
- Convert EAD to various formats (JSON, CSV)
- Tools for batch processing of EAD files

## Installation

Install EADPy using `pip`:

```bash
pip install eadpy
```

Install using `uv`:

```bash
uv tool install eadpy
```

EADPy requires Python 3.8 or higher.

## Command-line Usage

The following command will process an EAD XML file and export it to JSON format:

```bash
eadpy file path/to/finding_aid.xml -o output.json
```

To export to CSV format instead:

```bash
eadpy file path/to/finding_aid.xml -o output.csv -f csv
```

For batch processing of multiple EAD XML files in a directory:

```bash
eadpy dir path/to/ead_directory -o path/to/output_directory
```

To process subdirectories recursively:

```bash
eadpy dir path/to/ead_directory -r -o path/to/output_directory
```

Use the verbose flag for detailed information during processing:

```bash
eadpy file path/to/finding_aid.xml -v
```

Run the following to view all available options:

```bash
eadpy --help
```

## Python Usage

EADPy provides multiple ways to create an `EAD` instance depending on your source data:

```python
import eadpy

# Load an EAD file from a file path
ead = eadpy.from_path("path/to/finding_aid.xml")

# Create an EAD instance from an XML string
xml_string = """<?xml version="1.0" encoding="UTF-8"?>
<ead xmlns="urn:isbn:1-931666-22-9">
    <!-- EAD content here -->
</ead>"""
ead = eadpy.from_string(xml_string)

# Create an EAD instance from bytes
from eadpy import from_bytes
with open("path/to/finding_aid.xml", "rb") as f:
    xml_bytes = f.read()
ead = from_bytes(xml_bytes)

# Create an EAD instance from a file-like object
from eadpy import from_file
with open("path/to/finding_aid.xml", "r") as f:
    ead = from_file(f)

# Also works with StringIO or BytesIO objects
from io import StringIO, BytesIO
from eadpy import from_file, from_string, from_bytes

string_io = StringIO(xml_string)
ead = from_file(string_io)

bytes_io = BytesIO(xml_bytes)
ead = from_file(bytes_io)
```

### Class-Based API Style

```python
from eadpy import EAD

# Load an EAD file from a file path
ead = EAD.from_path("path/to/finding_aid.xml")

# Create an EAD instance from an XML string
ead = EAD.from_string(xml_string)

# Create an EAD instance from bytes
with open("path/to/finding_aid.xml", "rb") as f:
    xml_bytes = f.read()
ead = EAD.from_bytes(xml_bytes)

# Create an EAD instance from a file-like object
with open("path/to/finding_aid.xml", "r") as f:
    ead = EAD.from_file(f)
```

### Export to JSON chunks

JSON chunks are useful for embedding or display in applications:

```python
# Create chunks and save them to a file
chunks = ead.create_and_save_chunks("output.json")

# Or create chunks without saving
chunks = ead.create_item_chunks()

# Then save them separately if needed
ead.save_chunks_to_json(chunks, "output.json")
```

### Export to CSV

CSV export is useful for tabular analysis:

```python
# Create CSV data and save it to a file
csv_data = ead.create_and_save_csv("output.csv")

# Or create CSV data without saving
csv_data = ead.create_csv_data()

# Then save it separately if needed
ead.save_csv_data(csv_data, "output.csv")
```

## API Reference

### Package Level Functions 

- **`from_path(file_path: str) -> EAD`**: Creates an EAD instance from a file path. Validates that the file exists, is not a directory, and is readable.

- **`from_string(xml_string: str, encoding: str = 'utf-8') -> EAD`**: Creates an EAD instance from an XML string. Handles encoding the string to bytes for proper XML parsing.

- **`from_bytes(xml_bytes: bytes) -> EAD`**: Creates an EAD instance from XML bytes. Useful when working with binary data from HTTP responses or other sources.

- **`from_file(file_like_object) -> EAD`**: Creates an EAD instance from a file-like object with a `read()` method. Works with both text-based (StringIO) and binary (BytesIO) file objects.

### Class Methods (Object Creation)

- **`EAD.from_path(file_path: str) -> EAD`**: Creates an EAD instance from a file path. Validates that the file exists, is not a directory, and is readable.

- **`EAD.from_string(xml_string: str, encoding: str = 'utf-8') -> EAD`**: Creates an EAD instance from an XML string. Handles encoding the string to bytes for proper XML parsing.

- **`EAD.from_bytes(xml_bytes: bytes) -> EAD`**: Creates an EAD instance from XML bytes. Useful when working with binary data from HTTP responses or other sources.

- **`EAD.from_file(file_like_object) -> EAD`**: Creates an EAD instance from a file-like object with a `read()` method. Works with both text-based (StringIO) and binary (BytesIO) file objects.

### Instance Methods (Data Export)

- **`create_item_chunks() -> list`**: Creates item-focused chunks that include relevant information from their parent hierarchy. Returns a list of dictionaries, each containing a text representation and metadata for each item.

- **`save_chunks_to_json(chunks: list, output_file: str) -> None`**: Saves chunks to a JSON file. Takes a list of chunks and an output file path.

- **`create_and_save_chunks(output_file: str) -> list`**: Creates item-focused chunks and saves them to a JSON file. Returns the chunks that were created and saved.

- **`create_csv_data() -> list`**: Creates a flattened hierarchy representation suitable for CSV export. Returns a list of dictionaries, each representing a row in the CSV.

- **`save_csv_data(csv_data: list, output_file: str) -> None`**: Saves CSV data to a file. Takes a list of dictionaries and an output file path.

- **`create_and_save_csv(output_file: str) -> list`**: Creates flattened CSV data and saves it to a file. Returns the CSV data that was created and saved.

## Command-line Reference

### Global options

- `--version`: Show the version number and exit
- `--help`: Show help message and exit

### File command options

- `input`: Path to the EAD XML file (required)
- `-o, --output`: Path to the output file
- `-f, --format`: Output format ('json' or 'csv')
- `-v, --verbose`: Print detailed information

### Directory command options

- `input_dir`: Path to the directory containing EAD XML files (required)
- `-o, --output-dir`: Directory for output files
- `-f, --format`: Output format ('json' or 'csv', default: 'json')
- `-r, --recursive`: Process subdirectories recursively
- `-v, --verbose`: Print detailed information

## Development

### Setting up the development environment

EADPy uses [uv](https://github.com/astral-sh/uv) for dependency management and virtual environment setup.

1. Clone the repository:

```bash
git clone https://github.com/nulib-labs/eadpy
cd eadpy
```

2. Create and activate a virtual environment:

```bash
uv venv --python 3.13
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

3. Install development dependencies:

```bash
uv pip install -e ".[dev]"
```

### Running tests

```bash
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

Special thanks to the [ArcLight](https://github.com/projectblacklight/arclight) project, which inspired the EAD processing approach taken here. Thank you to the developers and contributors of ArcLight for their work in the archival community!

## License

This project is licensed under the MIT License - see the LICENSE file for details.
