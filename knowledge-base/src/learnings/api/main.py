"""
Main entry point for the Learnings API.

This module starts the FastAPI server with all routes configured.
"""

from src.learnings.api.routes import app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
