# Codebase restructure — design

Date: 2026-10-20. Status: draft for approval.

## Intent

Before milestone 3, make WatchTower readable for someone opening it for the first time (a recruiter,
a backend engineer, the owner in six months). The backend should look like it was designed by an
experienced backend engineer: folders by responsibility, file and folder names that say what they
contain, and code that matches the documentation.

Today `backend/app/` has 11 loose files at its root, a 363-line `api.py` holding every route inside
one `create_app` function, three different files named `live.py`, and vague names (`runtime.py`,
`tasks.py`, `db.py`, `text.py`). The frontend has seven loose files in `src/`.

## Goals

- A folder layout where each folder has one clear role and each file name describes its content.
- Routes split by domain; request/response schemas, database models, business rules, services,
  external integrations and background processes each in their own place.
- Documentation (`docs/GUIDE.md`, `docs/OPERATIONS.md`, `README.md`, `AGENTS.md`, `docs/VERIFICATION.md`
  where it names files or commands) describes the new layout exactly.
- An independent code review of the finished refactor, with its findings fixed before it is called done.

## Non-goals

- No new features and nothing from milestone 3.
- No behaviour change: same HTTP routes, payloads, status codes, database schema, migrations
  history, environment variables, Celery queues and UI behaviour.
- `mcp_server/` stays as is (a single file; folders would add nothing). Builder's call to leave it.
- No rewrite of algorithms or library swaps.

## Anti-goals (a failure even if tests pass)

- A layout with names that still need explaining, or folders holding a single trivial file for the
  sake of symmetry.
- Docs that describe paths or commands that no longer exist.
- Behaviour silently changed while "just moving code".

## Constraints

- All existing tests must pass before and after: 52 backend (`pytest`, 2 skipped without Redis/PostgreSQL),
  `ruff check app tests migrations`, `npm run build`, 3 Playwright tests.
- Project content stays in English; follow `AGENTS.md` style (Ruff, 120 columns, snake_case / PascalCase).
- Module paths are referenced outside Python: `backend/Dockerfile` (`app.main:app`), `compose.yaml`
  (`app.tasks:celery`, `python -m app.live`), `docs/OPERATIONS.md`, `README.md`, `backend/tests/ui_server.py`,
  Alembic `migrations/env.py` (model metadata import). All must be updated.
- Celery tasks already have explicit names (`watchtower.run`, `watchtower.sweep`); keep them unchanged so
  queued messages and beat schedules keep working.
- `domain/` means "no infrastructure": pydantic is allowed there. `Zone` stays a pydantic model and moves
  as is, so upload validation (accepted inputs, 422 cases) cannot drift. (Builder's call.)
- `docs/VERIFICATION.md` is a log: past rows keep the commands that were actually run. Add a short
  old-path → new-path table and a new entry for this refactor's own verification. Only the "how to run"
  instructions elsewhere are rewritten to new paths. (Builder's call.)
- Historical plans and specs under `docs/superpowers/` are records; do not rewrite them.

## Decided: backend layout

```
backend/app/
├── main.py                 # builds the FastAPI app and mounts the routers
├── cli.py                  # admin commands: create-user, seed-site, recover-job
├── core/
│   ├── config.py
│   └── security.py         # password hashing, JWT        (was auth.py)
├── api/
│   ├── dependencies.py     # current user, role checks, DB session, shared services
│   ├── schemas/            # request/response models (Login, Review, ...)
│   └── routes/             # one router per domain        (was api.py)
│       ├── health.py auth.py videos.py jobs.py documents.py incidents.py
│       └── investigations.py cameras.py alerts.py live_events.py
├── database/
│   ├── session.py          # engine / session factory
│   └── models.py           # ORM tables                   (was db.py)
├── domain/                 # pure rules, no external dependency
│   ├── dwell_rule.py       # Zone, Observation, DwellRule (was rules.py)
│   ├── text_chunking.py    #                              (was text.py)
│   └── interfaces.py       # Protocols for integrations   (was ports.py)
├── services/
│   ├── video_analysis.py   # (was services/video.py)
│   ├── knowledge_base.py   # (was services/knowledge.py)
│   ├── camera_monitor.py   # CameraRunner                 (was services/live.py)
│   ├── frame_annotation.py # (was services/annotate.py)
│   └── site_seeding.py     # (was services/sites.py)
├── investigation/          # LangGraph agent              (was agent/)
│   └── investigator.py workflow.py schemas.py checkpoints.py
├── integrations/           # external systems             (was adapters/)
│   ├── yolo_detector.py qdrant_index.py local_storage.py mcp_tickets.py
│   ├── looped_video_source.py
│   └── live_hub.py         # Redis hub + in-memory hub    (was adapters/live.py)
└── workers/
    ├── job_queue.py        # Celery app, run_job, sweep    (was tasks.py)
    ├── job_handlers.py     # what each job kind executes   (was runtime.py)
    └── camera_process.py   # live camera process entry     (was app/live.py)
```

Tests mirror this layout (`tests/api/`, `tests/services/`, `tests/integrations/`, ...). Names in this tree
are the target; the builder may adjust a name when the file's real content makes another name clearer,
and must record each such change in the plan.

## Decided: frontend layout

```
frontend/src/
├── main.tsx
├── App.tsx                 # login gate + tab navigation only
├── api/
│   ├── client.ts           # HTTP calls                   (was api.ts)
│   └── types.ts            # response types               (was types.ts)
├── pages/                  # one file per tab
│   └── LoginPage VideosPage ProceduresPage InvestigationsPage LiveCamerasPage (was LiveWall)
├── components/             # reusable pieces: ZoneEditor and whatever App.tsx splits out
└── styles/global.css       # (was style.css)
```

The exact page split follows the tabs that actually exist in `App.tsx`; the builder decides it after reading
the file. Playwright selectors must keep working without weakening the tests.

## Code readability inside files

Beyond moving files: clear names for unclear functions and variables, short docstrings on modules and on
non-obvious functions, consistent with the surrounding comment density. Dead code found during the move is
removed. Each such change stays behaviour-neutral.

## Process

1. Restructure in small, separately committed steps on a branch, running the full test suite at each step.
2. Update Docker, Compose, CI, test helpers and docs to the new paths.
3. Independent code review of the whole diff by a separate reviewer agent (the owner asked for a review
   after this much code); fix findings with tests where a bug is involved.
4. Final verification: backend tests, ruff, frontend build, Playwright, and a quick start of the API to
   check it boots. Report anything not run.
5. End state: a reviewed, verified branch. Merging into `main` (or opening a PR) waits for the owner's
   go-ahead, as for milestone 2. (Builder's call.)

## Left to the builder

- Order of the steps, and whether a step moves several folders at once.
- Small helpers' placement (`uid()`, `now()`, `public()` serializer) as long as the rule "one clear role per
  folder" holds.
- How `create_app` wires dependencies (FastAPI `Depends`, app state), provided test doubles can still be
  injected as they are today.
