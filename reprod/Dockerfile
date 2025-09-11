# file: Dockerfile
FROM python:3.11-slim

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps needed to build cartopy on aarch64 
# you may not need this if you are not on aarch64
# We kept this on, as it enhances multiarch compatibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    gcc \
    pkg-config \
  && rm -rf /var/lib/apt/lists/*


COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY src ./src
COPY entrypoint.sh ./entrypoint.sh


# entrypoint executable
RUN chmod +x /app/entrypoint.sh


RUN mkdir -p /app/datasets

# tini for proper signal handling; then entrypoint running reproduction pipeline
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]