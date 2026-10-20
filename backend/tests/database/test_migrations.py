import os
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.database.models import Base
from app.database.session import make_sessions


def test_fresh_alembic_schema_matches_models(tmp_path):
    url = f"sqlite:///{tmp_path}/migration.db"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "JWT_SECRET": "migration-test-secret-1234567890123456789",
            "DATABASE_URL": url,
            "DATA_DIR": str(tmp_path),
        },
    )
    engine, _ = make_sessions(url)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()
