# Infrastructure and operations

## Services and responsibilities

| Compose service | Command / role | Persistence |
|---|---|---|
| `frontend` | Unprivileged Nginx, compiled React and HTTP proxy | Immutable build |
| `api` | Uvicorn / FastAPI | PostgreSQL and files |
| `worker` | Celery, `processing` queue, concurrency 1 | SQL jobs and files |
| `investigator` | Celery, `investigation` queue, concurrency 1 | PostgreSQL checkpoints, tickets and SQL |
| `scheduler` | Celery Beat, outbox sweep every 30 seconds | Schedule file |
| `migrate` | Alembic, single run | PostgreSQL schema |
| `postgres` | Business data | `postgres-data` volume |
| `redis` | Task broker | SQL jobs remain the durable source |
| `qdrant` | Vector index | `qdrant-data` volume |

The backend services mount the `app-data` volume. It holds the media, the
checkpoints, the tickets and the detector weights. The MCP server is a subprocess
of the investigator, not an extra network service.

Only the frontend is exposed, on `127.0.0.1:5173`. The proxy forwards `/api`.
The backend, Redis, PostgreSQL and Qdrant stay on the internal Compose network.
Sign-in rate limiting is configured in Nginx; running Uvicorn directly without
the proxy does not apply this limit.

## HTTP contracts

Protected routes expect `Authorization: Bearer <token>`.

| Method / route | Input | Effect |
|---|---|---|
| `GET /api/health` | None | Process health, not a full dependency check |
| `POST /api/auth/login` | JSON email/password | JWT and user |
| `GET /api/me` | Token | Current profile |
| `GET /api/videos` | Token | Shared videos |
| `POST /api/videos` | Multipart `file`, JSON `zone` | Video and analysis job |
| `GET /api/videos/{id}/content` | Token | Video bytes |
| `GET /api/documents` | Token | Documents and indexing status |
| `POST /api/documents` | Multipart `file` | Document and ingestion job, SHA-256 deduplication |
| `GET /api/incidents` | Token | Detected events |
| `GET /api/incidents/{id}/evidence` | Token | JPEG capture |
| `POST /api/incidents/{id}/investigate` | Operator token | Investigation and its job |
| `GET /api/investigations` | Token | Reports and statuses |
| `POST /api/investigations/{id}/review` | JSON approved/create_ticket | Decision, then resume job |
| `GET /api/jobs` | Token | The 100 most recent jobs |
| `POST /api/jobs/{id}/retry` | Operator token | Retry a failed job |

Zone example:

```json
{"x1":0.25,"y1":0.15,"x2":0.8,"y2":0.9,"dwell_seconds":3}
```

Review example:

```json
{"approved":true,"create_ticket":true}
```

The OpenAPI documentation is available at `/api/docs`.

## States and consistency

A job goes `queued → running → completed` or `failed`. The atomic claim prevents
two deliveries of the same job from running it at the same time. The SQL sweep
repairs a missing publication to Redis. It also recovers hard crashes: a job
still `running` 20 minutes after it was claimed (longer than the 16-minute hard
time limit of a live worker) is requeued, and after 3 attempts it is marked
`failed` so a job that keeps killing workers does not loop forever.

An investigation moves from `queued` to `awaiting_review`, then `review_queued`,
and finally `approved` or `rejected`. The job status shows any intermediate
failure. A report approved without a ticket creates no MCP object.

Under Docker, LangGraph checkpoints are stored in PostgreSQL (tables created by
`PostgresSaver.setup()` on first use), so several investigation workers can share
them. Local development without PostgreSQL falls back to `checkpoints.db`
(SQLite) in the data directory, which suits a single worker only.

## Diagnosis and recovery

```bash
docker compose ps
docker compose logs --tail=100 api worker investigator scheduler
```

For a document error: check API access, extractable text, the embedding model and
Qdrant availability. Changing the embedding dimension requires a new collection
and re-indexing; do not reuse the existing collection with incompatible vectors.

For a video: check format, duration, resolution, access to the YOLO weights and
available CPU time. `lap` is installed explicitly for ByteTrack. On a closed
network, pre-install `/data/models/yolov8n.pt` in the volume; the weights are not
shipped with the project.

For an investigation: check the LLM model, its availability for the key in use,
the API quota and the MCP process logs. An invented reference makes the report
fail instead of being silently accepted as a citation.

A `failed` job can be retried from the UI. A job left `running` after a hard
crash is requeued automatically by the scheduler after 20 minutes. To recover it
sooner, confirm that its old worker has stopped, then run the recovery command
and let the scheduler republish it.

```bash
docker compose exec api python -m app.cli recover-job JOB_ID
```

Logs may contain library responses or errors: restrict access to them in a real
deployment. The V1 does not set up a log platform, distributed metrics or
external alerting.

## Development without Docker

Install the backend as described in the README. Create `backend/.env` with a
random local `JWT_SECRET` and your API key. Adjust `DATABASE_URL`, `REDIS_URL`
and `QDRANT_URL` to services reachable from your machine. SQLite is fine for a
first local start; PostgreSQL is the Compose target.

From `backend`:

```bash
alembic upgrade head
python -m app.cli create-user yaniv@example.com --role admin
uvicorn app.main:app --reload
```

In two more terminals with the same environment:

```bash
celery -A app.tasks:celery worker -Q processing --concurrency=1 --loglevel=INFO
celery -A app.tasks:celery worker -Q investigation --concurrency=1 --loglevel=INFO
```

Then a fourth one for Beat:

```bash
celery -A app.tasks:celery beat --loglevel=INFO
```

From `frontend`, run `npm ci` then `npm run dev`. Vite forwards `/api` to
`localhost:8000`. Celery is easier on Linux, macOS or WSL; Docker is the
recommended path on Windows.

## Later deployment

Before any public exposure: TLS/session/SSO strategy, data access scope, object
storage, video streaming, resource limits and parser isolation, backups,
retention policy and observability. These are identified work items, not
services already deployed by this project.

Vision weights and libraries have their own license terms. In particular, check
the Ultralytics license before any commercial distribution.
