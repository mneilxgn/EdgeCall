"""Vercel serverless entry point — imports the FastAPI app."""
import sys
import os

# Make backend modules importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app  # noqa: F401 — Vercel picks up `app`
