"""
Adobe Hackathon 
Round 1A: Understand Your Document
Round 1B: Persona-Driven Document Intelligence 

SUBMITTED BY : Team_BD (Bevina R, Deepitha P - SSNCE)
"""

import os, json, jsonschema, time, re
from pathlib import Path
from typing import Optional
import logging
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class OutlineParser:
    def __init__(self, validator_path: Optional[str] = None):
        self.validator = None
        if validator_path and os.path.exists(validator_path):
            try:
                with open(validator_path, 'r') as schema_file:
                    self.validator = json.load(schema_file)
            except Exception as err:
                log.warning(f"Failed to load schema: {err}")

    def get_doc_title(self, document: fitz.Document):
        meta = document.metadata
        if meta.get('title') and meta['title'].strip():
            return meta['title'].strip()

        if len(document) > 0:
            pg = document[0]
            content = pg.get_text()
            lines = [ln.strip() for ln in content.split('\n') if ln.strip()]
            for ln in lines[:10]:
                if 10 < len(ln) < 200 and not re.match(r'^\d+$|^page \d+|^\d+/\d+', ln.lower()):
                    return ln
        return "Untitled Document"

    def classify_heading(self, txt: str, sz: float, flg: int, avg_sz: float):
        txt = txt.strip()
        if not txt or len(txt) < 3 or len(txt) > 200:
            return None

        ratio = sz / avg_sz if avg_sz > 0 else 1.0
        is_bold = bool(flg & 2**4)

        patterns = [
            r'^\d+\.?\s+[A-Z]',
            r'^[A-Z][A-Z\s]{3,}$',
            r'^Chapter\s+\d+',
            r'^[IVX]+\.\s',
            r'^\d+\.\d+\.?\s',
            r'^\d+\.\d+\.\d+\.?\s'
        ]
        matched = any(re.match(p, txt) for p in patterns)

        if ratio >= 1.4 or (ratio >= 1.2 and is_bold) or matched:
            if ratio >= 1.6 or re.match(r'^[A-Z][A-Z\s]{5,}$', txt):
                return "H1"
            elif ratio >= 1.3 or re.match(r'^\d+\.?\s+[A-Z]', txt):
                return "H2"
            else:
                return "H3"

        return None

    def get_avg_font(self, document: fitz.Document):
        sizes = []
        for idx in range(min(5, len(document))):
            pg = document[idx]
            content = pg.get_text("dict")["blocks"]
            for blk in content:
                if "lines" in blk:
                    for ln in blk["lines"]:
                        for span in ln["spans"]:
                            if span["size"] > 0:
                                sizes.append(span["size"])
        return sum(sizes) / len(sizes) if sizes else 12.0

    def extract_outline(self, file_path):
        begin = time.time()
        try:
            doc = fitz.open(file_path)
            title = self.get_doc_title(doc)
            average = self.get_avg_font(doc)

            headings = []
            found = set()

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
                                    hkey = f"{tag}:{txt}:{pg_idx + 1}"
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

            if self.validator:
                try:
                    jsonschema.validate(data, self.validator)
                    log.debug(f"Validation passed for {file_path}")
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
    log.info("Kickoff: Adobe Challenge PDF Parsing")

    # Absolute base directory where this script is located
    base_dir = Path(__file__).resolve().parent
    in_dir = base_dir / "sample_dataset" / "pdfs"
    out_dir = base_dir / "sample_dataset" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load schema
    schema_path = base_dir / "schema" / "output_schema.json"
    if not schema_path.exists():
        log.warning("Schema not found. Skipping validation.")
        schema = None
    else:
        with open(schema_path, "r") as f:
            schema = json.load(f)

    # Show where we are looking
    log.info(f"Looking for PDFs in: {in_dir.resolve()}")

    pdf_files = list(in_dir.glob("*.pdf"))
    if not pdf_files:
        log.warning("No PDFs detected in input directory")
        return
    else:
        log.info(f"Found {len(pdf_files)} PDFs to process: {[p.name for p in pdf_files]}")

    parser = OutlineParser(validator_path=str(schema_path) if schema else None)

    started = time.time()
    for pdf_path in pdf_files:
        try:
            output = parser.extract_outline(str(pdf_path))

            json_file = out_dir / f"{pdf_path.stem}.json"
            with open(json_file, "w", encoding='utf-8') as jf:
                json.dump(output, jf, indent=2, ensure_ascii=False)
            log.info(f"Saved: {pdf_path.name} -> {json_file.name}")
        except Exception as err:
            log.error(f"Could not process {pdf_path.name}: {err}")

    total_duration = time.time() - started
    log.info(f"Processing complete. Total time: {total_duration:.2f}s")


# Entry point
if __name__ == "__main__":
    run_outline_parser()
