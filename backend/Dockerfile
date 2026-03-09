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

# Directory for AI-generated images (also mountable as a Docker volume)
RUN mkdir -p generated_images

EXPOSE 8000

# Run with uvicorn; override CMD or use docker-compose for hot-reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
