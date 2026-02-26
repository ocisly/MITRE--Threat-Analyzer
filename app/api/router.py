"""Aggregates all REST API routers under /api/v1."""
from fastapi import APIRouter
from app.api.browse import router as browse_router
from app.api.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(browse_router)
api_router.include_router(health_router)
