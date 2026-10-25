"""Main FastAPI application entrypoint for Windline."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.app.config import APP_DESCRIPTION, APP_NAME, REPO_ROOT, VERSION
from backend.app.loader import DataLoader
from backend.app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler: pre-load immutable dataset snapshots into memory upon startup."""
    # Eagerly load snapshots so subsequent requests are served instantly from memory
    loader = DataLoader.get_instance()
    loader.load_all()
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=VERSION,
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router)

# Mount frontend if build directory exists and app.frontend is supported
frontend_dist = REPO_ROOT / "frontend" / "dist"
if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file() and hasattr(app, "frontend"):
    app.frontend("/", directory=str(frontend_dist))
else:
    @app.get("/", include_in_schema=False)
    def root():
        """Redirect root to API documentation."""
        return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)

