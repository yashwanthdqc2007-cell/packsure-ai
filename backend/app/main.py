"""
PackSure AI — FastAPI Application Entry Point

This module initializes the FastAPI app, configures CORS,
and registers all API routers.

TODO (Backend Dev):
- Register route handlers for scans, history, analytics, rules
- Add startup/shutdown lifecycle hooks for DB and Gemini client
- Add global exception handlers
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PackSure AI",
    description="Legal Metrology Packaged Commodities Compliance System",
    version="0.1.0",
)

# TODO: Read allowed origins from config / .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "service": "packsure-ai-backend"}


# TODO: Register routers here after they are implemented
# from app.api.routes import scans, history, analytics, rules
# app.include_router(scans.router, prefix="/api/v1")
# app.include_router(history.router, prefix="/api/v1")
# app.include_router(analytics.router, prefix="/api/v1")
# app.include_router(rules.router, prefix="/api/v1")
