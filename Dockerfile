# ==============================================================================
# PUMP & DUMP REVERSION BOT - Docker Image
# Tarih: 18 Şubat 2026
# Northflank deployment için optimize edilmiştir
# ==============================================================================

# Build Stage
FROM python:3.12-slim-bookworm as builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==============================================================================
# Final Stage - Production Image
# ==============================================================================
FROM python:3.12-slim-bookworm

WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=UTC

# Runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy application files
COPY 18.02.2026.py .
COPY src/ ./src/
COPY run.py .
COPY config_example.py .

# Create logs directory
RUN mkdir -p /app/logs && chmod 755 /app/logs

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "print('OK')" || exit 1

# Default command - run main strategy file
CMD ["python", "-u", "18.02.2026.py"]
