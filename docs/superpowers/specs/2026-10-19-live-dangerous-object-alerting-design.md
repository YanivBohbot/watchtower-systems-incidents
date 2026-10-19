# WatchTower Live — dangerous-object alerting (design)

Status: draft for review — 2026-10-19

## Intent

Evolve WatchTower from "upload a video, analyze it later, investigate" into a
**live surveillance and alerting system**: camera feeds are watched continuously,
and when a person shows a **firearm, a knife or another dangerous object**, a
security operator gets a **live alert within seconds**, with the evidence, an
explanation and the site's procedure, and decides what happens next.

### Why

This is a **portfolio project** for learning and job interviews. It must show,
in a working demo, that the author knows how to:

- pick the right component for each job: a fast detector (YOLO) as a continuous
  filter, a VLM to verify and understand, an LLM agent to reason, RAG for context;
- architect an agentic system (LangChain agent inside a LangGraph workflow) that
  detects, verifies and alerts, with a human in the loop;
- use multimodal RAG for a concrete purpose, not as decoration.

Being able to **justify every choice** (cost, latency, reliability, privacy) matters
as much as the features.

### Who it serves

A **security operator** watching a site's cameras. They receive alerts live,
look at the evidence, confirm or reject, and follow the site's procedure.

## Goals

1. **Live feeds.** Process several "cameras" continuously. For the demo, a camera
   is a recorded video replayed at real-time speed (in a loop), indistinguishable
   from a live feed for the rest of the system.
2. **Detection.** Detect people and dangerous objects (firearm, knife, other
   dangerous objects) on every analyzed frame.
3. **Verification cascade.** An alert candidate must persist over several
   consecutive frames, then a **VLM** (Qwen-VL via Hugging Face Inference
   Providers) looks at the relevant frames and confirms or rejects.
4. **Immediate alert.** As soon as the VLM confirms, the alert reaches the operator.
   The alert never waits for the agent's analysis.
5. **Operator screen (layout "A", camera wall, chosen by the user).** All cameras
   stay visible in a grid of equal tiles. The alerting camera's tile gets a red
   outline with the detection box drawn; a red alert banner under the grid shows
   the camera, object, score, VLM description and time, with **View clip**,
   **Confirm** and **False alarm** buttons.
6. **Agent context.** In parallel with the alert, a LangChain agent retrieves the
   site's procedure (text RAG) and similar past alerts (multimodal RAG) and fills
   an expandable details area of the alert banner (designer's call: layout A has
   no side panel, so the context lives in the banner).
7. **Human decision.** The operator confirms or rejects. Nothing external happens
   without that decision. On confirmation, the procedure's follow-up runs (for
   example, a ticket through the existing MCP ticket server).
8. **Site-dependent "normal".** Whether an object is allowed depends on the site
   and camera (a knife is normal in the cafeteria kitchen, not in the hall). These
   rules live in the site's procedures and are retrieved by RAG.
9. **Multimodal RAG — three uses (agreed with the user):**
   - **Procedures** of each site (text, possibly with images such as a floor plan).
   - **Alert memory:** every alert keeps an image crop of the object, the VLM
     description and the operator's decision. New alerts retrieve visually similar
     past cases and show them to the VLM, so the system makes fewer false alarms
     over time **without retraining**. Seeded at start with public images of real
     weapons (true alerts) and classic look-alikes such as phones, umbrellas and
     drills (false alerts).
   - **History search:** "show all knife alerts this week", "alerts similar to
     this one", from the same index.
10. **Measured results.** Report alert latency, VLM calls per hour of video, and
    outcomes on a small set of labeled test clips.

## The demo (agreed with the user)

1. **Calm:** the hall camera runs, people pass, nothing happens. A counter shows
   thousands of frames analyzed and zero VLM calls.
2. **Real alert:** someone draws a fake gun; the box appears within about a second,
   the VLM confirms, screen C lights up with the procedure.
3. **The trap:** someone holds a phone the same way; the cascade (VLM + alert
   memory) concludes "phone", no alert.
4. **Context:** the same knife in the kitchen camera does not alert, because the
   site's procedure allows it.
5. **Human and learning:** the operator rejects a false alarm; the next similar
   case is judged better.
6. **Architecture and numbers:** a diagram and the measured results.

## Non-goals (this version)

- Abnormal **behaviors** (running, fighting, falling). Dangerous objects only.
- Real IP cameras / RTSP hardware. The design must not prevent them later.
- Multi-tenant, SSO, public deployment, autoscaling.
- Answering free-form questions about videos ("ask your videos").

## Anti-goals (a failure even if it technically works)

- The system **acts on its own**: calls emergency services, locks doors, or
  creates a ticket without an operator's decision.
- **Identifying people**: face recognition, re-identification across days
  ("this person came yesterday"), or storing faces in the alert memory. Memory
  crops are cut around the **object**, not the person.
- The alert **waits for the agent** (LLM reasoning) before reaching the operator.
- Sending every frame to a cloud model.
- Presenting unverified integrations or unmeasured accuracy as tested
  (see `docs/VERIFICATION.md` conventions).

## Constraints

- **Hardware:** development laptop, Intel Core i7-10510U, no NVIDIA GPU, low
  free RAM. Live detection runs on CPU at a reduced analysis rate (target 5–10
  analyzed frames per second per camera). Any model training happens on a free
  cloud GPU (Colab or Kaggle).
- **VLM:** Qwen-VL through Hugging Face Inference Providers (the user is creating
  an HF token). This requires purchased credits on a free HF account and accepts
  **images, not video files**: frames are extracted and sent as images. Provider
  availability for the chosen Qwen-VL model must be checked before relying on it.
- **Existing stack is kept:** OpenAI for the agent LLM and text embeddings,
  Qdrant for vectors (chosen over Pinecone so data can stay on site, and over
  Chroma for filtering and named vectors), PostgreSQL, Celery/Redis, FastAPI,
  React, LangChain, LangGraph, the MCP ticket server, Docker Compose.
- **Repository conventions** (`AGENTS.md`): all project content in English;
  deterministic test doubles for paid APIs and vision; no secrets, videos or
  generated evidence in git; human approval preserved.
- **Data:** no real data exists. Procedures are written for a **fictional site**
  (for example "Horizon Cultural Center": hall, reception, corridor, parking,
  cafeteria kitchen) and labeled as fictional. Demo videos are filmed by the user
  with consenting people and **clearly fake props**, never in a public place;
  normal-scene footage may come from free-license sources after checking each
  license. Seed images come from public datasets whose license allows this use.
- **Licenses:** Ultralytics YOLO is AGPL-3.0 — acceptable for a portfolio, to be
  noted in the README.

## Decisions made with the user

- Evolve WatchTower rather than start a new project.
- Operator screen layout A (camera wall; replaces the earlier choice of layout C).
- First-version triggers: firearm, knife, other dangerous objects.
- Qdrant stays.
- Multimodal RAG = procedures + alert memory + history search; no person
  identification.
- The demo scenario above.
- VLM: Qwen-VL via Hugging Face.

## Calls made by the designer (the user can overturn them)

- **Camera simulation:** a per-camera worker reads a video file at its native
  pace in a loop and feeds the same pipeline a real stream would.
- **Detector:** YOLO fine-tuned on a public weapon dataset (firearm, knife) on a
  cloud GPU; "other dangerous objects" covered by an open-vocabulary detector
  (YOLO-World or similar) and/or the VLM, evaluated before committing.
- **Live updates to the UI:** a push channel (WebSocket or Server-Sent Events)
  replaces polling for alerts.
- **Alert workflow (LangGraph):** notify immediately → agent gathers context in
  parallel → `interrupt()` for the operator's decision → follow-up actions. Uses
  the existing pattern of `agent/workflow.py`.
- **Image embeddings:** a small open model (CLIP or SigLIP family) running on CPU,
  stored as a named vector next to the text embedding of the VLM description in
  the same Qdrant point.
- **Consolidate first:** fix jobs stuck in `running`, move LangGraph checkpoints
  to PostgreSQL, stream video responses — before adding live features.
- **Existing features stay:** video upload, the dwell rule and investigations
  keep working; the dwell rule becomes one rule type among others.
- **Provider swap:** the VLM sits behind a port (`VisionLanguageModel`) so Gemini
  or OpenAI can replace Qwen through configuration.
- **"Other dangerous objects"** is a configurable list. Initial list: axe or
  hatchet, baseball bat, crowbar. Firearm and knife are the two classes the demo
  must handle well; the others are best-effort.
- **VLM unavailable** (no credits, provider down, timeout): the system does not
  stay silent. A persistent detection still reaches the operator, clearly marked
  **"unverified"**, so a provider outage never hides a real threat.
- **Sites and cameras** are defined in a seed file loaded into the database
  (site, camera name, video source, zone labels such as "kitchen"). No admin UI
  for them in this version.
- **Notifications** stay on the operator screen (with a sound once the operator
  has interacted with the page). SMS, e-mail and mobile push are out of scope.
- **Uploaded videos** go through the same detection rules as live cameras, so
  the existing upload path benefits from the new detector.

## Suggested milestones (each one demoable)

1. Consolidation (stuck jobs, Postgres checkpointer, video streaming).
2. Live cameras from looped videos + push alerts to the UI (people only).
3. Dangerous-object detector + persistence rule.
4. VLM verification behind the `VisionLanguageModel` port.
5. Alert workflow with screen C and operator decision.
6. Fictional site procedures + site-dependent rules via RAG.
7. Alert memory (multimodal RAG) + seeding + history search.
8. Test clips, measurements, README and architecture diagram.

## Left to the builder

Exact libraries and versions, database schema, thresholds (confidence, number of
frames), analysis rate, crop sizes, UI details beyond layout A, the choice
between WebSocket and SSE, Qwen-VL model size and provider, the weapon dataset,
and how test clips are labeled.

## Open risks

- CPU-only detection may be too slow for several cameras at once; the demo may
  run one or two cameras.
- The public weapon datasets may be noisy or under restrictive licenses.
- Hugging Face provider availability and latency for Qwen-VL are unverified.
- VLM latency (seconds) bounds how fast an alert can be confirmed.
