# ==========================================
# VisualCrypto Production Dockerfile
# ==========================================
FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    HOST=0.0.0.0 \
    FLASK_ENV=production

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code
COPY . .

# Create non-root application user and establish correct directory permissions
RUN useradd -m -u 1000 appuser && \
    mkdir -p web_app/static/uploads web_app/static/output scripts/images/output && \
    chown -R appuser:appuser /app

# Switch to non-root user for security
USER appuser

# Expose web service port
EXPOSE 5000

# Container health monitoring
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Launch with production WSGI server (Gunicorn)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 4 --threads 2 --timeout 120 wsgi:app"]
