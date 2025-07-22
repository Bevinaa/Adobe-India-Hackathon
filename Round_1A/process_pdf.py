"""
Adobe Hackathon Challenge 1A: PDF Outline Extraction

SUBMITTED BY : Team_BD (Bevina R, Deepitha P - SSNCE)

This script processes PDF files and extracts a structured outline,
including document titles and hierarchical headings (like H1, H2, H3).
It uses PyMuPDF (fitz) for reading PDFs and optionally validates the output JSON.
"""

import os, json, jsonschema, time, re
from pathlib import Path
from typing import Optional
import logging
import fitz

# Configure basic logging to print useful debug/info messages with timestamps
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class OutlineParser:
    """Main class responsible for parsing PDF files and detecting heading structures."""

    def __init__(self, validator_path: Optional[str] = None):
        """
        Initializes the parser with optional JSON schema validation.
        If a schema path is provided and valid, it loads the schema for future use.
        """
        self.validator = None
        if validator_path and os.path.exists(validator_path):
            try:
                with open(validator_path, 'r') as schema_file:
                    self.validator = json.load(schema_file)
            except Exception as err:
                log.warning(f"Failed to load schema: {err}")

    def get_doc_title(self, document: fitz.Document):
        """
        Tries to determine the title of the PDF document.
        First tries the PDF metadata, then scans the top lines of the first page.
        """
        meta = document.metadata
        if meta.get('title') and meta['title'].strip():
            return meta['title'].strip()  # Use title from metadata if available

        if len(document) > 0:
            pg = document[0]  # First page of the document
            content = pg.get_text()
            lines = [ln.strip() for ln in content.split('\n') if ln.strip()]

            # Scan through the top 10 lines for a plausible title
            for ln in lines[:10]:
                # Skip if it's just a page number or too short
                if 10 < len(ln) < 200 and not re.match(r'^\d+$|^page \d+|^\d+/\d+', ln.lower()):
                    return ln  # First good candidate as title

        return "Untitled Document"  # Fallback if no title found

    def classify_heading(self, txt: str, sz: float, flg: int, avg_sz: float):
        """
        Based on font size, boldness, and certain text patterns,
        classify text spans into headings (H1, H2, H3), or ignore them.
        """
        txt = txt.strip()
        if not txt or len(txt) < 3 or len(txt) > 200:
            return None  # Skip irrelevant or malformed text

        # Calculate size ratio compared to average font size in document
        ratio = sz / avg_sz if avg_sz > 0 else 1.0

        # PyMuPDF flag for bold text (bitmask)
        is_bold = bool(flg & 2**4)

        # Define regex patterns that typically match headings
        patterns = [
            r'^\d+\.?\s+[A-Z]',           # Numbered headings like "1. Introduction"
            r'^[A-Z][A-Z\s]{3,}$',        # ALL CAPS headings
            r'^Chapter\s+\d+',            # "Chapter 1", etc.
            r'^[IVX]+\.\s',               # Roman numeral outlines
            r'^\d+\.\d+\.?\s',            # Subsections like 1.1
            r'^\d+\.\d+\.\d+\.?\s'        # Deeper nesting like 1.2.3
        ]
        matched = any(re.match(p, txt) for p in patterns)

        # Determine heading level based on ratio and text pattern
        if ratio >= 1.4 or (ratio >= 1.2 and is_bold) or matched:
            if ratio >= 1.6 or re.match(r'^[A-Z][A-Z\s]{5,}$', txt):
                return "H1"
            elif ratio >= 1.3 or re.match(r'^\d+\.?\s+[A-Z]', txt):
                return "H2"
            else:
                return "H3"

        return None  # Not a heading

    def get_avg_font(self, document: fitz.Document):
        """
        Calculate average font size from the first few pages.
        This helps in detecting relative font size differences for headings.
        """
        sizes = []
        for idx in range(min(5, len(document))):  # Limit to first 5 pages
            pg = document[idx]
            content = pg.get_text("dict")["blocks"]
            for blk in content:
                if "lines" in blk:
                    for ln in blk["lines"]:
                        for span in ln["spans"]:
                            if span["size"] > 0:
                                sizes.append(span["size"])
        return sum(sizes) / len(sizes) if sizes else 12.0  # Default average

    def extract_outline(self, file_path):
        """
        Core method to extract the outline from the PDF:
        - Parses all pages
        - Identifies headings
        - Builds a structured dictionary of the outline
        """
        begin = time.time()
        try:
            doc = fitz.open(file_path)
            title = self.get_doc_title(doc)
            average = self.get_avg_font(doc)

            headings = []  # Will store the structured headings
            found = set()  # To avoid duplicates

            for pg_idx in range(len(doc)):
                pg = doc[pg_idx]
                content = pg.get_text("dict")["blocks"]

                for blk in content:
                    if "lines" in blk:
                        for ln in blk["lines"]:
                            for sp in ln["spans"]:
                                txt = sp["text"].strip()
                                sz = sp["size"]
                                flg = sp["flags"]

                                tag = self.classify_heading(txt, sz, flg, average)
                                if tag and txt:
                                    hkey = f"{tag}:{txt}:{pg_idx + 1}"  # Unique key
                                    if hkey not in found:
                                        headings.append({
                                            "level": tag,
                                            "text": txt,
                                            "page": pg_idx + 1
                                        })
                                        found.add(hkey)

            doc.close()

            data = {
                "title": title,
                "outline": headings
            }

            # Validate the extracted data if a schema is provided
            if self.validator:
                try:
                    jsonschema.validate(data, self.validator)
                    log.debug(f"Validated passed for {file_path}")
                except jsonschema.ValidationError as verr:
                    log.error(f"Validation failed for {file_path}: {verr}")

            duration = time.time() - begin
            log.info(f"Finished {file_path} in {duration:.2f}s, headings: {len(headings)}")
            return data

        except Exception as e:
            log.error(f"Failed to handle {file_path}: {e}")
            return {
                "title": f"Error with {Path(file_path).name}",
                "outline": []
            }


def run_outline_parser():
    """
    Entrypoint for the script:
    - Loads schema (if available)
    - Finds input PDFs
    - Runs the OutlineParser on each
    - Saves the extracted JSON outputs
    """
    log.info("Kickoff: Adobe Challenge PDF Parsing")

    # Define input/output directories (inside Docker)
    in_dir = Path("/app/input")
    out_dir = Path("/app/output")
    out_dir.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists

    # Load schema for output JSON structure validation
    schema_file = "/app/schema/output_schema.json"
    if not os.path.exists(schema_file):
        schema_file = None
        log.warning("Schema not found. Skipping validation.")

    # Create the parser instance
    parser = OutlineParser(schema_file)
    pdf_list = list(in_dir.glob("*.pdf"))

    if not pdf_list:
        log.warning("No PDFs detected in input directory")
        return

    log.info(f"Detected {len(pdf_list)} PDFs")
    started = time.time()

    for pdf_path in pdf_list:
        try:
            output = parser.extract_outline(str(pdf_path))

            # Save output to JSON file
            json_file = out_dir / f"{pdf_path.stem}.json"
            with open(json_file, "w", encoding='utf-8') as jf:
                json.dump(output, jf, indent=2, ensure_ascii=False)
            log.info(f"Saved: {pdf_path.name} -> {json_file.name}")
        except Exception as err:
            log.error(f"Could not process {pdf_path.name}: {err}")

    total_duration = time.time() - started
    log.info(f"Successful. Time: {total_duration:.2f}s")

# Entry point for command-line usage
if __name__ == "__main__":
    run_outline_parser()