import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kyc_engine.api.routes import auth, kyc, credit, aml
from kyc_engine.core.config import settings
from kyc_engine.db.session import create_tables
from kyc_engine.models.schemas import HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_tables()
        logger.info("Database tables ready.")
    except Exception as e:
        # Log but don't crash — allows /health to respond even if DB is misconfigured.
        # KYC endpoints will return 500 until DATABASE_URL is set correctly.
        logger.error(f"Database connection failed on startup: {e}")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description=(
        "AI-powered KYC document extraction and cross-validation engine. "
        "Extracts structured fields from PAN cards, Aadhaar cards, and bank statements; "
        "validates consistency across documents; flags mismatches for manual review."
    ),
    lifespan=lifespan,
    # Disable docs in production — sensitive document data must not be exposed via Swagger UI
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to bank's internal domain before deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth.router,
    prefix=f"/api/{settings.api_version}/auth",
    tags=["Auth"],
)

app.include_router(
    kyc.router,
    prefix=f"/api/{settings.api_version}/kyc",
    tags=["KYC"],
)

app.include_router(
    credit.router,
    prefix=f"/api/{settings.api_version}/credit",
    tags=["Credit Underwriting"],
)

app.include_router(
    aml.router,
    prefix=f"/api/{settings.api_version}/aml",
    tags=["AML Compliance"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.api_version,
    )


# ── Serve React frontend ───────────────────────────────────────────────────────
# Mount built JS/CSS assets. Must come after all /api routes are registered.
_static = Path("static")
if _static.exists():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(_static / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Serve any static file that exists (e.g. vite.svg); fall back to index.html for SPA routing
        candidate = _static / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
