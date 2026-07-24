"""
EADPy - A Python library for parsing EAD (Encoded Archival Description) XML files.

Supports EAD 2002 and EAD3, with experimental support for the draft
EAD 4.0 schema. The version is auto-detected from the document's namespace
and exposed as `EAD.ead_version`.
"""
from typing import IO, Optional, Union

from eadpy.ead import EAD
from eadpy.exceptions import EadpyError, EadParseError
__version__ = "0.2.0"
__all__ = [
    "EAD", "EadpyError", "EadParseError",
    "from_path", "from_string", "from_bytes", "from_file",
]

# Expose class methods directly at the package level
def from_path(file_path: str, *, include_internal: bool = False) -> EAD:
    """
    Creates an EAD instance from a file path.
    
    Parameters
    ----------
    file_path : str
        Path to the EAD XML file.
    include_internal : bool, optional
        Keep content marked audience="internal" (staff-only description).
        Excluded by default.
    
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_path(file_path, include_internal=include_internal)

def from_string(xml_string: str, encoding: Optional[str] = None, *,
                include_internal: bool = False) -> EAD:
    """
    Creates an EAD instance from an XML string.
    
    Parameters
    ----------
    xml_string : str
        String containing EAD XML content.
    encoding : str, optional
        Deprecated and ignored; passing it raises a DeprecationWarning.
    include_internal : bool, optional
        Keep content marked audience="internal" (staff-only description).
        Excluded by default.
    
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_string(xml_string, encoding, include_internal=include_internal)

def from_bytes(xml_bytes: bytes, *, include_internal: bool = False) -> EAD:
    """
    Creates an EAD instance from XML bytes.
    
    Parameters
    ----------
    xml_bytes : bytes
        Bytes containing EAD XML content.
    include_internal : bool, optional
        Keep content marked audience="internal" (staff-only description).
        Excluded by default.
    
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_bytes(xml_bytes, include_internal=include_internal)

def from_file(file_like_object: Union[IO[str], IO[bytes]], *,
              include_internal: bool = False) -> EAD:
    """
    Creates an EAD instance from a file-like object.
    
    Parameters
    ----------
    file_like_object : file-like object
        File-like object with a 'read' method containing EAD XML content.
    include_internal : bool, optional
        Keep content marked audience="internal" (staff-only description).
        Excluded by default.
    
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_file(file_like_object, include_internal=include_internal)