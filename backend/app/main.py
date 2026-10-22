"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router

VITE_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app = FastAPI(
    title="PA Platform API",
    description="Synthetic-data pharmacy prior authorization assistant API.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=VITE_DEV_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router, prefix="/api")
