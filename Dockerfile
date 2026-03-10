FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Pillow and compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ app/

# Create cache directory
RUN mkdir -p recibos_cache

# Verify imports work (fail fast at build time)
RUN python -c "from app.main import app; print('Import OK')"

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
