from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kyc_engine.api.routes import kyc
from kyc_engine.core.config import settings
from kyc_engine.db.session import create_tables
from kyc_engine.models.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
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
    kyc.router,
    prefix=f"/api/{settings.api_version}/kyc",
    tags=["KYC"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.api_version,
    )
