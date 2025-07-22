"""
Try out Challenge 1A on your custom PDF files.

This script is meant for testing the PDF outline extraction on individual PDF files.
It leverages the OutlineParser class defined in process_pdf.py and prints + saves the output.
"""

import sys
import os
import json

# Allow importing from the current directory (important when using relative imports)
sys.path.append('.')

# Import the OutlineParser from your main processing script
from process_pdf import OutlineParser


def evaluate_pdf_outline(input_pdf):
    """
    This function runs the outline extraction pipeline on a single PDF.
    It prints the extracted title, number of headings, a structured outline, 
    and saves the result to a JSON file.
    """
    # Check if the provided file path actually exists
    if not os.path.exists(input_pdf):
        print(f"File not found: {input_pdf}")
        return

    print(f"Running outline extraction...")

    # Define the path to the JSON schema file used for validation
    schema_file = "sample_dataset/schema/output_schema.json"
    parser = OutlineParser(schema_file)
    extracted = parser.extract_outline(input_pdf)

    print(f"\nTitle: {extracted['title']}")
    print(f"Total headings found: {len(extracted['outline'])}")

    # Print each heading in a hierarchical, indented format
    print(f"\nStructured Outline:")
    for entry in extracted['outline']:
        # Determine how much indentation to apply based on heading level (H1, H2, etc.)
        indentation = "  " * (int(entry['level'][1]) - 1)
        print(f"{indentation}{entry['level']}: \"{entry['text']}\" (Page {entry['page']})")

    # Save the structured output to a new JSON file
    output_filename = os.path.basename(input_pdf).replace('.pdf', '_output.json')
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)

    print(f"\nOutput saved at: {output_filename}")


# Entry point for command-line usage
if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        evaluate_pdf_outline(input_path)
    else:
        print("Run: python test_pdf.py <pdf_path>")