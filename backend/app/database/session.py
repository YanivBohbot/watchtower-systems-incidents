"""Database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_sessions(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def sqlite_options(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    return engine, sessionmaker(engine, expire_on_commit=False)
