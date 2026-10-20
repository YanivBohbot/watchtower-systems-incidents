"""Request bodies, and the serializer that hides internal columns from responses."""

from pydantic import BaseModel, Field

HIDDEN_COLUMNS = ("password_hash", "storage_key", "evidence_key", "snapshot_key", "source")


class Login(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=1000)


class Review(BaseModel):
    approved: bool
    create_ticket: bool = False


def public(row) -> dict:
    """Serialize an ORM row without password hashes, storage keys or camera sources."""
    return {
        column.name: getattr(row, column.name) for column in row.__table__.columns if column.name not in HIDDEN_COLUMNS
    }
