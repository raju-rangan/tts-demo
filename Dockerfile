# Use official lightweight Python 3.13 image
FROM python:3.13-slim

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Copy dependency specifications first for optimal Docker layer caching
COPY pyproject.toml requirements.txt ./

# Install dependencies (lameenc installs prebuilt manylinux wheel in seconds)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source tree and static assets
COPY . .

# Install local package in editable mode
RUN pip install --no-cache-dir -e .

# Expose default Cloud Run port
EXPOSE 8080

# Cloud Run injects $PORT (default 8080). Bind Uvicorn to 0.0.0.0:$PORT
CMD ["sh", "-c", "uvicorn src.ui.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
