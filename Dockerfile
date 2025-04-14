# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for newspaper3k
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies in stages to better debug failures
RUN pip install --upgrade pip && \
    pip install --no-cache-dir newspaper3k aiohttp nltk && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data required by newspaper3k
RUN python -c "import nltk; nltk.download('punkt')"

# Copy the rest of the application code into the container
COPY . .

# Command to run the application
CMD ["python", "discord_bot.py"]