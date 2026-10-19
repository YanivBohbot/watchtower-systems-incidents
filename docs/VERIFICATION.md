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
