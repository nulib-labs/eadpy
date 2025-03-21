# EADPy

![PyPI - Version](https://img.shields.io/pypi/v/eadpy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for working with Encoded Archival Description (EAD) XML documents.

## Features

- Parse and manipulate EAD XML documents
- Convert EAD to various formats (JSON, CSV, etc.)
- Validate EAD documents against schemas
- Tools for batch processing of EAD files

## Installation

Install EADPy using pip:

```bash
pip install eadpy
```

## Usage

```python
from eadpy import Ead

# Load an EAD file and process it
ead = Ead("path/to/finding_aid.xml")
ead.create_and_save_chunks("path/to/output.json")
```

## Development

### Setting up the development environment

EADPy uses [uv](https://github.com/astral-sh/uv) for dependency management and virtual environment setup.

1. Clone the repository:

```bash
git clone https://github.com/yourusername/eadpy.git
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
