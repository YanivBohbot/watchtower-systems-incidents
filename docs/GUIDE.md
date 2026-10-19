# Understanding the WatchTower code

This guide explains every file in the application and its important functions.
The source code is the reference: the descriptions below cover the delivered code,
not a parallel pseudo-project.

## 1. Why this architecture?

Three different problems are kept separate: extracting observations from a video,
applying a business rule, then preparing an investigation from evidence.
Frame-by-frame analysis is predictable; the investigation sometimes needs to
choose which tools to consult. Authorization and approval never depend on the
model's goodwill.

The backend is a **modular monolith**: Python code organized into modules and
run by several processes. FastAPI serves HTTP, Celery runs the jobs. These
processes share PostgreSQL and the file volume. They are not independent
microservices with their own databases.

The **ports and adapters** pattern is used at the boundaries. Services accept an
object that has the required methods; Python uses `Protocol` here to document
those capabilities. Replacing YOLO or Qdrant does not require rewriting the dwell
rule. You still need to check the new adapter's differences in scores,
coordinates and performance.

## 2. Domain: the stable contracts

### `backend/app/domain/rules.py`

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

### `backend/app/domain/text.py`

`chunk_text()` splits a page into overlapping character windows. `size=1200` and
`overlap=180` are starting values, not universal ones. The overlap keeps some
context between passages. Validation prevents a zero step, and empty pages are
skipped. This is deliberately simple chunking, to be compared later with
structural or token-based chunking.

### `backend/app/domain/ports.py`

`Storage` describes file operations. `Embedder` distinguishes document and query
embeddings. `VectorIndex` exposes indexing, search and point deletion. Tests
inject deterministic objects implementing these methods. They do not change the
business behavior in order to pass.

## 3. Configuration, persistence and security

### `backend/app/config.py`

`Settings` reads environment variables and optionally `.env`. `SecretStr` avoids
accidentally printing secrets in the model's representation. It does not replace
production secret management. `settings()` caches the process configuration and
prepares the data directory.

### `backend/app/db.py`

`Base` is the SQLAlchemy declarative registry. `make_sessions()` creates the
engine and a session factory; a session is a unit of SQL work. SQLite gets
foreign-key and lock-timeout settings. Docker uses PostgreSQL with the same
business schema.

| Table | Why it exists |
|---|---|
| `User` | Account, password hash, role |
| `Video` | Name, storage key and configured rule |
| `Job` | Durable work item, progress, status and error |
| `Incident` | Event, track, video time and evidence |
| `Document` | Immutable document and SHA-256 fingerprint |
| `Chunk` | Canonical text, page and document of a passage |
| `Investigation` | Report, status, author and human decision |

Unique constraints protect integrity even when two processes act at the same
time. They are not replaced by a simple Python `if`.

### `backend/app/auth.py`

`hash_password()` uses PBKDF2-SHA256, a random salt and 600,000 iterations.
The original password is not stored. `verify_password()` recomputes the hash and
compares the bytes with `hmac.compare_digest`.

`token_for()` signs an HS256 JWT valid for eight hours. The API extracts its
`sub`, checks signature and expiry, then reloads the user and role from SQL.
A role change therefore takes effect on the following requests.

### `backend/app/cli.py`

`create-user` prompts for the password with `getpass` and creates a user without
exposing a public sign-up route. `recover-job` resets a stuck job to `queued`
immediately, instead of waiting for the automatic lease recovery (section 9).
Use it only after confirming that the old worker has stopped.

### `backend/migrations/`

`env.py` provides the engine and metadata to Alembic. `0001_initial.py` defines
the initial schema explicitly; it does not just call `create_all()` on models
that may evolve. Any later change requires a new Alembic revision. Isolated
tests use `create_all()` for speed.

## 4. The API: from HTTP to use cases

### `backend/app/api.py`

`create_app()` is a factory: tests pass it a temporary database and a
deterministic dispatcher; the normal launch wires the real dependencies.

`current()` verifies the JWT. `operator()` allows only operators and admins to
perform mutations. Viewers can read the shared workspace. `public()` serializes
the public columns and strips hashes and internal storage keys.

`bounded_upload()` reads the file in blocks, rejects empty files and enforces the
byte limit. The extension is a first check; the video content is actually decoded
in the worker, and PDFs are actually parsed at ingestion.

`upload_video()` validates the zone, stores the file under a UUID key, then saves
the video and the job. The job is committed **before** it is sent to Celery. If
Redis is unavailable, the work stays durably in SQL and the scheduler can
republish it.

`upload_document()` computes SHA-256 to avoid re-indexing the same content. A
second check through an SQL constraint handles concurrent uploads: the loser
falls back to the existing document and deletes its temporary file.

Content routes first look up a video or incident ID in SQL, after authentication.
They never accept an arbitrary file key. In this V1, the video response is loaded
into memory; objects are capped at 100 MB. A high-load version would use
streaming and Range requests, or signed storage URLs after the permission check.

`investigate()` creates the investigation and its job. `review()` performs a
conditional update on `awaiting_review`, so two concurrent clicks cannot produce
two accepted decisions. It records the reviewer, the decision and a resume job.
`retry()` only reactivates failed jobs.

`enqueue()` is deliberately best-effort: publishing is not part of the SQL
transaction. The `jobs` table, the worker's atomic claim and the periodic sweep
form a small **durable outbox**.

### `backend/app/main.py`

Uvicorn entry point: load the configuration, then build the application.
It runs no migration or heavy processing at import time.

## 5. Video, end to end

### `backend/app/adapters/storage.py`

`LocalStorage.path()` resolves the path and requires it to stay under the storage
root. `put()` writes to a temporary file and then replaces the target. `read()`
reads the bytes, `delete()` allows cleanup, and `local_copy()` returns the local
path directly here. A future remote adapter could download into the temporary
path passed to that method.

### `backend/app/adapters/vision.py`

`TrackedObject` holds a normalized box, the detector score and an ID.
`YoloDetector` imports Ultralytics only when instantiated, so the backend and the
business tests work without installing the weights or PyTorch.

One instance is created **per video**, to isolate ByteTrack's state. `track()`
calls YOLO with `persist=True`, the ByteTrack tracker and COCO class `0`
(person). SDK tensors are converted into stable Python objects. `lap` is declared
explicitly to avoid a surprise install on the first tracking call.

### `backend/app/services/video.py`

`VideoService.analyze()` opens the file with OpenCV, checks its properties,
instantiates the detector and processes frames progressively. The timestamp is
`frame_number / fps`, not the time at which the CPU finishes inference.

For each object, the service computes the bottom-center point and calls
`DwellRule.feed()`. When an event fires, it draws the zone and the box on a copy
of the frame, encodes a JPEG, stores the capture and records the incident. The
`(video_id, track_id)` constraint and reading existing events prevent duplicates
on a retry.

`progress()` updates the job every 30 frames. An invalid, oversized, too long or
truncated file fails explicitly. A partially completed analysis may already have
created events: check the job status before treating its list as complete. It is
not a single transaction covering the whole video.

## 6. RAG, end to end

### `backend/app/adapters/vectors.py`

`QdrantIndex.upsert()` creates the collection if needed, using the dimension of
the first vector and cosine distance. IDs are the SQL chunk IDs. `search()`
returns IDs and scores. **The report text is never taken directly from an
unchecked Qdrant payload.** `delete()` exposes point cleanup, with no document
deletion route in this V1.

### `backend/app/services/knowledge.py`

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

### `backend/app/agent/schemas.py`

`Report` enforces a structured output: summary, findings, recommendation,
citations, limitations. `validate_report()` rejects any citation ID missing from
the set actually retrieved during the investigation. Detailed sources are
reattached by the code. Without citations, an explicit limitation is added.

This prevents an invented reference to a non-existent passage; **it does not
prove that every sentence is semantically justified**. Evaluation and human
review are still required.

### `backend/app/agent/investigator.py`

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

### `backend/app/agent/workflow.py`

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

### `backend/app/runtime.py`

This is the **composition root**. `knowledge_service()` selects the embeddings
and Qdrant. `execute()` routes a job type to the right service.

For an investigation, it wires the agent, the MCP server, the checkpoint saver
and the graph. `agent/checkpoints.py` picks the saver: `PostgresSaver` when the
application database is PostgreSQL (`checkpoint_url()` turns the SQLAlchemy URL
`postgresql+psycopg://…` into a plain libpq URL), `SqliteSaver` otherwise. `thread_id` is the investigation ID. A new invocation starts the
graph; a resume uses `Command(resume=...)`. A completed graph is not restarted
when the job is delivered again. If `finalize` failed, it resumes from its
checkpoint without asking the LLM for the report again.

## 8. MCP: a real, limited integration

### `mcp_server/server.py`

A **stdio** MCP server, launched as a local subprocess. `FastMCP` exposes
`search_tickets`, `get_ticket` and `create_ticket`. Data lives in a persistent
SQLite database. The transport opens no network port and needs no OAuth server
here; its trust boundary is the process allowed to launch it.

`create_ticket()` uses a unique idempotency key and `INSERT OR IGNORE`: if the
ticket was created but the response was lost, a new request for the same
investigation returns the same ticket.

### `backend/app/adapters/tickets.py`

`McpTickets` configures `MultiServerMCPClient` with the server path and its
database path. `read_tools()` passes only the two read-only tools to the agent.
`publish()` explicitly calls `create_ticket` from the approved workflow and
checks protocol errors. This is our own ticket system; it does not claim to
write to Jira, Linear or any other unconnected service.

## 9. Jobs and recovery

### `backend/app/tasks.py`

`run_job()` claims the work with `UPDATE ... WHERE status='queued'`. Only the
process that changes the row runs it; other deliveries return. Processing then
moves to `completed` or `failed`, with logs correlated to the ID. The public
error message stays short; details are in the logs.

The claim also records `started_at` and increments `attempts`. `sweep()` first
calls `recover_stale_jobs()`: a job still `running` after `JOB_LEASE_SECONDS`
(1200 s, longer than the 960 s hard time limit, so its worker must be dead) is
requeued, or marked `failed` once it reaches `MAX_JOB_ATTEMPTS` (3). Each change
is a conditional update, so a concurrent claim wins. `sweep()` then republishes
jobs still `queued`. The `processing` queue handles video and documents;
`investigation` handles the agent and the human resume. There is no
exactly-once execution guarantee.

## 10. The frontend, file by file

| File | Explanation |
|---|---|
| `src/main.tsx` | Mounts React and the `QueryClientProvider` that shares cache and mutations |
| `src/types.ts` | TypeScript contracts for the responses used by the UI |
| `src/api.ts` | `request()` adds the Bearer token and handles JSON/FormData and errors; `mediaUrl()` fetches an authenticated blob |
| `src/ZoneEditor.tsx` | Draws the rectangle with Pointer Events; converts screen pixels into normalized coordinates |
| `src/App.tsx` | Sign-in, navigation and the video/procedures/investigations views; mutations and list refresh |
| `src/style.css` | Responsive layout, statuses, forms and evidence display |
| `vite.config.ts` | React build and `/api` proxy in development |
| `nginx.conf` | Serves the build and forwards `/api` to FastAPI |
| `nginx-limits.conf` | Rate-limits sign-in requests at the proxy |

`useMedia()` cancels stale downloads and revokes blob URLs to avoid memory leaks.
The token is never put in a video URL.

`ZoneEditor` keeps the video's intrinsic aspect ratio. Drawing mode overlays the
image; finish the selection to reach the video controls. The zone sent to the
backend matches the image's coordinate frame, not a distorted rectangle.

In `App`, TanStack Query refreshes the lists every 2.5 seconds. After a mutation,
the cache is invalidated. Loading, errors, empty views and failed jobs are shown.
The viewer role hides mutation controls, but **the deciding authorization stays
in FastAPI**.

The JWT is kept in `sessionStorage` for this local application; a public
deployment would need a proper session strategy, CSP and XSS protection.

## 11. Infrastructure and test files

`compose.yaml` assembles the services and volumes. The Dockerfiles build the CPU
backend and the static frontend. `.env.example` documents the configuration;
`scripts/init_env.py` only generates local secrets and never sees the OpenAI key.
`.gitignore` and `.dockerignore` exclude data and secrets.

`requirements.lock` pins the verified backend environment; the vision extra and
CPU PyTorch are installed separately by the Dockerfile. `package-lock.json` pins
the frontend dependencies. `.github/workflows/ci.yml` runs tests, lint and build.

The `tests/test_*.py` files check the rules, permissions, upload concurrency, the
document pipeline, reading a real generated video, the persistent workflow, the
LangChain loop with a scripted provider and the real MCP protocol. Deterministic
test adapters live in the tests and are never enabled as a silent production
mode. `tests/ui_server.py` exists only for the Playwright scenario.

## Suggested reading order

Start with `domain/rules.py`, then `services/video.py`, `api.py` and `tasks.py`.
Next read `services/knowledge.py`, `agent/investigator.py`, `agent/workflow.py`
and `runtime.py`. Finish with MCP, React and Compose: by then each component will
have a clear role in the full flow.
