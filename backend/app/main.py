"""ASGI entry point: `uvicorn app.main:app`."""

from app.api.application import create_app
from app.core.config import settings

app = create_app(settings())
