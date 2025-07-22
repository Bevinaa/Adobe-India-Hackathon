"""
Adobe Hackathon Challenge 1B: Persona - Driven Document Intelligence 

This script processes PDF collections based on a persona-task input
configuration (challenge1b_input.json) and produces a relevance-ranked
structured JSON output. It extracts content using PyMuPDF, applies a
custom TF-IDF engine for semantic matching, and identifies the most
important sections and refined subsections.
"""

import os, json, sys
import time
from pathlib import Path
from typing import List, Dict, Any
import logging
import fitz 
from datetime import datetime
import re, math
from collections import Counter

# Add Round_1A directory to import path to reuse the OutlineParser
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Round_1A'))
from process_pdf import OutlineParser

# Configure logging to show timestamp and level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class TextScorer:
    """
    TF-IDF-based scoring engine that ranks text content based on relevance
    to a given persona and goal. Used to identify the most relevant sections
    in a PDF document.
    """
    def __init__(self):
        self.docs = []  # List of tokenized documents
        self.terms = set()  # Unique terms across all documents
        self.inverse_doc_freq = {}  # IDF values for each term

    def clean_text(self, raw):
        """Lowercase and tokenize the text while removing common stopwords."""
        raw = raw.lower()
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', raw)
        exclude = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was'}
        return [t for t in tokens if t not in exclude]

    def build_index(self, entries):
        """Builds TF-IDF index from the given list of text passages."""
        self.docs = []
        for entry in entries:
            tokens = self.clean_text(entry)
            self.docs.append(tokens)
            self.terms.update(tokens)
        total = len(self.docs)
        for term in self.terms:
            cnt = sum(1 for d in self.docs if term in d)
            self.inverse_doc_freq[term] = math.log(total / (cnt + 1))

    def vectorize(self, passage):
        """Converts a text passage into a weighted TF-IDF vector."""
        tokens = self.clean_text(passage)
        freq = Counter(tokens)
        total = len(tokens)
        return {t: (freq.get(t, 0) / total if total > 0 else 0) * self.inverse_doc_freq.get(t, 0) for t in self.terms}

    def compare_vectors(self, vec_a, vec_b):
        """Computes cosine similarity between two TF-IDF vectors."""
        shared = set(vec_a.keys()) & set(vec_b.keys())
        if not shared:
            return 0.0
        dot = sum(vec_a[t] * vec_b[t] for t in shared)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class PDFPersonaAnalyzer:
    """
    Main engine that analyzes PDFs against a given persona's goal,
    scores sections by relevance, and returns ranked results.
    """
    def __init__(self):
        self.extractor = OutlineParser()  # Reuse existing PDF parser from Round_1A
        self.scorer = TextScorer()  # Scoring engine for relevance evaluation

    def fetch_pdf_content(self, path):
        """
        Extracts and structures content from the PDF:
        - Splits into sections and subsections
        - Extracts font size and boldness to detect headings
        """
        try:
            file = fitz.open(path)
            data = {
                "title": self.extractor.extract_title(file),
                "outline": [],
                "sections": [],
                "full_text": ""
            }
            full = []
            current = None

            for page_num in range(len(file)):
                page = file[page_num]
                text = page.get_text()
                full.append(text)
                blocks = page.get_text("dict")["blocks"]

                for block in blocks:
                    if "lines" in block:
                        for line in block["lines"]:
                            line_text = " ".join(span["text"].strip() for span in line["spans"] if span["text"].strip())
                            fonts = [span for span in line["spans"] if span["text"].strip()]
                            avg_size = sum(f["size"] for f in fonts) / len(fonts) if fonts else 12
                            is_bold = any(f["size"] > 13 or f["flags"] & 16 for f in fonts)

                            # Detect start of a new section
                            if is_bold and len(line_text.strip()) < 150:
                                if current:
                                    data["sections"].append(current)
                                current = {
                                    "title": line_text.strip(),
                                    "page": page_num + 1,
                                    "content": "",
                                    "subsections": []
                                }
                            elif current:
                                # Accumulate text into section or subsection
                                current["content"] += line_text
                                if any(f["flags"] & 16 for f in fonts) and 10 < len(line_text.strip()) < 100:
                                    current["subsections"].append({
                                        "title": line_text.strip(),
                                        "page": page_num + 1,
                                        "content": ""
                                    })

            if current:
                data["sections"].append(current)

            data["full_text"] = "\n".join(full)
            file.close()
            return data

        except Exception as err:
            log.error(f"Failed to read {path}: {err}")
            return {"title": f"Error: {Path(path).name}", "outline": [], "sections": [], "full_text": ""}

    def evaluate(self, config_path, pdf_folder):
        """
        Main evaluation logic that:
        - Loads persona and task config
        - Extracts content from relevant PDFs
        - Scores sections based on semantic relevance
        - Returns top-ranked sections and subsections
        """
        start = time.time()
        with open(config_path, 'r') as j:
            config = json.load(j)

        persona_role = config["persona"]["role"]
        goal = config["job_to_be_done"]["task"]
        inputs = config["documents"]

        log.info(f"Persona: {persona_role}, Task: {goal}")

        all_pdfs = {}
        text_blobs = []

        for doc in inputs:
            file_path = os.path.join(pdf_folder, doc["filename"])
            if os.path.exists(file_path):
                details = self.fetch_pdf_content(file_path)
                all_pdfs[doc["filename"]] = details
                content = details["full_text"] + " ".join(s["title"] + " " + s["content"] for s in details["sections"])
                text_blobs.append(content)

        self.scorer.build_index(text_blobs)

        # Create a semantic query vector using persona and task
        query_vec = self.scorer.vectorize(f"{persona_role} {goal}")

        all_sections = []
        refined_subs = []

        for fname, doc_data in all_pdfs.items():
            for sec in doc_data["sections"]:
                combined = f"{sec['title']} {sec['content']}"
                vec = self.scorer.vectorize(combined)
                score = self.scorer.compare_vectors(query_vec, vec)
                all_sections.append({
                    "document": fname,
                    "section_title": sec["title"],
                    "page_number": sec["page"],
                    "relevance_score": score,
                    "content": sec["content"]
                })

                if score > 0.1 and sec["content"].strip():
                    refined_subs.append({
                        "document": fname,
                        "refined_text": sec["content"].strip()[:1000],
                        "page_number": sec["page"]
                    })

        # Sort all sections based on score (descending)
        all_sections.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Select top 5 relevant sections
        top = [{
            "document": s["document"],
            "section_title": s["section_title"],
            "importance_rank": i + 1,
            "page_number": s["page_number"]
        } for i, s in enumerate(all_sections[:5])]

        output = {
            "metadata": {
                "input_documents": [d["filename"] for d in inputs],
                "persona": persona_role,
                "job_to_be_done": goal,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": top,
            "subsection_analysis": refined_subs[:5]
        }

        log.info(f"Finished in {time.time() - start:.2f}s")
        return output


def handle_dir(folder):
    """Wrapper to load input, run evaluation, and store output as JSON."""
    input_json = os.path.join(folder, "challenge1b_input.json")
    pdfs = os.path.join(folder, "PDFs")
    output_json = os.path.join(folder, "challenge1b_output.json")

    if not os.path.exists(input_json) or not os.path.exists(pdfs):
        log.error("Missing required files.")
        return

    engine = PDFPersonaAnalyzer()
    result = engine.evaluate(input_json, pdfs)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    log.info(f"Results stored in {output_json}")


def kickstart():
    """Main entrypoint: scans all folders starting with 'Collection' and processes them."""
    base_path = Path("/app/collections")

    if not base_path.exists():
        base_path = Path(".")

    for folder in base_path.iterdir():
        if folder.is_dir() and folder.name.startswith("Collection"):
            log.info(f"Now processing: {folder.name}")
            handle_dir(str(folder))

# Entry point for command-line usage
if __name__ == "__main__":
    kickstart()