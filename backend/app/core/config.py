"""Application settings, read from environment variables and `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/watchtower.db"
    data_dir: Path = Path("./data")
    jwt_secret: SecretStr = Field(min_length=32)
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "procedures_v1"
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: SecretStr = SecretStr("")
    yolo_model: str = "yolov8n.pt"
    max_upload_mb: int = 100
    max_video_seconds: int = 180
    max_video_pixels: int = 3840 * 2160
    cors_origin: str = "http://localhost:5173"
    mcp_server_path: Path = Path("../mcp_server/server.py")
    skill_path: Path = Path("../skills/investigate/SKILL.md")
    live_analysis_fps: float = Field(default=5, gt=0, le=30)
    cameras_dir: Path | None = None  # relative camera sources resolve here; default data_dir/cameras


@lru_cache
def settings() -> Settings:
    value = Settings()
    value.data_dir.mkdir(parents=True, exist_ok=True)
    return value
