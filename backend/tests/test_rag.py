from pathlib import Path

from app.db import Base, Document, make_sessions
from app.adapters.storage import LocalStorage
from app.services.knowledge import KnowledgeService


class Embeddings:
    def embed_documents(self, texts):
        return [[float("zone" in text.lower()), 1.0] for text in texts]

    def embed_query(self, text):
        return [1.0, 1.0]


class Index:
    def __init__(self):
        self.points = {}

    def upsert(self, points):
        self.points.update({p["id"]: p for p in points})

    def delete(self, ids):
        for key in ids:
            self.points.pop(key, None)

    def search(self, vector, limit=5):
        return list(self.points.values())[:limit]


def test_ingestion_is_idempotent_and_search_resolves_canonical_text(tmp_path: Path):
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    storage, index = LocalStorage(tmp_path / "files"), Index()
    storage.put("procedure.txt", b"Zone A: verify footage before opening a ticket.")
    with sessions() as db:
        doc = Document(id="doc", name="procedure.txt", storage_key="procedure.txt", sha256="a" * 64)
        db.add(doc)
        db.commit()
    service = KnowledgeService(sessions, storage, Embeddings(), index)
    service.ingest("doc")
    service.ingest("doc")
    assert len(index.points) == 1
    hits = service.search("zone")
    assert hits[0]["page"] == 1
    assert "verify footage" in hits[0]["text"]
    # Stale / injected vector IDs are never treated as authoritative text.
    index.points["unknown"] = {"id": "unknown", "text": "forged"}
    assert len(service.search("zone")) == 1
    with sessions() as db:
        db.get(Document, "doc").status = "error"
        db.commit()
    assert service.search("zone") == []
