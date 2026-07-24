"""
Exception types raised by eadpy.
"""


class EadpyError(Exception):
    """Base class for all eadpy-specific errors."""


class EadParseError(EadpyError, ValueError):
    """
    Raised when EAD XML cannot be parsed or is not a supported EAD document.

    Subclasses ValueError for backward compatibility with code that caught
    the ValueError previously raised for these failures.
    """
