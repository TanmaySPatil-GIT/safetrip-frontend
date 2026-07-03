FROM python:3.11-slim

WORKDIR /app

# Install Node.js (required to compile Reflex frontend), unzip, and curl
RUN apt-get update && apt-get install -y curl unzip && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize Reflex (compiles frontend dependencies)
RUN reflex init

# Expose port (Render will configure the PORT environment variable)
EXPOSE 10000

# Start Reflex backend-only in production mode
CMD ["sh", "-c", "reflex run --env prod --backend-only --backend-port $PORT --backend-host 0.0.0.0"]