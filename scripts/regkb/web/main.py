"""
FastAPI application for Regulatory Knowledge Base.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from regkb.web.dependencies import get_flashed_messages
from regkb.web.lifespan import lifespan

# Load .env before anything else
load_dotenv()

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Create app
app = FastAPI(
    title="Regulatory Knowledge Base",
    description="Medical device regulatory document management",
    version="1.0.0",
    lifespan=lifespan,
)

# Session middleware for flash messages
secret_key = os.environ.get("REGKB_SECRET_KEY", "regkb-secret-change-in-production")
app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    session_cookie="regkb_session",
    max_age=3600,
)

# Static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# Make flash messages available in templates
@app.middleware("http")
async def add_template_globals(request: Request, call_next):
    request.state.get_flashed_messages = lambda: get_flashed_messages(request)
    response = await call_next(request)
    return response


# Root redirect
@app.get("/")
async def root():
    return RedirectResponse(url="/search", status_code=302)


# Import and register routes
# Note: documents must be registered before browse so /documents/add matches
# before /documents/{doc_id}
from regkb.web.health import router as health_router
from regkb.web.routes import admin, browse, diff, documents, gaps, intel, search, versions

app.include_router(health_router)
app.include_router(search.router)
app.include_router(diff.router)
app.include_router(versions.router)
app.include_router(gaps.router)
app.include_router(intel.router)
app.include_router(documents.router)  # Must be before browse
app.include_router(browse.router)
app.include_router(admin.router, prefix="/admin")
