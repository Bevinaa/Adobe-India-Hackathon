# Adobe Hackathon Challenge 1B: Persona-Driven PDF Analysis

FROM --platform=linux/amd64 python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy Round_1A folder (needed by sys.path and import)
COPY ../Round_1A /app/Round_1A

# Copy the Challenge 1B analyzer script
COPY analyze_collections.py .

# Create collections mount point
RUN mkdir -p /app/collections

# Default command
CMD ["python", "analyze_collections.py"]
