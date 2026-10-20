"""Procedure documents: list, and upload (deduplicated by SHA-256, starts an indexing job)."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import (
    JobDispatcher,
    current_user,
    get_dispatcher,
    get_sessions,
    get_settings,
    get_storage,
    require_operator,
)
from app.api.schemas import public
from app.api.uploads import receive_upload
from app.core.config import Settings
from app.database.models import Document, Job, uid
from app.integrations.local_storage import LocalStorage

DOCUMENT_EXTENSIONS = (".pdf", ".txt")

router = APIRouter()


@router.get("/api/documents", dependencies=[Depends(current_user)])
def list_documents(sessions=Depends(get_sessions)):
    with sessions() as db:
        return [public(document) for document in db.scalars(select(Document))]


@router.post("/api/documents", status_code=201, dependencies=[Depends(require_operator)])
async def upload_document(
    file: UploadFile = File(...),
    cfg: Settings = Depends(get_settings),
    sessions=Depends(get_sessions),
    storage: LocalStorage = Depends(get_storage),
    dispatcher: JobDispatcher = Depends(get_dispatcher),
):
    if Path(file.filename or "").suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise HTTPException(422, "Use a text PDF or UTF-8 TXT")
    upload, sha = await receive_upload(file, cfg.data_dir, cfg.max_upload_mb)
    with sessions() as db:
        existing = db.scalar(select(Document).where(Document.sha256 == sha))
        if existing:
            upload.unlink(missing_ok=True)
            return public(existing)
        doc_id, job_id = uid(), uid()
        key = f"documents/{doc_id}{Path(file.filename).suffix.lower()}"
        storage.put_file(key, upload)
        doc = Document(id=doc_id, name=Path(file.filename).name[:255], storage_key=key, sha256=sha)
        db.add_all([doc, Job(id=job_id, kind="document", resource_id=doc_id)])
        try:
            db.commit()
        except IntegrityError:
            # A concurrent upload of the same file won the unique SHA-256: return its document.
            db.rollback()
            existing = db.scalar(select(Document).where(Document.sha256 == sha))
            if existing is None:
                raise
            storage.delete(key)
            return public(existing)
        result = public(doc)
    dispatcher.enqueue(job_id)
    return result
