# WatchTower — specification of the delivered version

Educational full-stack application for uploaded videos: person detection,
tracking, a presence rule in a normalized rectangular zone, incidents with a
capture, PDF/TXT documents, vector search, agentic investigation and human
review before a ticket is created through a real MCP server.

## Contracts
- UUID identifiers. A single organization, several users, viewer/operator/admin roles.
- Signed JWT authentication, PBKDF2 passwords. No public predefined account.
- Short synchronous API, Celery for processing. PostgreSQL in Docker, SQLite in tests.
- Storage port with a shipped local adapter; S3 reserved for an extension; YOLO detection port; OpenAI embeddings; Qdrant.
- A video analysis is idempotent: at most one event per track and zone.
- Detections use video seconds, never compute time.
- LangChain agent with read-only tools inside a persistent LangGraph workflow.
- Valid citation = ID of a passage actually retrieved during this run.
- HITL resume: deterministic approve/reject, idempotent ticket per investigation.
- No keys in the source code. No paid call required for the tests.

## Explicit limits
V1: video file, rectangular zone, people, text documents, single organization.
No live RTSP, OCR, tracking guarantee across occlusions, or Kubernetes deployment.
Reference checking alone does not prove the generated text is true.
YOLO is optional for a local install; weights are supplied or downloaded on first use.
Tests use deterministic ports; live integrations are evaluated separately when available.

## Criteria
Rule tests (zone exit, tracking gap, threshold and duplicates), API permissions,
uploads, RAG with filtering on indexed documents, invented references rejected, graph
pause/resume and idempotent MCP ticket. TypeScript build. Docker configuration and guide.
