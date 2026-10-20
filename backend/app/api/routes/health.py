"""Liveness check, open without authentication."""

from fastapi import APIRouter

API_VERSION = "0.1.0"

router = APIRouter()


@router.get("/api/health")
def health():
    return {"status": "ok", "version": API_VERSION}
