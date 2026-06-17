"""
seo-agent/backend/app/main.py

Placeholder FastAPI backend for the SEO Agent.
Replace with the real application. Served at /seo/api/ via nginx.
"""
import os

from fastapi import FastAPI

app = FastAPI(title="SEO Agent API")

DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "")


@app.get("/")
def root():
    return {"agent": "seo", "status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database_configured": bool(DATABASE_URL),
        "redis_configured": bool(REDIS_URL),
    }
