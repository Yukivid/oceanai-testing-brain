"""
FastAPI application entrypoint for deployment.
This file imports the FastAPI app from backend/main.py to make it discoverable by deployment platforms.
"""
from backend.main import app

# Export the app for deployment platforms
__all__ = ["app"]

