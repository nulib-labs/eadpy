# EADPy

![PyPI - Version](https://img.shields.io/pypi/v/eadpy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for working with Encoded Archival Description (EAD) XML documents.

## Features

- Parse and manipulate EAD XML documents
- Convert EAD to various formats (JSON, CSV)
- Validate EAD documents against schemas
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

## Usage

### Parse an EAD file

```python
from eadpy import Ead

# Load an EAD file and parse it
ead = Ead("path/to/finding_aid.xml")
```

### Export to JSON chunks

```python
# Create chunks for embedding or display
ead.create_and_save_chunks("path/to/output.json")
```

### Export to CSV

```python
# Create a flattened CSV representation of the hierarchy
ead.create_and_save_csv("path/to/output.csv")
```

## Command-line Interface

EADPy supports processing multiple EAD XML files at once using the command-line interface.

### Processing a single file

```bash
# Export to JSON (default)
eadpy file path/to/finding_aid.xml -o output.json

# Export to CSV
eadpy file path/to/finding_aid.xml -o output.csv -f csv

# Use verbose mode for detailed output
eadpy file path/to/finding_aid.xml -v
```

### Batch processing a directory of files

```bash
# Process all XML files in a directory and export to JSON
eadpy dir path/to/ead_directory

# Export to CSV
eadpy dir path/to/ead_directory -f csv

# Specify an output directory
eadpy dir path/to/ead_directory -o path/to/output_directory

# Process subdirectories recursively
eadpy dir path/to/ead_directory -r

# Use verbose mode for detailed output
eadpy dir path/to/ead_directory -v
```

### Command-line options

#### Global options

- `--version`: Show the version number and exit
- `--help`: Show help message and exit

#### File command options

- `input`: Path to the EAD XML file (required)
- `-o, --output`: Path to the output file
- `-f, --format`: Output format ('json' or 'csv')
- `-v, --verbose`: Print detailed information

#### Directory command options

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
