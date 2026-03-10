import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.routes import api, pages

BASE_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

settings = get_settings()

logging.info("Starting Shalomax on port %s", os.environ.get("PORT", "8000 (default)"))

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Shalomax",
    description="Rastreo de envíos Shalom",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=500)

# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

# Routes
app.include_router(pages.router)
app.include_router(api.router)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Error handlers
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse("404.html", {
        "request": request,
        "title": "No encontrado - Shalomax",
    }, status_code=404)


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return templates.TemplateResponse("500.html", {
        "request": request,
        "title": "Error - Shalomax",
    }, status_code=500)
