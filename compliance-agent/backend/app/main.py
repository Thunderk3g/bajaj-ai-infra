"""
compliance-agent/backend/app/main.py

Placeholder FastAPI backend for the Compliance Agent.
Replace with the real application. Served at /compliance/api/ via nginx.
"""
import os

from fastapi import FastAPI

app = FastAPI(title="Compliance Agent API")

DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "")


@app.get("/")
def root():
    return {"agent": "compliance", "status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database_configured": bool(DATABASE_URL),
        "redis_configured": bool(REDIS_URL),
    }
