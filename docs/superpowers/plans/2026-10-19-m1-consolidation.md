# Milestone 1 — Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing backend reliable enough to carry live features: jobs never stay stuck in `running`, LangGraph checkpoints can live in PostgreSQL, and videos are uploaded and served without loading whole files into memory.

**Architecture:** Three independent hardening changes. (1) A time-based lease on jobs, enforced by the existing Celery Beat sweep. (2) A checkpointer factory that picks `PostgresSaver` when the app database is PostgreSQL and keeps `SqliteSaver` otherwise. (3) Uploads streamed to a temporary file and moved into storage; video content served with Starlette's `FileResponse` (Range support).

**Tech Stack:** Python 3.12, FastAPI 0.146 / Starlette 1.9, SQLAlchemy 2.1, Alembic, Celery 5.6, LangGraph 1.2.16 (`langgraph-checkpoint` 4.3.0), `langgraph-checkpoint-postgres` (new), psycopg 3.3.6, pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-live-dangerous-object-alerting-design.md` (milestone 1, "Consolidate first"). Background on the stuck-job bug: `docs/OPERATIONS.md`, section "Diagnosis and recovery".

## Global Constraints

- All project content (code, comments, docs, commit messages) in English.
- Tests use deterministic doubles; no test may require PostgreSQL, Redis, OpenAI or YOLO unless it is skipped when the service is absent.
- Ruff line length 120; run `ruff check app tests migrations` from `backend/`.
- Run tests with the Python 3.12 environment: `backend/.venv/Scripts/python -m pytest` (the global Python 3.14 cannot import the locked dependencies).
- Never commit `.env`, videos or generated evidence.
- Schema changes go through a new Alembic revision; `tests/test_migrations.py` must keep passing (models and migrations identical).
- Existing behavior stays: upload, dwell rule, investigations, review, retry, `recover-job` CLI.

## Review Focus

1. A job that crashes its worker every time (OOM on a huge video) must not be requeued forever → after `MAX_JOB_ATTEMPTS` it becomes `failed`. (Task 1, `test_poison_job_fails_after_max_attempts`)
2. A long but healthy job (LLM investigation near its time limit) must not be stolen by the sweep → lease longer than Celery's hard `time_limit`. (Task 1, `test_sweep_leaves_recent_running_jobs_alone`)
3. Sweep and a late worker racing on the same stale job must requeue it at most once → conditional update on `status` and `started_at`. (Task 1, `test_requeue_is_conditional`)
4. An upload rejected for size, or a client that disconnects mid-upload, must not leave temporary files behind. (Task 3, `test_oversized_upload_leaves_no_temp_file`)
5. The Docker `DATABASE_URL` uses the SQLAlchemy form `postgresql+psycopg://…`, which LangGraph's saver does not accept → it must be converted. (Task 2, `test_checkpoint_url_strips_driver`)

---

### Task 1: Job lease and automatic recovery of stuck jobs

**Files:**
- Modify: `backend/app/db.py` (class `Job`)
- Create: `backend/migrations/versions/0002_job_lease.py`
- Modify: `backend/app/tasks.py` (`run_job`, `sweep`)
- Modify: `docs/OPERATIONS.md` (sections "States and consistency", "Diagnosis and recovery"), `docs/GUIDE.md` (section 9)
- Test: `backend/tests/test_jobs.py`

**Interfaces:**
- Produces: `Job.started_at: Mapped[datetime | None]`, `Job.attempts: Mapped[int]` (default 0); constants `JOB_LEASE_SECONDS = 1200` and `MAX_JOB_ATTEMPTS = 3` in `app/tasks.py`; function `recover_stale_jobs(sessions, now: datetime) -> list[str]` in `app/tasks.py` returning the IDs it requeued.

Why 1200: `run_job` has `time_limit=960`, so a live worker can never hold a job longer than 960 s; anything `running` for more than 1200 s belongs to a dead worker.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_jobs.py`, reusing the setup pattern of the existing test (env vars, `settings.cache_clear()`, `Base.metadata.create_all`).

```python
def test_claim_sets_started_at_and_counts_attempts(...):
    # Job "a" queued; run_job.run("a") with runtime.execute patched to a no-op
    assert row.attempts == 1 and row.started_at is not None

def test_stale_running_job_is_requeued(...):
    # Job running, attempts=1, started_at = now - 1300 s
    assert tasks.recover_stale_jobs(sessions, now) == ["stale"]
    assert row.status == "queued" and row.started_at is None

def test_sweep_leaves_recent_running_jobs_alone(...):
    # started_at = now - 100 s
    assert tasks.recover_stale_jobs(sessions, now) == []
    assert row.status == "running"

def test_poison_job_fails_after_max_attempts(...):
    # running, attempts=3, started_at = now - 1300 s
    assert tasks.recover_stale_jobs(sessions, now) == []
    assert row.status == "failed" and "worker" in row.error.lower()

def test_requeue_is_conditional(...):
    # call recover_stale_jobs twice with the same stale job
    assert first == ["stale"] and second == []
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `backend/.venv/Scripts/python -m pytest backend/tests/test_jobs.py -v`
Expected: FAIL (`Job` has no `attempts` / `recover_stale_jobs` not defined).

- [ ] **Step 3: Add the columns and the migration**

`Job.started_at` (`DateTime(timezone=True)`, nullable) and `Job.attempts` (`Integer`, not null, default 0). Migration `0002` (`down_revision = "0001"`) adds both with `server_default="0"` for `attempts` and drops them in `downgrade()`. The model must declare a matching `server_default` so `test_migrations.py` stays green.

- [ ] **Step 4: Update the claim in `run_job`**

The claiming `UPDATE ... WHERE status == "queued"` also sets `started_at=now()` and `attempts=Job.attempts + 1`. Completion and failure keep their current behavior.

- [ ] **Step 5: Implement `recover_stale_jobs(sessions, now)` and call it at the start of `sweep()`**

For each `running` job with `started_at < now - JOB_LEASE_SECONDS`: if `attempts >= MAX_JOB_ATTEMPTS`, set `failed` with error `"Worker stopped repeatedly; check the worker logs."`; otherwise set `queued`, `started_at=None`. Each change is a conditional `UPDATE` whose `WHERE` repeats `status == "running"` and the `started_at` value read, so a concurrent change wins and the job is skipped. `sweep()` then republishes queued jobs exactly as today. Compare datetimes in UTC; SQLite returns naive datetimes, so normalize with `replace(tzinfo=timezone.utc)` when `tzinfo` is missing.

- [ ] **Step 6: Run the whole backend suite**

Run: `backend/.venv/Scripts/python -m pytest -q` (from `backend/`) and `backend/.venv/Scripts/python -m ruff check app tests migrations`
Expected: all tests pass (19 existing + 5 new), ruff clean.

- [ ] **Step 7: Update the docs**

`OPERATIONS.md`: a `running` job older than 20 minutes is requeued automatically by the scheduler, and failed after 3 attempts; `recover-job` remains for immediate manual recovery. Remove the sentence saying the sweep does not repair a crash. `GUIDE.md` section 9: same facts, replacing "the recovery command is then required".

- [ ] **Step 8: Commit**

```bash
git add backend/app/db.py backend/app/tasks.py backend/migrations/versions/0002_job_lease.py backend/tests/test_jobs.py docs/OPERATIONS.md docs/GUIDE.md
git commit -m "Recover jobs left running by a dead worker"
```

### Task 2: PostgreSQL checkpointer for LangGraph

**Files:**
- Create: `backend/app/agent/checkpoints.py`
- Modify: `backend/app/runtime.py` (the `investigate`/`review` branch of `execute`)
- Modify: `backend/pyproject.toml`, `backend/requirements.lock`
- Modify: `compose.yaml` (comment on the `investigator` service), `docs/OPERATIONS.md`, `docs/GUIDE.md` (`runtime.py` section), `README.md` ("Known limitations")
- Test: `backend/tests/test_checkpoints.py`

**Interfaces:**
- Produces: `checkpoint_url(database_url: str) -> str | None` (returns a libpq URL for PostgreSQL URLs, `None` otherwise) and a context manager `open_checkpointer(database_url: str, data_dir: Path) -> Iterator[BaseCheckpointSaver]` in `app/agent/checkpoints.py`.
- Consumes: `build_workflow(checkpointer, ...)` from `app/agent/workflow.py` (unchanged).

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_checkpoints.py`

```python
def test_checkpoint_url_strips_driver():
    assert checkpoint_url("postgresql+psycopg://u:p@db:5432/w") == "postgresql://u:p@db:5432/w"
    assert checkpoint_url("postgresql://u:p@db/w") == "postgresql://u:p@db/w"
    assert checkpoint_url("sqlite:///./data/w.db") is None

def test_sqlite_checkpointer_persists_between_openings(tmp_path):
    # open_checkpointer("sqlite:///x.db", tmp_path) → build_workflow → invoke until interrupt;
    # reopen → graph.get_state(config).next == ("human_review",)

@pytest.mark.skipif(not os.environ.get("WATCHTOWER_TEST_POSTGRES_URL"), reason="needs PostgreSQL")
def test_postgres_checkpointer_round_trip():
    # same scenario against WATCHTOWER_TEST_POSTGRES_URL
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `backend/.venv/Scripts/python -m pytest backend/tests/test_checkpoints.py -v`
Expected: FAIL (module `app.agent.checkpoints` not found); the Postgres test is skipped.

- [ ] **Step 3: Add the dependency**

Add `langgraph-checkpoint-postgres` to `pyproject.toml` dependencies, pinned to the newest release compatible with `langgraph-checkpoint==4.3.0`, and regenerate or extend `requirements.lock` so `pip check` passes.

- [ ] **Step 4: Implement `app/agent/checkpoints.py`**

PostgreSQL: `PostgresSaver.from_conn_string(url)`, call `setup()` once on entry (idempotent), yield it. Otherwise: `sqlite3.connect(data_dir / "checkpoints.db", check_same_thread=False)` wrapped in `SqliteSaver`, closed on exit. This replaces the inline SQLite code in `runtime.py`.

- [ ] **Step 5: Use it in `runtime.execute`**

Replace the `sqlite3.connect(...)` block with `with open_checkpointer(cfg.database_url, cfg.data_dir) as saver:`. The rest of the branch (thread ID, resume, redelivery guard) is unchanged.

- [ ] **Step 6: Run the whole backend suite and ruff**

Expected: all pass, Postgres test skipped.

- [ ] **Step 7: Update compose and docs**

`compose.yaml`: replace the "Singleton protects the SQLite checkpoint saver. Do not scale this service." comment with one saying checkpoints live in PostgreSQL. Keep `--concurrency=1`. `OPERATIONS.md`, `GUIDE.md` and `README.md`: checkpoints are in PostgreSQL under Docker and in SQLite for local development; remove the "single investigation worker" limitation.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent/checkpoints.py backend/app/runtime.py backend/pyproject.toml backend/requirements.lock backend/tests/test_checkpoints.py compose.yaml docs/OPERATIONS.md docs/GUIDE.md README.md
git commit -m "Store LangGraph checkpoints in PostgreSQL when available"
```

### Task 3: Streamed uploads and video responses

**Files:**
- Modify: `backend/app/adapters/storage.py` (`LocalStorage`)
- Modify: `backend/app/api.py` (`bounded_upload`, `upload_video`, `upload_document`, `video_content`)
- Modify: `docs/GUIDE.md` (section 4), `README.md` if it mentions in-memory video
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `LocalStorage.put_file(key: str, source: Path) -> None` (moves `source` into storage, atomic replace) and, in `api.py`, `async def receive_upload(file: UploadFile) -> tuple[Path, str]` returning a temporary file path under `cfg.data_dir / "uploads"` and the SHA-256 hex digest of its content.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_api.py`, using the existing `app_client` fixture and `login` helper.

```python
def test_video_content_supports_range_requests(app_client, tmp_path):
    # upload a small .mp4 (bytes b"0123456789" * 100) with a valid zone
    response = client.get(f"/api/videos/{vid}/content", headers={**headers, "Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.content == b"0123456789"

def test_oversized_upload_leaves_no_temp_file(app_client, tmp_path):
    # Settings(max_upload_mb=1) fixture variant; upload 1 MB + 1 byte
    assert response.status_code == 413
    assert list((tmp_path / "uploads").glob("*")) == []

def test_document_dedup_still_uses_sha256(app_client):
    # same TXT uploaded twice → same document id, one job queued
```

- [ ] **Step 2: Run them and confirm they fail**

Expected: the Range test fails (200 instead of 206); the temp-file test fails or errors.

- [ ] **Step 3: Implement `LocalStorage.put_file`**

Validate the key with `path()`, create parent directories, then `Path.replace`. `uploads/` and `files/` are both under `data_dir`, so the move stays on one filesystem.

- [ ] **Step 4: Replace `bounded_upload` with `receive_upload`**

Read 1 MiB chunks into a `NamedTemporaryFile(dir=data_dir / "uploads", delete=False)` while updating a `hashlib.sha256`; on size overflow, empty file or any exception, delete the temp file and re-raise (413 / 422 unchanged). `upload_video` and `upload_document` call `storage.put_file` with the temp path; `upload_document` uses the returned digest and deletes the temp file when the content is a duplicate.

- [ ] **Step 5: Serve videos with `FileResponse`**

`video_content` returns `FileResponse(storage.path(video.storage_key), media_type=...)` with the same media type as today. Evidence JPEGs may stay as they are (small files).

- [ ] **Step 6: Run the whole backend suite and ruff**

Expected: all pass.

- [ ] **Step 7: Update the docs**

`GUIDE.md` section 4: uploads are streamed to disk and hashed on the fly; video responses are streamed with Range support. Remove "the video response is loaded into memory". Note that the React client still downloads the video as an authenticated blob, so browser seeking benefits only once a later milestone switches to a streaming URL.

- [ ] **Step 8: Commit**

```bash
git add backend/app/adapters/storage.py backend/app/api.py backend/tests/test_api.py docs/GUIDE.md README.md
git commit -m "Stream uploads to disk and serve videos with Range support"
```

## After the three tasks

Run the full verification from `docs/VERIFICATION.md` (backend tests, ruff, `npm run build`), then push and check that the GitHub Actions run is green. Update `docs/VERIFICATION.md` with what was actually run in this milestone.
