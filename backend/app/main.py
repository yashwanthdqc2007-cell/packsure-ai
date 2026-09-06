import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import analytics, history, rules, scans
from app.core.config import settings


def _resolve_storage_directory() -> str:
    """Resolve storage directory path robustly across repository root and backend CWD."""
    package_storage = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage"))
    if os.path.exists(package_storage):
        return package_storage
    cwd_storage = os.path.abspath("storage")
    if os.path.exists(cwd_storage):
        return cwd_storage
    os.makedirs(package_storage, exist_ok=True)
    return package_storage


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

for route in analytics.router.routes:
    app.routes.append(route)

# Mount local runtime storage directory for visual evidence and report artifacts
_storage_dir = _resolve_storage_directory()
app.mount("/storage", StaticFiles(directory=_storage_dir), name="storage")
