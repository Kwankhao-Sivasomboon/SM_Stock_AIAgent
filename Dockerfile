# Use official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for some pandas/numpy operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port (Cloud Run defaults to 8080)
EXPOSE 8080

# Define execution command (Start Flask with Gunicorn)
# Use 1 worker + threads to handle concurrent requests (for Fire-and-Forget)
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 src.app:app
