# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime - Lean production image
# ============================================
FROM python:3.11-slim AS runtime

LABEL maintainer="Network Admin"
LABEL description="Network Configuration Manager for Nokia SR Linux"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY netconfig.py .
COPY src/ src/
COPY inventory/ inventory/
COPY configs/ configs/
COPY lab/ lab/

# Create directories for logs and backups
RUN mkdir -p logs configs/backups

# Default environment variables
# NOTE: For production, pass credentials at runtime via --env-file or -e flags
# These defaults are for the Containerlab lab environment only
ENV DEVICE_USERNAME=admin
ENV DEVICE_PASSWORD=NokiaSrl1!
ENV LOG_LEVEL=INFO
ENV BACKUP_DIR=configs/backups
ENV LOGS_DIR=logs
ENV SSH_TIMEOUT=30
ENV COMMAND_TIMEOUT=60

ENTRYPOINT ["python3", "netconfig.py"]
CMD ["--help"]
