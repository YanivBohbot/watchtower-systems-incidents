# Understanding the WatchTower code

This guide explains every file in the application and its important functions.
The source code is the reference: the descriptions below cover the delivered code,
not a parallel pseudo-project.

## 0. Where things live

```
backend/app/
├── main.py            ASGI entry point (uvicorn app.main:app)
├── cli.py             admin commands: create-user, seed-site, recover-job
├── core/              settings and security, used everywhere
├── database/          ORM tables and the session factory
├── domain/            pure business rules and the interfaces integrations implement
├── api/               HTTP: app factory, shared dependencies, schemas, one router per domain
├── services/          use cases: video analysis, knowledge base, live cameras, site seeding
├── investigation/     the LangGraph workflow and its LLM agent
├── integrations/      external systems: storage, YOLO, Qdrant, MCP tickets, video sources, live hub
└── workers/           background processes: Celery job queue, job handlers, camera process

backend/tests/         same folders as app/, plus test_layout.py, test_entry_points.py and support/
frontend/src/
├── main.tsx  App.tsx  sign-in gate and navigation
├── api/               HTTP client, response types, polling and media hooks
├── pages/             one file per tab, plus the sign-in page
├── components/        reusable pieces: zone editor, status badge, evidence image, job table
└── styles/            global stylesheet
```

A layer only imports the layers below it: `api` and `workers` call `services` and
`investigation`, which use `domain`, `database` and `integrations`. `domain` imports
nothing from the application. `backend/tests/test_layout.py` fails if one of the
documented modules disappears or an old path comes back.

## 1. Why this architecture?

Three different problems are kept separate: extracting observations from a video,
applying a business rule, then preparing an investigation from evidence.
Frame-by-frame analysis is predictable; the investigation sometimes needs to
choose which tools to consult. Authorization and approval never depend on the
model's goodwill.

The backend is a **modular monolith**: Python code organized into packages and
run by several processes. FastAPI serves HTTP, Celery runs the jobs, and a camera
process watches the live feeds. These processes share PostgreSQL and the file
volume. They are not independent microservices with their own databases.

The **ports and adapters** pattern is used at the boundaries. Services accept an
object that has the required methods; Python uses `Protocol` in
`domain/interfaces.py` to document those capabilities, and `integrations/` holds
the concrete adapters. Replacing YOLO or Qdrant does not require rewriting the
dwell rule. You still need to check the new adapter's differences in scores,
coordinates and performance.

## 2. Domain: the stable contracts

### `backend/app/domain/dwell_rule.py`

`Zone` is a Pydantic model. Coordinates are normalized between 0 and 1, so a zone
is independent of resolution. The fields enforce the bounds; `ordered()` rejects
an inverted or zero-area rectangle. `dwell_seconds` is the minimum presence time,
in video seconds.

`Observation` is an immutable dataclass holding a tracking ID, a point and a
timestamp. The video service uses the **bottom-center of the box**, an
approximation of the ground contact point. This choice is recorded in the
incident details.

`DwellRule.feed()` maintains two structures: `active` keeps the start and last
observation for each track; `emitted` prevents creating several events for the
same track within one analysis. Leaving the zone or disappearing for too long
resets the counter. The rule knows nothing about images, SQL or the agent.

### `backend/app/domain/text_chunking.py`

`chunk_text()` splits a page into overlapping character windows. `size=1200` and
`overlap=180` are starting values, not universal ones. The overlap keeps some
context between passages. Validation prevents a zero step, and empty pages are
skipped. This is deliberately simple chunking, to be compared later with
structural or token-based chunking.

### `backend/app/domain/interfaces.py`

`Storage` describes file operations. `Embedder` distinguishes document and query
embeddings. `VectorIndex` exposes indexing, search and point deletion.
`FrameSource` is a camera feed, `LiveHub` and `Subscription` the live channel.
Tests inject deterministic objects implementing these methods. They do not change
the business behavior in order to pass.

## 3. Configuration, persistence and security

### `backend/app/core/config.py`

`Settings` reads environment variables and optionally `.env`. `SecretStr` avoids
accidentally printing secrets in the model's representation. It does not replace
production secret management. `settings()` caches the process configuration and
prepares the data directory.

### `backend/app/core/security.py`

`hash_password()` uses PBKDF2-SHA256, a random salt and 600,000 iterations.
The original password is not stored. `verify_password()` recomputes the hash and
compares the bytes with `hmac.compare_digest`.

`token_for()` signs an HS256 JWT valid for eight hours. The API extracts its
`sub`, checks signature and expiry, then reloads the user and role from SQL.
A role change therefore takes effect on the following requests.

### `backend/app/database/models.py` and `session.py`

`models.py` holds `Base`, the SQLAlchemy declarative registry, the ID and clock
helpers `uid()` and `now()`, and every table. `session.py` holds
`make_sessions()`, which creates the engine and a session factory; a session is a
unit of SQL work. SQLite gets foreign-key and lock-timeout settings. Docker uses
PostgreSQL with the same business schema.

| Table | Why it exists |
|---|---|
| `User` | Account, password hash, role |
| `Video` | Name, storage key and configured rule |
| `Job` | Durable work item, progress, status, attempts and error |
| `Incident` | Event, track, video time and evidence |
| `Document` | Immutable document and SHA-256 fingerprint |
| `Chunk` | Canonical text, page and document of a passage |
| `Investigation` | Report, status, author and human decision |
| `Site`, `Camera` | Live cameras grouped by site, with their source, zone and labels |
| `Alert` | Event raised by a live camera, with its snapshot |

Unique constraints protect integrity even when two processes act at the same
time. They are not replaced by a simple Python `if`.

### `backend/app/cli.py`

`create-user` prompts for the password with `getpass` and creates a user without
exposing a public sign-up route. `seed-site` loads a site and its cameras from a
JSON file. `recover-job` resets a stuck job to `queued` immediately, instead of
waiting for the automatic lease recovery (section 9). Use it only after
confirming that the old worker has stopped.

### `backend/migrations/`

`env.py` provides the engine and metadata to Alembic. `0001_initial.py` defines
the initial schema explicitly; it does not just call `create_all()` on models
that may evolve. Any later change requires a new Alembic revision. Isolated
tests use `create_all()` for speed.

## 4. The API: from HTTP to use cases

### `backend/app/api/application.py`

`create_app()` is a factory: tests pass it a temporary database, a dispatcher that
records job IDs and an in-memory hub; the normal launch wires the real
dependencies. It stores the settings, sessions, storage, live hub and job
dispatcher on `app.state`, adds CORS, and mounts every router.

### `backend/app/api/dependencies.py`

`current_user()` verifies the JWT. `require_operator()` allows only operators and
admins to perform mutations; viewers can read the shared workspace. `get_*()`
functions hand the services stored on `app.state` to the routes.

`JobDispatcher.enqueue()` is deliberately best-effort: publishing is not part of
the SQL transaction. The `jobs` table, the worker's atomic claim and the periodic
sweep form a small **durable outbox**. `call_live_hub()` turns a hub failure into
`503` instead of `500`.

### `backend/app/api/schemas.py` and `uploads.py`

`Login` and `Review` are the JSON request bodies. `public()` serializes the
public columns and strips password hashes, internal storage keys and camera
sources.

`receive_upload()` streams the file in 1 MiB blocks to a temporary file under
`data_dir/uploads`, computes its SHA-256 on the fly, rejects empty files and
enforces the byte limit; on any failure the temporary file is deleted. Accepted
files are moved into storage with `LocalStorage.put_file()`, so an upload never
sits in memory. The extension is a first check; the video content is actually
decoded in the worker, and PDFs are actually parsed at ingestion.

### `backend/app/api/routes/`

Each router keeps the full URL in its decorators, so searching for a path finds
its handler.

| Router | Routes |
|---|---|
| `health.py` | `GET /api/health` |
| `auth.py` | `POST /api/auth/login`, `GET /api/me` |
| `videos.py` | list, upload with a zone, stream the content |
| `jobs.py` | list, retry a failed job |
| `documents.py` | list, upload a procedure |
| `incidents.py` | list, evidence image, open an investigation |
| `investigations.py` | list, human review |
| `cameras.py` | list with live status, latest frame |
| `alerts.py` | list newest first, snapshot |
| `live_events.py` | `GET /api/live/events`, Server-Sent Events |

`upload_video()` validates the zone, stores the file under a UUID key, then saves
the video and the job. The job is committed **before** it is sent to Celery. If
Redis is unavailable, the work stays durably in SQL and the scheduler can
republish it.

`upload_document()` computes SHA-256 to avoid re-indexing the same content. A
second check through an SQL constraint handles concurrent uploads: the loser
falls back to the existing document and deletes its temporary file.

Content routes first look up a video or incident ID in SQL, after authentication.
They never accept an arbitrary file key. Videos are served with `FileResponse`,
which streams the file and answers Range requests (`206 Partial Content`). The
React client still downloads a video as one authenticated blob, so seeking in
the browser only benefits once a later milestone switches it to a streaming URL.

`investigate_incident()` creates the investigation and its job.
`review_investigation()` performs a conditional update on `awaiting_review`, so
two concurrent clicks cannot produce two accepted decisions. It records the
reviewer, the decision and a resume job. `retry_job()` only reactivates failed
jobs.

### `backend/app/main.py`

Uvicorn entry point: load the configuration, then build the application.
It runs no migration or heavy processing at import time.

## 5. Video, end to end

### `backend/app/integrations/local_storage.py`

`LocalStorage.path()` resolves the path and requires it to stay under the storage
root. `put()` writes to a temporary file and then replaces the target. `read()`
reads the bytes, `delete()` allows cleanup, and `local_copy()` returns the local
path directly here. A future remote adapter could download into the temporary
path passed to that method.

### `backend/app/integrations/yolo_detector.py`

`TrackedObject` holds a normalized box, the detector score and an ID.
`YoloDetector` imports Ultralytics only when instantiated, so the backend and the
business tests work without installing the weights or PyTorch.

One instance is created **per video**, to isolate ByteTrack's state. `track()`
calls YOLO with `persist=True`, the ByteTrack tracker and COCO class `0`
(person). SDK tensors are converted into stable Python objects. `lap` is declared
explicitly to avoid a surprise install on the first tracking call.

### `backend/app/services/video_analysis.py`

`VideoService.analyze()` opens the file with OpenCV, checks its properties,
instantiates the detector and processes frames progressively. The timestamp is
`frame_number / fps`, not the time at which the CPU finishes inference.

For each object, the service computes the bottom-center point and calls
`DwellRule.feed()`. When an event fires, it draws the zone and the box on a copy
of the frame (`services/frame_annotation.py`), encodes a JPEG, stores the capture
and records the incident. The `(video_id, track_id)` constraint and reading
existing events prevent duplicates on a retry.

`progress()` updates the job every 30 frames. An invalid, oversized, too long or
truncated file fails explicitly. A partially completed analysis may already have
created events: check the job status before treating its list as complete. It is
not a single transaction covering the whole video.

## 6. RAG, end to end

### `backend/app/integrations/qdrant_index.py`

`QdrantIndex.upsert()` creates the collection if needed, using the dimension of
the first vector and cosine distance. IDs are the SQL chunk IDs. `search()`
returns IDs and scores. **The report text is never taken directly from an
unchecked Qdrant payload.** `delete()` exposes point cleanup, with no document
deletion route in this V1.

### `backend/app/services/knowledge_base.py`

`ingest()` moves the document to `indexing`, extracts the pages, chunks the text,
computes deterministic UUID5 IDs and requests the embeddings. Qdrant indexing
finishes before SQL marks the document `indexed`. The same IDs make retries
possible without adding copies of the same passage. On error, the document moves
to `error` and its passages are not served by search.

`search()` embeds the question, queries Qdrant, then resolves each ID in SQL,
requiring an `indexed` document. It returns the canonical text, the document name
and the page. Unknown or inactive IDs are ignored.

There is no distributed transaction between SQL and Qdrant: write ordering,
deterministic IDs and the SQL filter keep retries consistent for this case. New
files are separate documents; there is no automatic supersession between
versions of a procedure yet.

## 7. The agent and its workflow

### `backend/app/investigation/schemas.py`

`Report` enforces a structured output: summary, findings, recommendation,
citations, limitations. `validate_report()` rejects any citation ID missing from
the set actually retrieved during the investigation. Detailed sources are
reattached by the code. Without citations, an explicit limitation is added.

This prevents an invented reference to a non-existent passage; **it does not
prove that every sentence is semantically justified**. Evaluation and human
review are still required.

### `backend/app/investigation/investigator.py`

`Investigator.run()` loads the incident and builds tools scoped to its context:

| Tool | Allowed access |
|---|---|
| `get_evidence` | Observations and evidence link of the current incident |
| `search_procedures` | Document search, recording the retrieved sources |
| `search_related_events` | At most ten events in the same video, within ±60 s |
| Read-only MCP tools | Ticket search and lookup |

An initial document search is enforced by the code. The agent can refine it
afterwards. The tools are closures: their context data are not parameters the
model can supply freely.

`create_agent()` builds a tool-calling loop. `ToolStrategy(Report)` requests the
structured output. Depth is capped at 16 graph steps, and each model request has
a timeout and a limited number of retries. This is not yet a global cost
counter. The provider is wired by `make_model()`; another factory can supply a
compatible model without changing the tools.

`tool_trace` keeps the names of the local tools, not the LLM's internal
reasoning. MCP calls are not detailed in this minimal trace.

### `skills/investigate/SKILL.md`

This is an **application procedure loaded into the system prompt**, versioned
with the project. It is not a dynamic skill-discovery engine, and the file does
not install itself as a ChatGPT skill. The steps cover checking the evidence,
separating facts from hypotheses, and human review.

### `backend/app/investigation/workflow.py`

`build_workflow()` produces a LangGraph graph with three nodes:

1. `investigate` prepares and persists the draft.
2. `human_review` calls `interrupt()` and suspends execution.
3. `finalize` applies the decision and optionally publishes a ticket.

The key point: the review node does not create a ticket before `interrupt()`.
LangGraph may re-run that node on resume. The external side effect happens in a
later step, with an idempotency key.

The pattern is therefore a **deterministic workflow containing one tool-using
agent**, not several agents artificially playing roles. Video detection does not
go through this loop.

### `backend/app/investigation/checkpoints.py`

`open_checkpointer()` picks the saver: `PostgresSaver` when the application
database is PostgreSQL (`checkpoint_url()` turns the SQLAlchemy URL
`postgresql+psycopg://…` into a plain libpq URL), `SqliteSaver` otherwise.

## 8. MCP: a real, limited integration

### `mcp_server/server.py`

A **stdio** MCP server, launched as a local subprocess. `FastMCP` exposes
`search_tickets`, `get_ticket` and `create_ticket`. Data lives in a persistent
SQLite database. The transport opens no network port and needs no OAuth server
here; its trust boundary is the process allowed to launch it.

`create_ticket()` uses a unique idempotency key and `INSERT OR IGNORE`: if the
ticket was created but the response was lost, a new request for the same
investigation returns the same ticket.

### `backend/app/integrations/mcp_tickets.py`

`McpTickets` configures `MultiServerMCPClient` with the server path and its
database path. `read_tools()` passes only the two read-only tools to the agent.
`publish()` explicitly calls `create_ticket` from the approved workflow and
checks protocol errors. This is our own ticket system; it does not claim to
write to Jira, Linear or any other unconnected service.

## 9. Jobs and recovery

### `backend/app/workers/job_queue.py`

The Celery application. `run_job()` (task `watchtower.run`) claims the work with
`UPDATE ... WHERE status='queued'`. Only the process that changes the row runs
it; other deliveries return. Processing then moves to `completed` or `failed`,
with logs correlated to the ID. The public error message stays short; details
are in the logs.

The claim also records `started_at` and increments `attempts`. `sweep()` (task
`watchtower.sweep`, every 30 s through Celery beat) first calls
`recover_stale_jobs()`: a job still `running` after `JOB_LEASE_SECONDS` (1200 s,
longer than the 960 s hard time limit, so its worker must be dead) is requeued,
or marked `failed` once it reaches `MAX_JOB_ATTEMPTS` (3). Each change is a
conditional update, so a concurrent claim wins. `sweep()` then republishes jobs
still `queued`. `queue_for_kind()` sends video and document jobs to the
`processing` queue, the agent and the human resume to `investigation`. There is
no exactly-once execution guarantee.

### `backend/app/workers/job_handlers.py`

This is the worker's **composition root**. `knowledge_service()` selects the
embeddings and Qdrant. `execute()` routes a job kind to the right service.

For an investigation, it wires the agent, the MCP server, the checkpoint saver
and the graph. `thread_id` is the investigation ID. A new invocation starts the
graph; a resume uses `Command(resume=...)`. A completed graph is not restarted
when the job is delivered again. If `finalize` failed, it resumes from its
checkpoint without asking the LLM for the report again.

## 10. Live cameras

### `backend/app/services/site_seeding.py`

`seed_site()` validates a JSON site description with Pydantic (zones reuse the
`Zone` model) and creates or updates the site and its cameras by name.

### `backend/app/integrations/looped_video_source.py`

`LoopedVideoSource` wraps OpenCV: `read()` returns the next frame and rewinds at
the end (incrementing `loops`), `skip(n)` grabs frames without decoding them.
It implements the `FrameSource` interface, so an RTSP source could replace it.

### `backend/app/services/camera_monitor.py`

`CameraRunner.step()` computes which frame matches the wall-clock time, skips
the late ones, runs the detector, publishes the annotated frame and status, and
feeds the `DwellRule`. When the rule fires, `_raise_alert()` stores a snapshot,
commits an `Alert` row, then publishes the event. Any error marks the camera
`error` instead of raising. `run()` paces the steps and retries failed sources.

### `backend/app/integrations/live_hub.py` and `backend/app/workers/camera_process.py`

`RedisHub` (production) and `MemoryHub` (tests) implement the `LiveHub`
interface. `camera_process.py` builds one runner per enabled camera and runs each
in a thread. The live routes (`api/routes/cameras.py`, `alerts.py`,
`live_events.py`) read from the hub; `/api/live/events` turns the alert channel
into Server-Sent Events.

## 11. The frontend, file by file

| File | Explanation |
|---|---|
| `src/main.tsx` | Mounts React and the `QueryClientProvider` that shares cache and mutations |
| `src/App.tsx` | Sign-in gate, sidebar, tab headings, banners, statistics, and the mutations shared by the pages |
| `src/api/client.ts` | `request()` adds the Bearer token and handles JSON/FormData and errors; `mediaUrl()` fetches an authenticated blob; `streamEvents()` reads the live event stream |
| `src/api/types.ts` | TypeScript contracts for the responses used by the UI |
| `src/api/queries.ts` | `useList()` polls a list endpoint every 2.5 seconds |
| `src/api/media.ts` | `useMedia()` turns an authenticated image or video into an object URL |
| `src/pages/LoginPage.tsx` | Sign-in form |
| `src/pages/LiveCamerasPage.tsx` | Camera wall, alert list and pushed alert banner |
| `src/pages/VideoAnalysisPage.tsx` | Video upload with a zone, playback and detected events |
| `src/pages/ProceduresPage.tsx` | Procedure library and document upload |
| `src/pages/InvestigationsPage.tsx` | Reports, sources, limitations and the review buttons |
| `src/components/ZoneEditor.tsx` | Draws the rectangle with Pointer Events; converts screen pixels into normalized coordinates |
| `src/components/StatusBadge.tsx` | Readable label for a status |
| `src/components/EvidenceImage.tsx` | Evidence capture of an incident |
| `src/components/JobActivity.tsx` | Job table shown under every tab, with retry |
| `src/styles/global.css` | Responsive layout, statuses, forms and evidence display |
| `vite.config.ts` | React build and `/api` proxy in development |
| `nginx.conf` | Serves the build and forwards `/api` to FastAPI |
| `nginx-limits.conf` | Rate-limits sign-in requests at the proxy |

`useMedia()` cancels stale downloads and revokes blob URLs to avoid memory leaks.
The token is never put in a video URL.

`ZoneEditor` keeps the video's intrinsic aspect ratio. Drawing mode overlays the
image; finish the selection to reach the video controls. The zone sent to the
backend matches the image's coordinate frame, not a distorted rectangle.

TanStack Query refreshes the lists every 2.5 seconds. After a mutation, the cache
is invalidated. Loading, errors, empty views and failed jobs are shown. `App`
keeps the video being prepared (`useVideoDraft()`) so it survives a tab switch.
The viewer role hides mutation controls, but **the deciding authorization stays
in FastAPI**.

The JWT is kept in `sessionStorage` for this local application; a public
deployment would need a proper session strategy, CSP and XSS protection.

## 12. Infrastructure and test files

`compose.yaml` assembles the services and volumes. The Dockerfiles build the CPU
backend and the static frontend. `.env.example` documents the configuration;
`scripts/init_env.py` only generates local secrets and never sees the OpenAI key.
`.gitignore` and `.dockerignore` exclude data and secrets.

`requirements.lock` pins the verified backend environment; the vision extra and
CPU PyTorch are installed separately by the Dockerfile. `package-lock.json` pins
the frontend dependencies. `.github/workflows/ci.yml` runs tests, lint and build.

`backend/tests/` mirrors `app/`: `api/test_routes.py` checks the route table,
permissions and upload concurrency; `domain/`, `services/`, `investigation/`,
`integrations/`, `workers/` and `database/` cover the rules, the document
pipeline, reading a real generated video, live cameras, the persistent workflow,
the LangChain loop with a scripted provider, the real MCP protocol, job recovery
and migrations. `test_layout.py` pins the package layout and `test_entry_points.py`
the process entry points. Deterministic test adapters live in the tests and are
never enabled as a silent production mode. `tests/support/ui_server.py` exists
only for the Playwright scenarios.

## Suggested reading order

Start with `domain/dwell_rule.py`, then `services/video_analysis.py`,
`api/routes/videos.py` and `workers/job_queue.py`. Next read
`services/knowledge_base.py`, `investigation/investigator.py`,
`investigation/workflow.py` and `workers/job_handlers.py`. Then the live path:
`services/camera_monitor.py` and `workers/camera_process.py`. Finish with MCP,
React and Compose: by then each component will have a clear role in the full flow.
