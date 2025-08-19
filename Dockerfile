# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for shapely/pyproj)
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

# Render automatically sets $PORT, we just expose it
EXPOSE 8000

# Start FastAPI app with uvicorn
# Use "exec form" and pass PORT from environment variable
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

