"""
Command-line interface for the EADPy library.
"""
import sys
import os
import pathlib
from eadpy import Ead

def main():
    """Main entry point for the EADPy command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: eadpy path_to_ead.xml [output_file.json|output_file.csv]")
        print("  - For JSON output, use .json extension")
        print("  - For CSV output, use .csv extension")
        sys.exit(1)
    
    ead_file = sys.argv[1]
    print(f"Loading EAD file: {ead_file}")
    
    try:
        if not os.path.exists(ead_file):
            print(f"Error: File '{ead_file}' does not exist.")
            print(f"Current working directory: {os.getcwd()}")
            sys.exit(1)
            
        ead = Ead(ead_file)
        print(f"Successfully parsed EAD file: {ead_file}")

        # Determine output file and format
        output_file = None
        if len(sys.argv) == 3:
            output_file = sys.argv[2]
            print(f"Output file: {output_file}")
        else:
            print("No output file specified. Using default: ead.json")
            output_file = "ead.json"
        
        # Determine output format based on file extension
        file_ext = pathlib.Path(output_file).suffix.lower()
        
        if file_ext == '.csv':
            ead.create_and_save_csv(output_file)
            print(f"Successfully wrote CSV output to: {output_file}")
        else:
            # Default to JSON for any other extension
            if file_ext != '.json':
                print(f"Warning: Unrecognized file extension '{file_ext}'. Using JSON format.")
            ead.create_and_save_chunks(output_file)
            print(f"Successfully wrote JSON output to: {output_file}")
        
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        print(f"Current working directory: {os.getcwd()}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
