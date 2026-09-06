"""
PackSure AI — FastAPI Application Entry Point.

Initializes the FastAPI app, configures CORS, and registers API routers for:
- /api/v1/scans
- /api/v1/rules
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import history, rules, scans
from app.core.config import settings

app = FastAPI(
    title="PackSure AI",
    description="Legal Metrology Packaged Commodities Compliance System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "service": "packsure-ai-backend"}


# Register Phase 1, 7 & 8 API Routes
for route in scans.router.routes:
    app.routes.append(route)

for route in rules.router.routes:
    app.routes.append(route)

for route in history.router.routes:
    app.routes.append(route)
