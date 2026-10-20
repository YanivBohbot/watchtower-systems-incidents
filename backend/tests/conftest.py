import pytest


@pytest.fixture
def app_env(monkeypatch, tmp_path):
    """Environment for modules that read settings at import time (the Celery worker, the ASGI entry)."""
    monkeypatch.setenv("JWT_SECRET", "entry-test-secret-not-for-production-1234")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/entry.db")
    from app.core.config import settings

    settings.cache_clear()
    yield
    settings.cache_clear()
