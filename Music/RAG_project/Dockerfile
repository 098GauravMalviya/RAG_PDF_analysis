# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for compiling some packages (like lxml if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Expose the internal ports for both services
EXPOSE 8000
EXPOSE 8501

# Set default configuration variables for deployment
ENV HOST=0.0.0.0
ENV BACKEND_PORT=8000
ENV FRONTEND_PORT=8501
ENV BACKEND_URL=http://localhost:8000

# Run the unified launcher script
CMD ["python", "run_system.py"]
