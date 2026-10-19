# WatchTower

Full-stack platform for watching live cameras, analyzing uploaded videos and running
assisted investigations.
English interface, FastAPI, React/TypeScript, YOLO, RAG, LangChain/LangGraph and MCP.

**A working portfolio version, not a certified surveillance platform.**
The source code implements the real integrations; the automated tests replace paid
calls and the detector with deterministic ports. Read
[the verification report](docs/VERIFICATION.md) before mistaking shipped code for integrations that were run.

## Reading and understanding the project

- [Code and architecture guide, file by file](docs/GUIDE.md)
- [Infrastructure, HTTP contracts and operations](docs/OPERATIONS.md)
- [V1 specification](docs/superpowers/specs/2026-10-18-watchtower.md)
- [Live alerting design](docs/superpowers/specs/2026-10-19-live-dangerous-object-alerting-design.md)
- [Checks actually performed and limitations](docs/VERIFICATION.md)

## Getting started with Docker Compose

Prerequisites: Docker with Compose v2, Python 3 to generate the environment file,
a few GB free for the Python/PyTorch image, and Internet access for the images,
the dependencies and the YOLO weights on first launch.

From the project folder:

```bash
python scripts/init_env.py
```

Open `.env` in your editor and set `OPENAI_API_KEY` to your existing key.
Do not publish this file. A ChatGPT subscription does not cover API calls.
The chat model and the embedding model are configurable; choose models your
OpenAI project actually has access to.

```bash
docker compose up --build -d
docker compose exec api python -m app.cli create-user yaniv@example.com --role admin
```

The password is prompted for in the terminal, without echo. Minimum 12 characters.
Open **http://localhost:5173** and sign in. HTTP documentation:
**http://localhost:5173/api/docs**.

The default build uses CPU PyTorch. No GPU is required; speed depends on the
hardware. Videos are limited to 100 MB, 180 seconds and 3840×2160.
The maximum duration of a job is also capped.

## First demo

1. Add `examples/procedure-zone-a.txt` in the **Procedures** tab.
2. Wait for its **Indexed** status. Indexing calls the embeddings API.
3. Film a consenting person with a fixed camera for 30–60 seconds: they walk in,
   stay in a zone for a few seconds, then walk out.
4. Upload the video. Draw the zone and choose a threshold of 2 or 3 seconds.
5. Click **Start analysis**. The first run may download the YOLO weights.
6. From an event, open an investigation. The LLM consults the observations,
   the procedures and, if useful, the MCP ticket tools.
7. Read the report, its references and its limitations. Approve with or without
   a ticket, or reject. The ticket is created by the workflow after approval,
   never directly by the agent.

## Live cameras

A "camera" is a recorded video replayed in a loop at real-time speed. Put your
own short MP4 files (never committed) in the `app-data` volume under `cameras/`,
named as in `examples/site-horizon.json` (a fictional site), then load the site
and restart the camera process:

```bash
docker compose cp hall.mp4 cameras:/data/cameras/hall.mp4
docker compose exec api python -m app.cli seed-site /project/examples/site-horizon.json
docker compose restart cameras
```

The **Live cameras** tab shows every camera on a wall of tiles. When a person
stays in a camera's zone longer than its threshold, the tile turns red and an
alert banner appears without reloading the page. In this milestone, detection is
people only; dangerous objects, VLM verification and the Confirm/False alarm
decision come next (see the design).

A video that does not satisfy the rule can legitimately produce zero events.
The system does not recognize a person's identity or intent.

## Layout

```text
watchtower/
  backend/
    app/
      domain/       contracts, geometry and dwell rule
      adapters/     storage, YOLO, Qdrant and MCP
      services/     video and document pipelines
      agent/        agent, report schema and HITL workflow
      api.py        HTTP interface and permissions
      auth.py       passwords and tokens
      db.py         SQL models and sessions
      runtime.py    adapter wiring
      tasks.py      Celery tasks and SQL outbox
      cli.py        local administration
    migrations/     Alembic history
    tests/          business, API, video, RAG, agent and MCP tests
  frontend/
    src/            React components, HTTP client and styles
    tests/          Playwright browser scenario
  mcp_server/       MCP ticket server over stdio
  skills/           versioned agent instructions
  examples/         fictitious demo procedure
  scripts/          local environment file generation
  docs/             detailed explanation and report
  compose.yaml      services, networks and volumes
```

## Tests without an API key

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e '.[dev]'
pytest
ruff check app tests migrations
```

The `vision` extra is required to run YOLO outside Docker:
`pip install -e '.[vision]'`. Install CPU PyTorch explicitly before this extra
if you want to avoid the CUDA dependencies.

```bash
cd frontend
npm ci
npm run build
npx playwright install chromium
```

The browser scenario starts its own test API: no OpenAI, no Celery, and no
supposedly real vision results. To run it, set `WATCHTOWER_PYTHON` to the backend
environment's Python if `python` is not already that interpreter, then run
`npx playwright test`.

## Known limitations

- A single shared workspace: roles apply to the whole organization.
- Live cameras are looped video files, not RTSP hardware. Detection runs on CPU at
  about 5 analyzed frames per second per camera; tiles show near-live snapshots
  (two per second), not video streaming. Live detection is people only.
- Person detection with YOLO COCO and ByteTrack; IDs can be lost during
  occlusion. A new track can generate a new event.
- Text PDF/TXT documents; no OCR. Documents are immutable and deduplicated by
  content. Replacing or deleting versions is not implemented.
- Local storage shared through volumes. The `Storage` port prepares an S3
  replacement, but the S3 adapter is not included in this V1.
- The LLM receives structured observations and links to the evidence, not the
  pixels of the capture. Multimodal analysis with a VLM is a separate extension.
- Live alerts are pushed with Server-Sent Events; the other lists still refresh by
  polling.
- No SSO, multi-tenancy, public TLS, autoscaling or external monitoring configured.

The documentation explains possible extensions; it does not present them as
already built.
