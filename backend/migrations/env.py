from alembic import context

from app.config import settings
from app.db import Base, make_sessions

config = context.config
target_metadata = Base.metadata
engine, _ = make_sessions(settings().database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
