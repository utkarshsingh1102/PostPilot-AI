FROM python:3.12-slim

# System deps for Playwright and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser + its OS deps
RUN playwright install chromium && playwright install-deps chromium

# Copy application source
COPY . .

# Directory for AI-generated images (also mountable as a Docker volume / Render Disk)
RUN mkdir -p generated_images

# Make the startup script executable
RUN chmod +x start.sh

EXPOSE 8000

# start.sh honours the $PORT env var injected by Render (falls back to 8000).
CMD ["./start.sh"]
