"""LangGraph checkpoint storage: PostgreSQL when the app runs on it, SQLite otherwise."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver


def checkpoint_url(database_url: str) -> str | None:
    """Libpq URL for a PostgreSQL SQLAlchemy URL (drops the "+driver" suffix), else None."""
    scheme, separator, rest = database_url.partition("://")
    if not separator or scheme.split("+")[0] not in ("postgresql", "postgres"):
        return None
    return f"postgresql://{rest}"


@contextmanager
def open_checkpointer(database_url: str, data_dir: Path) -> Iterator[BaseCheckpointSaver]:
    url = checkpoint_url(database_url)
    if url:
        from langgraph.checkpoint.postgres import PostgresSaver

        with PostgresSaver.from_conn_string(url) as saver:
            saver.setup()
            yield saver
        return
    with closing(sqlite3.connect(str(data_dir / "checkpoints.db"), check_same_thread=False)) as conn:
        yield SqliteSaver(conn)
