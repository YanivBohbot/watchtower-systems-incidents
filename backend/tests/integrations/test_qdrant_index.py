from uuid import uuid4

from qdrant_client import QdrantClient

from app.integrations.qdrant_index import QdrantIndex


def test_actual_qdrant_sdk_upsert_query_and_delete():
    index = QdrantIndex("http://localhost:6333", "test", client=QdrantClient(location=":memory:"))
    first, second = str(uuid4()), str(uuid4())
    index.upsert(
        [
            {"id": first, "document_id": "a", "vector": [1.0, 0.0]},
            {"id": second, "document_id": "b", "vector": [0.0, 1.0]},
        ]
    )
    assert index.search([1.0, 0.0], limit=1)[0]["id"] == first
    index.delete([first])
    assert index.search([1.0, 0.0], limit=1)[0]["id"] == second
    index.client.close()
