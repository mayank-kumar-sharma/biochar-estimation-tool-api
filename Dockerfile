# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for shapely & pyproj
RUN apt-get update && apt-get install -y \
    build-essential \
    libproj-dev \
    proj-data \
    proj-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching layers)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Render provides $PORT env automatically; expose for documentation
EXPOSE 8000

# Start FastAPI app with uvicorn
# IMPORTANT: use "exec form" so signals are passed correctly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


