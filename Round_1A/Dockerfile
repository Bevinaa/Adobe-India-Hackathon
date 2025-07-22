# Adobe Hackathon Challenge 1A: PDF Outline Extraction

FROM --platform=linux/amd64 python:3.10-slim

# Metadata for documentation and traceability
LABEL maintainer="Bevina R bevina2210766@ssn.edu.in"
LABEL description="PDF outline extractor using PyMuPDF for Adobe Hackathon Challenge 1A"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install system dependencies required for building and running PyMuPDF
RUN apt-get update && apt-get install -y \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code and schema
COPY process_pdfs.py .
COPY test_pdf.py .
COPY sample_dataset/schema/ /app/sample_dataset/schema/

# Create input/output directories (if not mounted externally)
RUN mkdir -p /app/input /app/output

# Default command to run the final script
CMD ["python", "process_pdf.py"]