"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes_health import router as health_router

app = FastAPI(
    title="PA Platform API",
    description="Synthetic-data pharmacy prior authorization assistant API.",
    version="0.1.0",
)
app.include_router(health_router, prefix="/api")
