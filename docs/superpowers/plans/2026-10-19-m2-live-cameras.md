# Milestone 2 — Live cameras + push alerts (people only)

## Context

The approved design (`docs/superpowers/specs/2026-10-19-live-dangerous-object-alerting-design.md`)
turns WatchTower into a live surveillance and alerting system. Milestone 1 (consolidation) is merged
and pushed (CI green on `9e16698`). Milestone 2 makes the system *live*: several "cameras" (looped
video files replayed at real-time pace) are analyzed continuously, the operator sees them on a
**camera wall (layout A)**, and alerts are **pushed** to the screen within about a second.
Detection stays **people only** with the existing `DwellRule` (dangerous objects are Milestone 3,
the VLM Milestone 4, Confirm/False alarm with the LangGraph workflow Milestone 5).

On execution, this plan is first copied to `docs/superpowers/plans/2026-10-19-m2-live-cameras.md`
and run inline on a branch `m2-live-cameras` (same process as M1: TDD per task, one final review).

## Global constraints

- All project content in English; deterministic test doubles for YOLO (no model download in tests).
- No videos, frames or `.env` in git. Demo videos live under `data/cameras/` (gitignored `data/`).
- CPU only: analysis rate configurable, default `live_analysis_fps = 5`; frames are dropped,
  never queued, when analysis is slower than real time.
- No new heavy dependency: Redis (already in the stack) carries live frames and events; JSON seed
  file (no PyYAML).
- Existing upload → analysis → investigation path keeps working unchanged.

## Architecture (designer's calls)

```
looped video ─► FrameSource ─► CameraRunner (1 thread / camera)
                                 ├─ YoloDetector.track (people)  ─► DwellRule(camera zone)
                                 ├─ LiveHub.put_frame(camera, annotated JPEG)   (latest only)
                                 ├─ LiveHub.put_status(camera, frames_analyzed, fps)
                                 └─ on alert: Alert row (SQL) + snapshot + LiveHub.publish(event)
API: GET /api/cameras, /api/cameras/{id}/frame, /api/alerts, /api/alerts/{id}/snapshot,
     GET /api/live/events  (Server-Sent Events, fed by LiveHub.subscribe)
UI:  "Live" tab = camera wall grid + red alert banner
```

- **SSE over WebSocket:** one-way server→browser is all we need, works through nginx with
  buffering off. The browser reads it with `fetch` + stream reader (not `EventSource`) so the
  bearer token stays in the `Authorization` header, never in a URL.
- **Tiles** refresh the latest annotated JPEG by `fetch` ~2×/s per tile (boxes drawn server-side).
  Honest label: near-live snapshots, not video streaming. Alerts themselves are pushed.
- **One `cameras` process** (`python -m app.live`), one thread per camera, each with its own
  detector instance (tracker state is per camera). On loop restart the detector and rule are
  rebuilt so recycled track IDs cannot be suppressed.
- **`LiveHub` port** with a Redis adapter (prod) and an in-memory adapter (tests).

## Tasks

### Task 1 — Sites, cameras, alerts in the database + seed command
- `backend/app/db.py`: `Site(id, name)`, `Camera(id, site_id→sites, name, source, zone JSON|None,
  labels JSON list, enabled bool)`, `Alert(id, camera_id→cameras, kind="person_dwell", status
  ="open", created_at, snapshot_key, details JSON {track_id, box, confidence, zone})`.
- `backend/migrations/versions/0003_live_cameras.py` (pattern of `0002_job_lease.py`);
  `tests/test_migrations.py` schema comparison must still pass.
- `backend/app/cli.py`: `seed-site PATH` — upserts a site and its cameras from JSON by name
  (idempotent: re-running updates, never duplicates).
- `examples/site-horizon.json`: fictional "Horizon Cultural Center" (hall, reception, corridor,
  parking, cafeteria kitchen), sources `/data/cameras/<name>.mp4`, labelled fictional.
- Tests (`tests/test_live.py`): seed twice → same rows, updated fields; invalid zone rejected.

### Task 2 — Frame source and camera runner (pure, testable)
- `backend/app/domain/ports.py`: add `FrameSource` (`read() -> frame | None`, `fps`, `restart()`)
  and `LiveHub` (`put_frame`, `get_frame`, `put_status`, `get_status`, `publish`, `subscribe`).
- `backend/app/adapters/camera.py`: `LoopedVideoSource(path)` — OpenCV, loops at end.
- `backend/app/services/live.py`: `CameraRunner(camera, source, detector_factory, hub, sessions,
  storage, clock, analysis_fps)` with `step()` (one analyzed frame) and `run(stop_event)`.
  Pacing: target frame index = elapsed × fps; `grab()` to skip late frames; analyze one frame per
  `1/analysis_fps`. Reuses `DwellRule`/`Observation` from `app/domain/rules.py` and the drawing /
  JPEG code currently inline in `app/services/video.py` (extract `annotate(frame, zone, box)` into
  a shared helper used by both, no behavior change for uploads).
- Tests with a generated MJPG clip (as in `tests/test_video.py`), a fake detector, a fake clock
  and the in-memory hub:
  - frames analyzed counter grows, latest frame is a JPEG;
  - a person dwelling in the zone creates exactly one `Alert` + snapshot + one published event;
  - late clock → frames are skipped (analyzed count ≈ analysis_fps × elapsed, not every frame);
  - loop restart rebuilds the detector (recycled track ID alerts again);
  - camera with no zone never alerts but still streams frames;
  - unreadable source → camera status `error`, runner does not crash the other cameras.

### Task 3 — Hub adapters + live process
- `backend/app/adapters/live.py`: `MemoryHub` (tests, thread-safe) and `RedisHub(redis_url)`
  (`SET` latest frame with short TTL, `HSET` status, `PUBLISH`/`SUBSCRIBE` on `watchtower:alerts`).
- `backend/app/live.py`: `main()` loads enabled cameras, starts a `CameraRunner` thread each with
  `YoloDetector(cfg.yolo_model)`, stops cleanly on SIGTERM.
- `backend/app/config.py`: `live_analysis_fps: float = 5`, `cameras_dir: Path`.
- `compose.yaml`: service `cameras` (`<<: *backend`, `command: [python, -m, app.live]`, depends on
  migrate). `.gitignore` already covers `data/`.
- Tests: `MemoryHub` publish/subscribe and frame TTL semantics; `RedisHub` test skipped unless
  `WATCHTOWER_TEST_REDIS_URL` is set (same convention as the Postgres test).

### Task 4 — API endpoints + SSE
- `backend/app/api.py` (`create_app(cfg, sessions, dispatcher, hub=None)`; default `RedisHub`):
  - `GET /api/cameras` → cameras + live status (frames analyzed, fps, state, last seen);
  - `GET /api/cameras/{id}/frame` → latest JPEG, 404 if none yet (`Cache-Control: no-store`);
  - `GET /api/alerts?limit=50` newest first; `GET /api/alerts/{id}/snapshot`;
  - `GET /api/live/events` → `StreamingResponse` `text/event-stream`, events `alert` and a
    15 s heartbeat comment; auth required (viewer role allowed).
- `frontend/nginx.conf`: `location /api/live/` with `proxy_buffering off`, `proxy_read_timeout 1h`.
- Tests (`tests/test_api.py` style with `make_client` + `MemoryHub`): 401 without token on every
  new route; frame 404 then 200 after `put_frame`; SSE yields a published alert as
  `event: alert` + JSON data; alerts list ordering.

### Task 5 — Camera wall UI (layout A)
- `frontend/src/types.ts`: `Camera`, `CameraStatus`, `Alert`.
- `frontend/src/api.ts`: `streamEvents(token, onEvent, signal)` (fetch + `ReadableStream`
  SSE parser, auto-reconnect with backoff).
- `frontend/src/LiveWall.tsx`: grid of equal tiles (3 columns, 2 on phone), each tile refreshes
  its frame, shows name + frames-analyzed counter; alerting tile gets a red outline; red banner
  under the grid with camera, kind, confidence, time, **View snapshot** and **Dismiss**
  (client-side only — Confirm/False alarm arrive in Milestone 5). Recent alerts list below.
- `frontend/src/App.tsx`: new first tab "Live"; existing tabs untouched. Styles in `style.css`
  using existing tokens.
- `frontend/tests/live.spec.ts`: with the test server (`backend/tests/ui_server.py`, seeded
  camera + `MemoryHub`), the wall shows the camera tile; a published alert makes the banner
  appear without a page reload.

### Task 6 — Docs and verification
- `docs/GUIDE.md` (how to put demo videos in `data/cameras/`, run `seed-site`, start `cameras`),
  `docs/OPERATIONS.md` (CPU budget, analysis rate, Redis keys), `README.md` feature list,
  `docs/VERIFICATION.md` new "Milestone 2" table (what ran, what did not: no Docker, no real
  Redis unless tested, YOLO not run in tests).

## Review focus (failure modes no task test fully covers)

1. Analysis slower than real time for several cameras → frames dropped, latency stays bounded.
2. Browser loses the SSE connection (sleep, proxy timeout) → reconnects and reloads alerts list,
   no missed alert silently.
3. Redis down at API start or mid-stream → API keeps serving the existing features; live routes
   return 503, not 500.
4. Video file missing/corrupt for one camera → that tile shows "offline", others keep running.
5. Many tiles polling frames → bounded request rate (pause polling when the tab is hidden).

## Verification

- `backend/.venv` (Python 3.12): `pytest -q` and `ruff check app tests migrations` all green.
- `frontend`: `npm run build`, `npx playwright test`.
- Manual (if memory allows): put one short MP4 in `data/cameras/hall.mp4`, `python -m app.cli
  seed-site ../examples/site-horizon.json`, run Redis, `python -m app.live`, open the Live tab,
  walk a person into the zone → banner appears. Report honestly in `VERIFICATION.md` what was and
  wasn't run.
- Push, then `gh run watch` for CI.
