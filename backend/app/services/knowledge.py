from io import BytesIO
from uuid import NAMESPACE_URL, uuid5

from pypdf import PdfReader
from sqlalchemy import delete, select

from app.db import Chunk, Document
from app.domain.ports import Embedder, Storage, VectorIndex
from app.domain.text import chunk_text


class KnowledgeService:
    def __init__(self, sessions, storage: Storage, embedder: Embedder, index: VectorIndex):
        self.sessions, self.storage, self.embedder, self.index = sessions, storage, embedder, index

    def ingest(self, document_id: str):
        with self.sessions() as db:
            doc = db.get(Document, document_id)
            if doc is None:
                raise ValueError("Document not found")
            if doc.status == "indexed":
                return
            doc.status = "indexing"
            db.commit()
            try:
                content = self.storage.read(doc.storage_key)
                if doc.name.lower().endswith(".pdf"):
                    reader = PdfReader(BytesIO(content))
                    if len(reader.pages) > 100:
                        raise ValueError("Maximum 100 PDF pages")
                    pages = [page.extract_text() or "" for page in reader.pages]
                else:
                    pages = [content.decode("utf-8")]
                if sum(map(len, pages)) > 2_000_000:
                    raise ValueError("Document text exceeds limit")
                chunks = []
                for page_number, text in enumerate(pages, 1):
                    for i, part in enumerate(chunk_text(text)):
                        chunks.append(
                            {
                                "id": str(uuid5(NAMESPACE_URL, f"{doc.id}/{page_number}/{i}")),
                                "document_id": doc.id,
                                "page": page_number,
                                "text": part,
                            }
                        )
                if not chunks:
                    raise ValueError("No readable text; scanned PDFs require OCR, not included in V1")
                vectors = self.embedder.embed_documents([c["text"] for c in chunks])
                if len(vectors) != len(chunks):
                    raise ValueError("Embedding response length mismatch")
                self.index.upsert([{**c, "vector": v} for c, v in zip(chunks, vectors, strict=True)])
                db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
                db.add_all([Chunk(**c) for c in chunks])
                doc.status = "indexed"
                db.commit()
            except Exception:
                db.rollback()
                doc = db.get(Document, document_id)
                doc.status = "error"
                db.commit()
                raise

    def search(self, query: str, limit: int = 5) -> list[dict]:
        hits = self.index.search(self.embedder.embed_query(query[:4000]), limit=min(limit, 10) * 3)
        result = []
        with self.sessions() as db:
            for hit in hits:
                row = db.execute(
                    select(Chunk, Document).join(Document).where(Chunk.id == hit["id"], Document.status == "indexed")
                ).first()
                if row:
                    chunk, document = row
                    result.append(
                        {
                            "id": chunk.id,
                            "document_id": document.id,
                            "document": document.name,
                            "page": chunk.page,
                            "text": chunk.text,
                            "score": hit.get("score"),
                        }
                    )
                if len(result) >= limit:
                    break
        return result
