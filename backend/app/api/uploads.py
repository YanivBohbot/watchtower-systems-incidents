"""Streaming upload reception with a size limit."""

import hashlib
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile


async def receive_upload(file: UploadFile, data_dir: Path, max_upload_mb: int) -> tuple[Path, str]:
    """Stream the upload to a temporary file under data_dir; return its path and SHA-256."""
    uploads = data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    with tempfile.NamedTemporaryFile(dir=uploads, delete=False) as temp:
        path = Path(temp.name)
        try:
            while part := await file.read(1024 * 1024):
                size += len(part)
                if size > max_upload_mb * 1024 * 1024:
                    raise HTTPException(413, "File exceeds upload limit")
                digest.update(part)
                temp.write(part)
            if not size:
                raise HTTPException(422, "Empty file")
        except BaseException:
            temp.close()
            path.unlink(missing_ok=True)
            raise
    return path, digest.hexdigest()
