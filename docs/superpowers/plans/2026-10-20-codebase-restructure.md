# Codebase Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `backend/app/` and `frontend/src/` into folders with self-explanatory names, split the 363-line `api.py` into per-domain routers, and bring every doc in line, without changing behaviour.

**Architecture:** Pure moves and splits, one layer per task, with the full suite green after each task. A layout test (`tests/test_layout.py`) is the red/green driver: it asserts that each new module imports and each old module is gone. Behaviour is pinned by the existing 52 backend tests and 3 Playwright tests, plus the Review Focus tests added in Tasks 3 and 4.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Celery, LangGraph, pytest, ruff; React 18 + TypeScript + Vite + TanStack Query, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-20-codebase-restructure-design.md`

## Global Constraints

- No behaviour change: same HTTP routes, payloads, status codes, DB schema, migration history, env variables, Celery task names (`watchtower.run`, `watchtower.sweep`) and queues (`processing`, `investigation`), and UI text.
- Every task ends with: `pytest` (from `backend/`, 52 passed + 2 skipped at the start; the count only grows), `ruff check app tests migrations`, and for frontend tasks `npm run build` and `npx playwright test` (3 passed).
- English for all project content; Ruff 120 columns; snake_case Python, PascalCase React components and types.
- Use `git mv` for every moved file so history follows it.
- `docs/superpowers/` plans/specs are historical records: do not edit them (except this plan's checkboxes).
- `docs/VERIFICATION.md` past rows keep the commands actually run.
- `mcp_server/` is not touched.
- Work on branch `refactor-codebase-structure`; do not merge into `main`.

## Review Focus

1. A route silently dropped or its method/path/status changed during the router split → Task 4 `test_route_table_is_unchanged`.
2. A viewer reaching an operator route, or a missing token giving something other than 401, after dependencies move → Task 4 `test_role_guards_on_every_write_route`.
3. Jobs routed to the wrong Celery queue (investigate/review must go to `investigation`, everything else to `processing`) → Task 4 `test_enqueue_routes_jobs_to_the_right_queue`.
4. Celery task names or entry points (`uvicorn app.main:app`, `celery -A app.workers.job_queue:celery`, `python -m app.workers.camera_process`) failing to import → Task 3 `test_entry_points_import` and `test_celery_task_names_are_stable`.
5. `create_app(cfg, sessions)` without a hub trying to reach Redis at startup → Task 4 `test_app_starts_without_redis`.

---

## Module map (the decisions every task uses)

| Old path (`backend/app/`) | New path | Contents |
|---|---|---|
| `config.py` | `core/config.py` | `Settings`, `settings()` |
| `auth.py` | `core/security.py` | `hash_password`, `verify_password`, `token_for` |
| `db.py` | `database/models.py` | `Base`, `uid`, `now`, all ORM tables |
| `db.py` | `database/session.py` | `make_sessions` |
| `domain/rules.py` | `domain/dwell_rule.py` | `Zone`, `Observation`, `DwellRule` (pydantic stays) |
| `domain/text.py` | `domain/text_chunking.py` | `chunk_text` |
| `domain/ports.py` | `domain/interfaces.py` | Protocols |
| `adapters/storage.py` | `integrations/local_storage.py` | `LocalStorage` |
| `adapters/vision.py` | `integrations/yolo_detector.py` | `TrackedObject`, `YoloDetector` |
| `adapters/vectors.py` | `integrations/qdrant_index.py` | `QdrantIndex` |
| `adapters/tickets.py` | `integrations/mcp_tickets.py` | `McpTickets` |
| `adapters/camera.py` | `integrations/looped_video_source.py` | `LoopedVideoSource` |
| `adapters/live.py` | `integrations/live_hub.py` | `MemoryHub`, `RedisHub`, subscriptions |
| `services/video.py` | `services/video_analysis.py` | `VideoService` |
| `services/knowledge.py` | `services/knowledge_base.py` | `KnowledgeService` |
| `services/live.py` | `services/camera_monitor.py` | `CameraRunner`, `alert_payload` |
| `services/annotate.py` | `services/frame_annotation.py` | `annotate`, `encode_jpeg` |
| `services/sites.py` | `services/site_seeding.py` | `CameraSeed`, `SiteSeed`, `seed_site` |
| `agent/*` | `investigation/*` | same four file names |
| `tasks.py` | `workers/job_queue.py` | `celery`, `run_job`, `recover_stale_jobs`, `sweep` |
| `runtime.py` | `workers/job_handlers.py` | `knowledge_service`, `execute` |
| `live.py` | `workers/camera_process.py` | `build_runners`, `main` |
| `api.py` | `api/application.py` + `api/routes/*` + `api/schemas.py` + `api/dependencies.py` + `api/uploads.py` | see Task 4 |
| `main.py`, `cli.py` | unchanged | ASGI entry, admin CLI |

Two deviations from the spec tree, recorded here as the builder's call: (a) `create_app` lives in `api/application.py`, not `main.py`, because importing `main.py` calls `settings()` and needs `JWT_SECRET`, which would break tests that build the app with their own settings; `main.py` stays the one-line ASGI entry. (b) `api/schemas.py` is a single file, not a folder: it holds two models (`Login`, `Review`), and a folder of two tiny files is the anti-goal the spec names.

Every package directory gets an `__init__.py` with a one-line docstring that says what the folder holds. Every moved module keeps or gains a one-line module docstring.

---

### Task 1: Core, database and domain layers

**Files:**
- Create: `backend/app/core/__init__.py`, `backend/app/database/__init__.py`, `backend/tests/test_layout.py`
- Move: `config.py` → `core/config.py`; `auth.py` → `core/security.py`; `db.py` → `database/models.py`, plus new `database/session.py`; `domain/rules.py` → `domain/dwell_rule.py`; `domain/text.py` → `domain/text_chunking.py`; `domain/ports.py` → `domain/interfaces.py`
- Modify: every importer (see `grep -rn "app\.\(config\|auth\|db\|domain\)" backend`), `backend/migrations/env.py`

**Interfaces:**
- Produces: `app.core.config.Settings`, `app.core.config.settings`; `app.core.security.{hash_password, verify_password, token_for}`; `app.database.models.{Base, uid, now, User, Video, Job, Incident, Document, Chunk, Investigation, Site, Camera, Alert}`; `app.database.session.make_sessions(url) -> (engine, sessionmaker)`; `app.domain.dwell_rule.{Zone, Observation, DwellRule}`; `app.domain.text_chunking.chunk_text`; `app.domain.interfaces.{Storage, Embedder, VectorIndex, FrameSource, Subscription, LiveHub}`.

- [ ] **Step 1: Write the failing layout test**

```python
import importlib

import pytest

NEW_MODULES = [
    "app.core.config", "app.core.security", "app.database.models", "app.database.session",
    "app.domain.dwell_rule", "app.domain.text_chunking", "app.domain.interfaces",
]
OLD_MODULES = ["app.config", "app.auth", "app.db", "app.domain.rules", "app.domain.text", "app.domain.ports"]


@pytest.mark.parametrize("name", NEW_MODULES)
def test_new_module_imports(name):
    importlib.import_module(name)


@pytest.mark.parametrize("name", OLD_MODULES)
def test_old_module_is_gone(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)
```

- [ ] **Step 2: Run** `pytest tests/test_layout.py -v`. Expected: FAIL (new modules missing, old ones present).
- [ ] **Step 3: Move the files with `git mv`, split `make_sessions` into `database/session.py`, update every import.** `models.py` does not import `session.py`; `session.py` may import nothing from models.
- [ ] **Step 4: Run** `pytest` and `ruff check app tests migrations`. Expected: all green, layout tests pass, 52 + new layout tests passed, 2 skipped.
- [ ] **Step 5: Commit** `git commit -m "Move config, security, database and domain into their own packages"`

### Task 2: Integrations, services and investigation packages

**Files:**
- Create: `backend/app/integrations/__init__.py`, `backend/app/investigation/__init__.py`
- Move: `adapters/*` → `integrations/*` and `services/*` → new names, per the module map; `agent/` → `investigation/` (`git mv backend/app/agent backend/app/investigation`). Delete the empty `adapters/` package.
- Modify: every importer, `backend/tests/ui_server.py`, `backend/tests/test_layout.py`

**Interfaces:**
- Consumes: Task 1 paths.
- Produces: the integration, service and investigation paths in the module map, same class and function names.

- [ ] **Step 1: Extend `NEW_MODULES`/`OLD_MODULES` in `test_layout.py`** with the 6 integration modules, 5 service modules, 4 investigation modules (new) and `app.adapters`, `app.agent`, `app.services.video`, `app.services.knowledge`, `app.services.live`, `app.services.annotate`, `app.services.sites` (old).
- [ ] **Step 2: Run** `pytest tests/test_layout.py -v`. Expected: FAIL on the new entries.
- [ ] **Step 3: Move and re-import.** Lazy imports inside functions (`api.py` RedisHub, `live.py` YoloDetector) are updated too.
- [ ] **Step 4: Run** `pytest` and ruff. Expected: all green.
- [ ] **Step 5: Commit** `git commit -m "Rename adapters to integrations and give services descriptive names"`

### Task 3: Workers package and entry points

**Files:**
- Create: `backend/app/workers/__init__.py`, `backend/tests/test_entry_points.py`
- Move: `tasks.py` → `workers/job_queue.py`; `runtime.py` → `workers/job_handlers.py`; `live.py` → `workers/camera_process.py`
- Modify: `compose.yaml` (lines 66, 73, 80, 86: `app.workers.job_queue:celery`, `python -m app.workers.camera_process`), `camera_process.py` module docstring and its log hint, `cli.py`, `api.py` lazy `run_job` import, `tests/test_jobs.py` (`from app.workers import job_handlers, job_queue`; monkeypatch `job_handlers.execute` and `job_queue.cfg`), `tests/test_camera.py`, `test_layout.py`

**Interfaces:**
- Produces: `app.workers.job_queue.{celery, run_job, recover_stale_jobs, sweep}`; `app.workers.job_handlers.{knowledge_service, execute}`; `app.workers.camera_process.{build_runners, main}`. `run_job` keeps its lazy `from app.workers.job_handlers import execute` so monkeypatching `job_handlers.execute` keeps working.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_entry_points.py
import importlib


def test_entry_points_import(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", "entry-test-secret-not-for-production-1234")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/entry.db")
    from app.core.config import settings
    settings.cache_clear()
    for name in ("app.main", "app.cli", "app.workers.job_queue", "app.workers.camera_process"):
        importlib.import_module(name)
    settings.cache_clear()


def test_celery_task_names_are_stable():
    from app.workers.job_queue import celery
    assert {"watchtower.run", "watchtower.sweep"} <= set(celery.tasks)
```

Add `app.workers.*` to `NEW_MODULES` and `app.tasks`, `app.runtime`, `app.live` to `OLD_MODULES`.

- [ ] **Step 2: Run** `pytest tests/test_entry_points.py tests/test_layout.py -v`. Expected: FAIL (`app.workers` missing).
- [ ] **Step 3: Move, update importers and `compose.yaml`.** Check the beat schedule inside `job_queue.py` references the task by name, not module path.
- [ ] **Step 4: Run** `pytest`, ruff, and `docker compose config --quiet` (if Docker is unavailable, say so in the report). Expected: green.
- [ ] **Step 5: Commit** `git commit -m "Group background processes under workers"`

### Task 4: Split the HTTP API into routers

**Files:**
- Create: `backend/app/api/__init__.py`, `api/application.py`, `api/dependencies.py`, `api/schemas.py`, `api/uploads.py`, `api/routes/__init__.py`, and routers `api/routes/{health,auth,videos,jobs,documents,incidents,investigations,cameras,alerts,live_events}.py`
- Delete: `backend/app/api.py`
- Modify: `backend/app/main.py`, `backend/tests/test_api.py`, `backend/tests/ui_server.py`, `test_layout.py`
- Test: `backend/tests/test_api.py` (new tests below)

**Interfaces:**
- Consumes: Tasks 1–3 paths.
- Produces:
  - `app.api.application.create_app(cfg: Settings, sessions=None, dispatcher=None, hub=None) -> FastAPI` — same signature and defaults as today. Stores `cfg`, `sessions`, `storage`, `hub` and a `JobDispatcher` on `app.state`, adds CORS, includes every router.
  - `app.api.dependencies`: `get_settings(request) -> Settings`, `get_sessions(request)`, `get_storage(request) -> LocalStorage`, `get_hub(request)`, `get_dispatcher(request) -> JobDispatcher`, `current_user(...) -> User` (401 cases unchanged), `require_operator(user) -> User` (403 unchanged), `call_live_hub(call, *args)` (503 wrapper, was `live`).
  - `app.api.dependencies.JobDispatcher(sessions, dispatcher=None)` with `.enqueue(job_id) -> None`: same queue choice and same "log and keep the SQL job queued" behaviour as today's `enqueue`.
  - `app.api.schemas.{Login, Review, public}` — `public(row) -> dict` hides the same five columns.
  - `app.api.uploads.receive_upload(file: UploadFile, data_dir: Path, max_upload_mb: int) -> tuple[Path, str]`.
  - Each `api/routes/<domain>.py` exposes `router = APIRouter()`; full paths stay in the decorators (`/api/videos`, ...), no prefixes, so a grep for a URL finds its handler.
  - `main.py`: `from app.api.application import create_app` then `app = create_app(settings())`.

- [ ] **Step 1: Write the failing Review Focus tests in `tests/test_api.py`** (they use the existing `app_client` / `live_client` fixtures; adapt fixture names if they differ)

```python
EXPECTED_ROUTES = {
    ("GET", "/api/health"), ("POST", "/api/auth/login"), ("GET", "/api/me"),
    ("GET", "/api/videos"), ("POST", "/api/videos"), ("GET", "/api/videos/{video_id}/content"),
    ("GET", "/api/jobs"), ("POST", "/api/jobs/{job_id}/retry"),
    ("GET", "/api/documents"), ("POST", "/api/documents"),
    ("GET", "/api/incidents"), ("GET", "/api/incidents/{incident_id}/evidence"),
    ("POST", "/api/incidents/{incident_id}/investigate"),
    ("GET", "/api/investigations"), ("POST", "/api/investigations/{investigation_id}/review"),
    ("GET", "/api/cameras"), ("GET", "/api/cameras/{camera_id}/frame"),
    ("GET", "/api/alerts"), ("GET", "/api/alerts/{alert_id}/snapshot"), ("GET", "/api/live/events"),
}

def test_route_table_is_unchanged(app_client):
    routes = {(m, r.path) for r in app_client.app.routes if r.path.startswith("/api/") and hasattr(r, "methods")
              for m in r.methods if m != "HEAD"}
    assert EXPECTED_ROUTES <= routes
    assert {r for r in routes if not r[1].startswith("/api/docs") and r[1] != "/api/openapi.json"} == EXPECTED_ROUTES

def test_role_guards_on_every_write_route(app_client):
    # viewer token -> 403 and no token -> 401 for: POST /api/videos, /api/jobs/x/retry, /api/documents,
    # /api/incidents/x/investigate, /api/investigations/x/review
    ...

def test_enqueue_routes_jobs_to_the_right_queue(tmp_path, monkeypatch):
    # JobDispatcher(sessions) with job_queue.run_job.apply_async monkeypatched to record (args, queue):
    # kinds "investigate" and "review" -> queue "investigation"; "video" and "document" -> "processing"
    ...

def test_app_starts_without_redis(tmp_path):
    # create_app(Settings(..., redis_url="redis://127.0.0.1:1/0"), sessions) builds and GET /api/health == 200
    ...
```

The `...` bodies follow the assertions in their comments, using the existing helpers in `test_api.py` for users and tokens. Change the import at the top to `from app.api.application import create_app`. Add `app.api.application`, `app.api.dependencies`, `app.api.schemas`, `app.api.uploads` and the ten router modules to `NEW_MODULES`.

- [ ] **Step 2: Run** `pytest tests/test_api.py tests/test_layout.py -v`. Expected: FAIL on import of `app.api.application`.
- [ ] **Step 3: Split `api.py`** following the Interfaces block. Bodies move as they are; only the dependency access changes (from closure variables to `Depends(get_...)`). Keep `tests/ui_server.py` building the app the same way.
- [ ] **Step 4: Run** `pytest`, ruff, then `npx playwright test` from `frontend/` (the UI server uses `create_app`). Expected: all green, including the 4 new tests.
- [ ] **Step 5: Commit** `git commit -m "Split the HTTP API into one router per domain"`

### Task 5: Mirror the layout in the test suite

**Files:**
- Move (`git mv`, from `backend/tests/`):
  - `test_api.py` → `api/test_routes.py`; `test_layout.py`, `test_entry_points.py` stay at the root
  - `test_domain.py` → `domain/test_domain_rules.py`
  - `test_migrations.py` → `database/test_migrations.py`
  - `test_video.py` → `services/test_video_analysis.py`; `test_rag.py` → `services/test_knowledge_base.py`; `test_camera.py` → `services/test_camera_monitor.py`; `test_live.py` → `services/test_site_seeding.py`
  - `test_agent.py` → `investigation/test_investigator.py`; `test_workflow.py`, `test_checkpoints.py` → `investigation/`
  - `test_mcp.py` → `integrations/test_mcp_tickets.py`; `test_vectors.py` → `integrations/test_qdrant_index.py`
  - `test_jobs.py` → `workers/test_job_queue.py`
  - `ui_server.py` → `support/ui_server.py`
- Modify: `Path(__file__).resolve().parents[N]` in the moved files (`test_agent`, `test_live`, `test_mcp`: 2 → 3; `test_migrations`: 1 → 2), `frontend/playwright.config.ts` (`--app-dir ../backend/tests/support`)

No `__init__.py` in test folders: basenames are unique, and the default rootdir import mode handles them.

- [ ] **Step 1: Record the count** `pytest -q | tail -1` before moving (N passed, 2 skipped).
- [ ] **Step 2: Move and fix paths.**
- [ ] **Step 3: Run** `pytest -q`. Expected: the same N passed, 2 skipped. A lower count means a file is no longer collected.
- [ ] **Step 4: Run** `npx playwright test`. Expected: 3 passed.
- [ ] **Step 5: Commit** `git commit -m "Organize backend tests like the application packages"`

### Task 6: Frontend folders and one page per tab

**Files (from `frontend/src/`):**
- Move: `api.ts` → `api/client.ts`; `types.ts` → `api/types.ts`; `LiveWall.tsx` → `pages/LiveCamerasPage.tsx`; `ZoneEditor.tsx` → `components/ZoneEditor.tsx`; `style.css` → `styles/global.css`
- Create from `App.tsx`: `pages/LoginPage.tsx` (`Login`), `pages/VideoAnalysisPage.tsx` (the `workspace` tab), `pages/ProceduresPage.tsx` (the `knowledge` tab), `pages/InvestigationsPage.tsx`, `components/StatusBadge.tsx` (`Status` + `labels`), `components/EvidenceImage.tsx` (`Evidence`), `api/media.ts` (`useMedia` next to `mediaUrl`), `api/queries.ts` (`useList`)
- Modify: `App.tsx` (keeps token/session, user query, tab state, sidebar, header counts, notice/error banner), `main.tsx`

**Interfaces:**
- `useList<T>(name: string, token: string, enabled: boolean)` in `api/queries.ts`, same query key `[name, token]` and `refetchInterval: 2500`, so App and pages share one cache entry per list.
- Pages receive `{ token: string; canWrite: boolean; onNotice: (text: string) => void; onError?: ... }` as needed; `VideoAnalysisPage` also gets `onOpenInvestigations: () => void` (today's `setTab("investigations")`). Exact prop sets are the builder's call; visible text, roles, labels and behaviour must not change.
- Default exports for page and component files, as `LiveWall` and `ZoneEditor` do today.

- [ ] **Step 1: Run** `npx playwright test` and `npm run build` on the untouched tree. Expected: 3 passed, build OK (baseline).
- [ ] **Step 2: Move files and split `App.tsx`.**
- [ ] **Step 3: Run** `npm run build`. Expected: no TypeScript errors.
- [ ] **Step 4: Run** `npx playwright test`. Expected: 3 passed, with no selector changed in `frontend/tests/`.
- [ ] **Step 5: Commit** `git commit -m "Organize the frontend into api, pages, components and styles"`

### Task 7: Readability pass and documentation

**Files:**
- Modify: backend and frontend files touched above, only for names and docstrings; `docs/GUIDE.md` (sections 2–11 retitled to the new paths, a new section 0 showing the folder tree with one line per folder), `docs/OPERATIONS.md` (commands at lines ~12, 70, 135, 153–167), `README.md` (a short "Project layout" section after "Reading and understanding the project"), `AGENTS.md` ("Project Structure & Architecture"), `docs/VERIFICATION.md` (old → new path table and a new "Restructure (2026-10-20)" entry filled in by Task 8)

- [ ] **Step 1: Readability edits.** Rename unclear local names you met while moving code (e.g. `cfg`-shadowing, one-letter loop variables over rows in routers) only where the new name is clearly better; add a one-line docstring to modules and to non-obvious functions; remove dead code. No logic edits.
- [ ] **Step 2: Docs.** Then verify no stale path remains:

Run: `grep -rnE "app/(api\.py|db\.py|auth\.py|config\.py|runtime\.py|tasks\.py|live\.py|adapters|agent/)|app\.(tasks|live|runtime|db|auth|api)\b|src/(LiveWall|api\.ts|types\.ts|style\.css|ZoneEditor)" --include=*.md --include=*.yaml --include=*.yml --include=*.ts --include=*.py --include=Dockerfile . | grep -v -e node_modules -e .venv -e docs/superpowers/ -e .remember/`
Expected: matches only in the historical rows and the old → new table of `docs/VERIFICATION.md`.

- [ ] **Step 3: Run** `pytest`, ruff, `npm run build`, `npx playwright test`. Expected: green.
- [ ] **Step 4: Commit** `git commit -m "Document the new project layout and tidy names"`

### Task 8: Independent review and final verification

- [ ] **Step 1: Whole-branch review** by a separate reviewer agent (superpowers:requesting-code-review) over `main...refactor-codebase-structure`, briefed with the spec, this plan and the Review Focus list. Ask in particular for behaviour changes hidden in moves.
- [ ] **Step 2: Fix findings.** Any finding that is a bug gets a failing test first, then the fix.
- [ ] **Step 3: Final verification**: `pytest`, `ruff check app tests migrations`, `npm run build`, `npx playwright test`, and boot check: from `backend/` with a throwaway `JWT_SECRET` and SQLite URL, `python -m uvicorn app.main:app --port 8012` then `curl http://127.0.0.1:8012/api/health` returns `{"status":"ok","version":"0.1.0"}`. Docker image build only if Docker is available; otherwise record "not run".
- [ ] **Step 4: Record results** in the new `docs/VERIFICATION.md` entry, listing what was not run. Commit `git commit -m "Record restructure verification"`.
- [ ] **Step 5: Stop.** Report to the owner; merging waits for their go-ahead.
