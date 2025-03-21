"""
Command-line interface for the EADPy library.
"""
import sys
import os
from eadpy import Ead

def main():
    """Main entry point for the EADPy command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: eadpy path_to_ead.xml [output_file.json]")
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

        output_file = None
        if len(sys.argv) == 3:
            output_file = sys.argv[2]
            print(f"Output file: {output_file}")
        else:
            print("No output file specified. Using default: ead.json")
            output_file = "ead.json"
        
        ead.create_and_save_chunks(output_file)
        print(f"Successfully wrote output to: {output_file}")
        
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        print(f"Current working directory: {os.getcwd()}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
