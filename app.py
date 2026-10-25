"""Windline unified application entrypoint.

This module provides the root FastAPI application instance for local execution
and Docker production containers. It imports the configured FastAPI app
from backend.app.main and ensures the pre-built React frontend is served at '/'.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'backend' package imports resolve cleanly
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import APP_NAME, VERSION
from backend.app.main import app

# Expose app for ASGI servers (Uvicorn / Vercel Python runtime)
__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    print(f"Starting {APP_NAME} v{VERSION} on http://0.0.0.0:8000 ...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
