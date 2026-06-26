# monitoring-agent/backend/Dockerfile
# Read-only container monitoring API. Mirrors the compliance backend style
# (python:3.11-slim, requirements-first for layer caching) and additionally
# runs as a non-root user and trusts an optional org CA bundle.
FROM docker.io/library/python:3.11-slim

WORKDIR /app

# Optional org CA bundle: if a *.crt is COPYed into ./certs it is installed into
# the system trust store at build time. The directory is created empty so the
# build still works when no cert is present (the trailing "|| true" is a no-op
# guard when ./certs holds only the .gitkeep).
COPY certs/ /usr/local/share/ca-certificates/monitoring/
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates || true \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app ./app

# Run as a non-root user (read-only API; no need for root).
RUN useradd --create-home --uid 10002 monitor \
    && chown -R monitor:monitor /app
USER monitor

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
