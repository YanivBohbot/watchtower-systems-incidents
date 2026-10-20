# Verification report — October 18, 2026

This document separates the implemented source code from the integrations that were actually run.
No user key was read or stored. No paid OpenAI call was made.

| Check | Result | Actual scope |
|---|---|---|
| Python suite `pytest -q` | **19 tests passed** | Rules, auth, roles, uploads, concurrency, RAG, video, graph, agent, MCP, migration, jobs |
| Ruff | **Passed** | Imports, Python errors and formatting of application/test/migration files |
| React build `npm run build` | **Passed** | TypeScript check and Vite bundle |
| Prettier | **Passed** | React sources, CSS and frontend configuration |
| Playwright | **1 scenario passed** | Chromium, real test FastAPI server: sign-in, empty workspace, TXT upload, list and sign-out |
| Real YOLO + ByteTrack | **Passed** | Ultralytics reference image: three people tracked, normalized coordinates |
| Video pipeline with real YOLO | **Passed** | Eight frames of a repeated reference image: three SQL incidents and their JPEG captures |
| Alembic migration | **Passed on SQLite** | Fresh schema compared with the models, no difference |
| MCP stdio | **Passed** | Real server process, tool discovery, creation, search and persistent deduplication |
| LangChain | **Passed with a scripted provider** | Real tool-calling loop and structured report; not a live OpenAI response |
| LangGraph | **Passed** | Checkpoint, stop for review, resume after reopening, rejection and publication retry |
| Qdrant SDK | **Passed in embedded mode** | Upsert, vector ranking and deletion; not a remote server |
| Compose file | **YAML parsed** | Services and volumes inspected; no Docker engine available |
| Python dependencies | **Passed** | Lock resolution and `pip check` with no incompatibility |

## What was not run

- Building the images and `docker compose up`: Docker is not installed in the working environment.
- PostgreSQL, the Redis/Celery broker and networked Qdrant together in the same deployment.
- OpenAI embedding and generation calls with the requester's personal key.
- A full browser flow from a real video to an OpenAI report and then a ticket.
- Load tests, accuracy evaluation on representative videos, GPU or live camera.

The YOLO test on eight repeated frames is a technical integration test, **not a
quality measurement on real incidents**. The browser test covers part of the
flow; the backend tests cover the remaining steps separately.

## Fixes found during verification

- Explicit install of `lap` for ByteTrack.
- Concurrent document uploads: a single document/job, no 500 response; concurrency test added.
- Migration aligned with the SQL type of video time; automatic comparison added.
- Qdrant client injection, to test its SDK without opening an unwanted network connection.
- Vite server bound to localhost so it starts in an environment without access to the system network inventory.

An independent review of the source examined permissions, job states,
concurrent approval, MCP idempotency, media and startup. The two concrete issues
it reported were fixed. Operational limits remain described in the README and
OPERATIONS.md.

## Milestone 1 (consolidation) — October 19, 2026

| Check | Result | Actual scope |
|---|---|---|
| Python suite `pytest -q` (Python 3.12, Windows) | **31 passed, 1 skipped** | Adds job lease recovery, late-worker protection, attempts reset, checkpoint factory, streamed uploads and Range responses |
| Ruff | **Passed** | `ruff check app tests migrations` |
| Alembic migration `0002` | **Passed on SQLite** | Schema comparison test; not run against PostgreSQL |
| PostgreSQL checkpointer | **Not run** | `test_postgres_checkpointer_round_trip` is skipped without `WATCHTOWER_TEST_POSTGRES_URL` |
| Docker image with the updated lock | **Not run** | `langgraph-checkpoint-postgres==3.2.0` resolved with uv for Linux/Python 3.12 only |

## Milestone 2 (live cameras) — October 20, 2026

| Check | Result | Actual scope |
|---|---|---|
| Python suite `pytest -q` (Python 3.12, Windows) | **52 passed, 2 skipped** | Adds site seeding, camera runner pacing, slow analysis, loop restart, source errors, live hub outage, live API routes, SSE stream, 503 when the hub is down |
| Ruff | **Passed** | `ruff check app tests migrations` |
| Alembic migration `0003` | **Passed on SQLite** | Schema comparison test; not run against PostgreSQL |
| React build `npm run build` | **Passed** | TypeScript check and Vite bundle |
| Playwright | **3 scenarios passed** | Chromium, real test FastAPI server with an in-memory hub: camera wall, alert pushed over SSE without reload, dismiss; alert reaching the banner by polling while the event stream is blocked; existing workspace scenario |
| Camera runner with real video decoding | **Passed** | Generated MJPG clips decoded by OpenCV; the detector is a deterministic double |
| Redis hub | **Not run** | `test_redis_hub_round_trip` is skipped without `WATCHTOWER_TEST_REDIS_URL` |
| Live loop with real YOLO + ByteTrack and the browser | **Passed (without Redis)** | One local process ran the API and two camera runners on the CPU (YOLOv8n, Torch 2.14.1 CPU): a looped 8 s clip built from the Ultralytics reference image, and a camera whose file is missing. About 5 frames analyzed per second; alerts raised from real detections; Chromium through Vite signed in, saw the annotated tile, the missing camera as "Source error", the banner pushed about 3 s after the wall opened, and the alert snapshot. The in-memory hub stood in for Redis |
| `python -m app.live` with Redis | **Not run** | Same code path minus the Redis hub; no Redis server available |
| Docker image and `cameras` service | **Not run** | Docker is not installed in the working environment |

Live detection is people only in this milestone. No latency or accuracy figure is
claimed yet; measurements are planned for milestone 8.

## Code restructure — October 20, 2026

The rows above keep the module paths that existed when they were run. The code
was then reorganized into folders without changing behaviour; old paths map to
new ones as follows (`backend/app/` prefix omitted).

| Old path | New path |
|---|---|
| `config.py`, `auth.py` | `core/config.py`, `core/security.py` |
| `db.py` | `database/models.py` + `database/session.py` |
| `domain/rules.py`, `text.py`, `ports.py` | `domain/dwell_rule.py`, `text_chunking.py`, `interfaces.py` |
| `api.py` | `api/application.py`, `api/dependencies.py`, `api/schemas.py`, `api/uploads.py`, `api/routes/*.py` |
| `adapters/*` | `integrations/local_storage.py`, `yolo_detector.py`, `qdrant_index.py`, `mcp_tickets.py`, `looped_video_source.py`, `live_hub.py` |
| `services/video.py`, `knowledge.py`, `live.py`, `annotate.py`, `sites.py` | `services/video_analysis.py`, `knowledge_base.py`, `camera_monitor.py`, `frame_annotation.py`, `site_seeding.py` |
| `agent/*` | `investigation/*` |
| `tasks.py`, `runtime.py`, `live.py` | `workers/job_queue.py`, `workers/job_handlers.py`, `workers/camera_process.py` |
| `python -m app.live`, `celery -A app.tasks:celery` | `python -m app.workers.camera_process`, `celery -A app.workers.job_queue:celery` |
| `frontend/src/api.ts`, `types.ts`, `LiveWall.tsx`, `ZoneEditor.tsx`, `style.css` | `src/api/client.ts`, `src/api/types.ts`, `src/pages/LiveCamerasPage.tsx`, `src/components/ZoneEditor.tsx`, `src/styles/global.css` |
| `backend/tests/test_*.py`, `ui_server.py` | `backend/tests/<package>/test_*.py`, `tests/support/ui_server.py` |

## Reproducing the checks

```bash
cd backend
pytest -q
ruff check app tests migrations
ruff format --check app tests migrations
```

```bash
cd frontend
npm ci
npm run build
npx playwright install chromium
# Set WATCHTOWER_PYTHON if the backend Python is not the one on PATH.
npx playwright test
```

For the real vision test, with the vision extra installed, from the project root:

```bash
python scripts/smoke_vision.py --model PATH_TO/yolov8n.pt
```

The weights are downloaded if missing and available to Ultralytics.
The videos and weights used for the trials are not included in the project.
