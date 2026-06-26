"""Make `import app` resolve regardless of pytest's invocation directory.

The backend package lives at monitoring-agent/backend/app. Adding this file's
directory (monitoring-agent/backend) to sys.path lets `from app import ...`
work whether pytest is run from the repo root or from backend/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
