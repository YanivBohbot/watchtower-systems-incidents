"""Qdrant vector index holding the embeddings of procedure chunks."""

from qdrant_client import QdrantClient, models


class QdrantIndex:
    def __init__(self, url: str, collection: str, client: QdrantClient | None = None):
        self.client = client if client is not None else QdrantClient(url=url, timeout=30)
        self.collection = collection

    def upsert(self, points: list[dict]) -> None:
        if not points:
            return
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=len(points[0]["vector"]), distance=models.Distance.COSINE),
            )
        self.client.upsert(
            self.collection,
            points=[
                models.PointStruct(id=p["id"], vector=p["vector"], payload={"document_id": p["document_id"]})
                for p in points
            ],
            wait=True,
        )

    def search(self, vector: list[float], limit: int = 5) -> list[dict]:
        if not self.client.collection_exists(self.collection):
            return []
        return [
            {"id": str(p.id), "score": p.score}
            for p in self.client.query_points(self.collection, query=vector, limit=limit).points
        ]

    def delete(self, ids: list[str]) -> None:
        if ids and self.client.collection_exists(self.collection):
            self.client.delete(self.collection, points_selector=models.PointIdsList(points=ids), wait=True)
