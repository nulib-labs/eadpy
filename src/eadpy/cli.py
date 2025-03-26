"""
Command-line interface for the EADPy library.
"""
import sys
import os
import argparse
import pathlib
import glob
from typing import List, Optional, Tuple
from eadpy import from_path, __version__

def process_file(ead_file: str, output_file: Optional[str] = None, 
                format_type: Optional[str] = None, verbose: bool = False) -> Tuple[bool, str]:
    """
    Process a single EAD XML file.
    
    Parameters
    ----------
    ead_file : str
        Path to the EAD XML file
    output_file : str, optional
        Path to the output file
    format_type : str, optional
        Output format ('json' or 'csv')
    verbose : bool
        Whether to print detailed information
    
    Returns
    -------
    Tuple[bool, str]
        Success status, Output file path or error message
    """
    try:
        if not os.path.exists(ead_file):
            return False, f"File '{ead_file}' does not exist."
        
        if not os.path.isfile(ead_file):
            return False, f"'{ead_file}' is not a file."
            
        # Determine output file if not provided
        if output_file is None:
            # Use the input file's directory and base name to construct the output path
            input_dir = os.path.dirname(ead_file) or '.'
            input_base = os.path.splitext(os.path.basename(ead_file))[0]
            ext = 'csv' if format_type == 'csv' else 'json'
            output_file = os.path.join(input_dir, f"{input_base}.{ext}")
        
        # Determine format type if not provided
        if format_type is None:
            ext = pathlib.Path(output_file).suffix.lower()
            format_type = 'csv' if ext == '.csv' else 'json'
        
        if verbose:
            print(f"Parsing EAD file: {ead_file}")
        
        ead = from_path(ead_file)
        
        if format_type == 'csv':
            ead.create_and_save_csv(output_file)
        else:
            ead.create_and_save_chunks(output_file)
            
        if verbose:
            print(f"Successfully wrote {format_type.upper()} output to: {output_file}")
            
        return True, output_file
        
    except Exception as e:
        return False, str(e)

def process_directory(directory: str, output_dir: Optional[str] = None,
                     format_type: str = 'json', recursive: bool = False,
                     verbose: bool = False) -> Tuple[int, int, List[str]]:
    """
    Process all XML files in a directory.
    
    Parameters
    ----------
    directory : str
        Path to the directory containing EAD XML files
    output_dir : str, optional
        Directory for output files
    format_type : str
        Output format ('json' or 'csv')
    recursive : bool
        Whether to process subdirectories recursively
    verbose : bool
        Whether to print detailed information
    
    Returns
    -------
    Tuple[int, int, List[str]]
        Success count, Failure count, List of errors
    """
    if not os.path.exists(directory):
        return 0, 1, [f"Directory '{directory}' does not exist."]
        
    if not os.path.isdir(directory):
        return 0, 1, [f"'{directory}' is not a directory."]
    
    # Create output directory if it doesn't exist
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # Find all XML files in the directory
    pattern = os.path.join(directory, '**' if recursive else '', '*.xml')
    xml_files = glob.glob(pattern, recursive=recursive)
    
    if not xml_files:
        return 0, 0, [f"No XML files found in '{directory}'."]
    
    success_count = 0
    failure_count = 0
    errors = []
    
    for xml_file in xml_files:
        if verbose:
            print(f"Processing file: {xml_file}")
        
        # Determine output file path
        if output_dir:
            rel_path = os.path.relpath(xml_file, directory)
            output_base = os.path.splitext(rel_path)[0]
            output_file = os.path.join(output_dir, f"{output_base}.{format_type}")
            
            # Create subdirectories if needed
            os.makedirs(os.path.dirname(os.path.join(output_dir, rel_path)), exist_ok=True)
        else:
            output_base = os.path.splitext(xml_file)[0]
            output_file = f"{output_base}.{format_type}"
        
        success, result = process_file(xml_file, output_file, format_type, verbose)
        
        if success:
            success_count += 1
        else:
            failure_count += 1
            errors.append(f"Error processing {xml_file}: {result}")
            if verbose:
                print(f"Error: {result}")
    
    return success_count, failure_count, errors

def main():
    """
    Main entry point for the EADPy command-line interface.
    
    Provides command-line functionality for processing EAD XML files,
    either individually or in directories. Supports output in both
    JSON and CSV formats.
    
    Returns
    -------
    None
        Terminates with exit code 0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description="EADPy - Process Encoded Archival Description (EAD) XML files",
        epilog="For more information, visit: https://github.com/nulib-labs/eadpy"
    )
    
    parser.add_argument('--version', action='version', version=f'EADPy {__version__}')
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # File command
    file_parser = subparsers.add_parser('file', help='Process a single EAD XML file')
    file_parser.add_argument('input', help='Path to the EAD XML file')
    file_parser.add_argument('-o', '--output', help='Path to the output file')
    file_parser.add_argument('-f', '--format', choices=['json', 'csv'], 
                            help='Output format (default: determined by output file extension)')
    file_parser.add_argument('-v', '--verbose', action='store_true', 
                            help='Print detailed information')
    
    # Directory command
    dir_parser = subparsers.add_parser('dir', help='Process all EAD XML files in a directory')
    dir_parser.add_argument('input_dir', help='Path to the directory containing EAD XML files')
    dir_parser.add_argument('-o', '--output-dir', help='Directory for output files')
    dir_parser.add_argument('-f', '--format', choices=['json', 'csv'], default='json',
                           help='Output format (default: json)')
    dir_parser.add_argument('-r', '--recursive', action='store_true',
                           help='Process subdirectories recursively')
    dir_parser.add_argument('-v', '--verbose', action='store_true',
                           help='Print detailed information')
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is given, print help
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Process command
    if args.command == 'file':
        success, result = process_file(args.input, args.output, args.format, args.verbose)
        if not success:
            print(f"Error: {result}")
            print(f"Current working directory: {os.getcwd()}")
            sys.exit(1)
        else:
            print(f"Successfully processed {args.input} to {result}")
            
    elif args.command == 'dir':
        success_count, failure_count, errors = process_directory(
            args.input_dir, args.output_dir, args.format, args.recursive, args.verbose
        )
        
        print(f"Processed {success_count + failure_count} files:")
        print(f"  - Successfully processed: {success_count}")
        print(f"  - Failed to process: {failure_count}")
        
        if failure_count > 0 and args.verbose:
            print("\nErrors:")
            for error in errors:
                print(f"  - {error}")
        
        if failure_count > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()