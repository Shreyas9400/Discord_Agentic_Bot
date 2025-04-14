# Use the official SearXNG image as base
FROM searxng/searxng:latest

# Copy your custom settings file into the correct location
COPY settings.yml /etc/searxng/settings.yml
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install dependencies using Alpine's package manager
RUN apk add --no-cache \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt-dev \
    libjpeg-turbo-dev \
    zlib-dev \
    libpng-dev \
    curl \
    wget \
    build-base \
    libffi-dev \
    musl-dev \
    openssl-dev \
    python3

# Create a virtual environment to avoid system-wide Python package installation issues
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies in the virtual environment
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Modify settings.yml to allow JSON format
RUN sed -i 's/    - html/    - html\n    - json/' /etc/searxng/settings.yml

# Copy the rest of your application code
COPY . .

# Start the bot
CMD ["python", "discord_bot.py"]
