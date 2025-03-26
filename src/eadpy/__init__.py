"""
EADPy - A Python library for parsing EAD (Encoded Archival Description) XML files.
"""
from eadpy.ead import EAD
__version__ = "0.1.3"
__all__ = ["EAD", "from_path", "from_string", "from_bytes", "from_file"]

# Expose class methods directly at the package level
def from_path(file_path):
    """
    Creates an EAD instance from a file path.
    
    Parameters
    ----------
    file_path : str
        Path to the EAD XML file.
        
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_path(file_path)

def from_string(xml_string, encoding='utf-8'):
    """
    Creates an EAD instance from an XML string.
    
    Parameters
    ----------
    xml_string : str
        String containing EAD XML content.
    encoding : str, optional
        Encoding of the XML string. Default is 'utf-8'.
        
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_string(xml_string, encoding)

def from_bytes(xml_bytes):
    """
    Creates an EAD instance from XML bytes.
    
    Parameters
    ----------
    xml_bytes : bytes
        Bytes containing EAD XML content.
        
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_bytes(xml_bytes)

def from_file(file_like_object):
    """
    Creates an EAD instance from a file-like object.
    
    Parameters
    ----------
    file_like_object : file-like object
        File-like object with a 'read' method containing EAD XML content.
        
    Returns
    -------
    EAD
        An instance of the EAD class.
    """
    return EAD.from_file(file_like_object)