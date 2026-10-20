# Repository Guidelines

## Project Structure & Architecture

WatchTower analyzes uploaded videos and live cameras and supports human-reviewed incident investigations. `backend/app/` is split by responsibility: `core/` (settings, security), `database/` (tables, sessions), `domain/` (pure rules and interfaces), `api/` (app factory, dependencies, one router per domain in `api/routes/`), `services/` (use cases), `investigation/` (LangGraph workflow and agent), `integrations/` (external adapters) and `workers/` (Celery job queue, job handlers, camera process). `docs/GUIDE.md` explains each file. Database migrations live in `backend/migrations/`; backend tests in `backend/tests/` mirror the `app/` folders. The React/TypeScript frontend is in `frontend/src/` (`api/`, `pages/`, `components/`, `styles/`), with Playwright tests in `frontend/tests/`. `mcp_server/` implements the ticket server; `skills/`, `examples/`, `scripts/`, and `docs/` hold agent instructions, sample procedures and sites, utilities, and project documentation. New modules go in the folder that matches their role, and `backend/tests/test_layout.py` lists the documented modules.

## Build, Test & Development Commands

- `python scripts/init_env.py`: create local environment configuration; add the API key to `.env`.
- `docker compose up --build -d`: build and start the full stack at `http://localhost:5173`.
- From `backend/`, install `requirements.lock` and `pip install -e '.[dev]'`, then run `pytest` and `ruff check app tests migrations`.
- From `frontend/`, run `npm ci`, `npm run dev` for Vite, or `npm run build` for TypeScript checking and production assets.
- Run `npx playwright install chromium` and `npx playwright test` from `frontend/` for browser tests. Set `WATCHTOWER_PYTHON` to the backend environment's Python when necessary.

## Coding Style & Testing

Use four-space indentation and snake_case for Python modules and functions; use PascalCase for React components and TypeScript types. Follow existing code patterns. Ruff checks Python with a 120-character line limit. Name backend tests `test_*.py` and browser tests `*.spec.ts`; place tests alongside the existing suite for the affected component. Prefer deterministic doubles for paid APIs and vision dependencies. No coverage threshold is configured.

## Security & Changes

Never commit `.env`, credentials, private videos, or generated evidence. Preserve the human approval step before ticket creation and avoid describing unverified integrations as tested. See `docs/VERIFICATION.md` for current verification limits. For pull requests, describe behavior changes, tests run, relevant issues, and screenshots for UI changes. Git history was unavailable when this guide was created; use concise, imperative commit subjects.

## Documentation for Agents

For library, API, or CLI questions, fetch current documentation with `npx ctx7@latest library <name> "<question>"`, then `npx ctx7@latest docs <libraryId> "<question>"`. Run Context7 requests outside the default sandbox and never include secrets in queries. Do not use Context7 for general refactoring or business-logic debugging.
