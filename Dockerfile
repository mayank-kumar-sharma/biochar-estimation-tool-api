# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed by pyproj/shapely)
RUN apt-get update && apt-get install -y \
    build-essential \
    libproj-dev \
    proj-data \
    proj-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose the Render port
EXPOSE $PORT

# Default command (Render overrides with render.yaml if needed)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
