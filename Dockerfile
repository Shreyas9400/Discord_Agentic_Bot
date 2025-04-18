FROM python:3.11-slim

# Install system dependencies for newspaper3k, lxml, and others
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        gcc \
        python3-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        libffi-dev \
        libssl-dev \
        libpq-dev \
        curl \
        git \
        poppler-utils \
        tesseract-ocr \
        pkg-config \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose any ports if needed (Discord bots usually don't need to expose ports)
# EXPOSE 8000

# Set environment variables (override with docker run -e or .env file)
# ENV DISCORD_TOKEN=your_token_here
# ENV GOOGLE_API_KEY=your_google_api_key_here

# Default command to run the bot
CMD ["python", "discord_bot.py"]
