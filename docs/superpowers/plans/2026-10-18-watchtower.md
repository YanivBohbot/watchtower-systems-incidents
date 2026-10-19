# Implementation plan

1. Domain and contracts: write rule and chunking tests, see RED, implement the ports and rules.
2. Persistence and API: write auth/upload/validation tests, then SQLAlchemy models, migrations and endpoints.
3. Pipelines: storage, YOLO, video processing, ingestion, Qdrant, status handling; tests through port injection.
4. Agent: bounded tools, structured report, citation check, SQLite checkpoints, interrupt/resume; tests without a paid provider.
5. MCP: stdio server authenticated by the local process boundary, SQLite tickets, deduplication; real protocol client test.
6. React: sign-in, upload and zone selection, documents, statuses/jobs, evidence, report and decision; TypeScript build.
7. Infra and documentation: Compose PostgreSQL/Redis/Qdrant/API/workers/frontend, CI, file-by-file guide and verified report.

## Review focus
Concurrent resume, DB/queue atomicity, ticket deduplication after a network failure,
media access, invalid files, secrets and document references that were never retrieved.
