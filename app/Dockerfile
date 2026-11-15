# ============================================================
# Base Image
#
# Use the official slim Python image to reduce attack surface
# and keep image size smaller than the full Python image.
# ============================================================

FROM python:3.13-slim

# ============================================================
# Environment Settings
#
# PYTHONDONTWRITEBYTECODE
#   Prevents creation of .pyc files.
#
# PYTHONUNBUFFERED
#   Ensures logs are immediately written to stdout for
#   Kubernetes log collection.
# ============================================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ============================================================
# Create Application User
#
# Create a dedicated non-root user with a fixed UID/GID.
#
# UID 1000 is explicitly referenced by the Kubernetes
# securityContext:
#
#   runAsNonRoot: true
#   runAsUser: 1000
#   runAsGroup: 1000
#
# This allows Kubernetes to verify the container is not
# running as root.
# ============================================================

RUN groupadd \
    --gid 1000 \
    appuser \
    && useradd \
    --uid 1000 \
    --gid 1000 \
    --create-home \
    --shell /bin/bash \
    appuser

# ============================================================
# Application Directory
#
# Create the working directory used by the application.
# ============================================================

WORKDIR /app

# ============================================================
# Dependency Installation
#
# Copy requirements separately so Docker can reuse cached
# dependency layers when application code changes.
#
# This significantly speeds up rebuilds.
# ============================================================

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    -r requirements.txt

# ============================================================
# Copy Application Source
# ============================================================

COPY . .

# ============================================================
# Runtime Directories
#
# The application writes temporary recording files under:
#
#   output/
#
# Create the directory during image build and assign
# ownership to the application user.
#
# This prevents:
#
#   PermissionError: [Errno 13]
#
# when running as a non-root container.
# ============================================================

RUN mkdir -p /app/output \
    && chown -R 1000:1000 /app

# ============================================================
# Switch To Non-Root User
#
# All application processes run as UID/GID 1000.
# ============================================================

USER 1000:1000

# ============================================================
# Exposed Port
#
# Used for:
#
#   /metrics
#   /health/live
#   /health/ready
# ============================================================

EXPOSE 8000

# ============================================================
# Container Entrypoint
#
# Starts the synthetic recording generator.
# ============================================================

CMD ["python", "generator.py"]