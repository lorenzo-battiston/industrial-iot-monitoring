FROM python:3.11-slim

# Install system dependencies (if any extensions are needed later)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 5001

ENV DB_HOST=postgres \
    DB_PORT=5432 \
    DB_DATABASE=iot_analytics \
    DB_USER=iot_user \
    DB_PASSWORD=iot_password

# Use unbuffered output for easier logging
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"] 