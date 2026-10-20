"""What each job kind runs. The worker composition root: concrete adapters are wired here."""

import asyncio
import json

from langchain_openai import OpenAIEmbeddings
from langgraph.types import Command

from app.core.config import settings
from app.database.models import Investigation
from app.database.session import make_sessions
from app.integrations.local_storage import LocalStorage
from app.integrations.mcp_tickets import McpTickets
from app.integrations.qdrant_index import QdrantIndex
from app.integrations.yolo_detector import YoloDetector
from app.investigation.checkpoints import open_checkpointer
from app.investigation.investigator import Investigator
from app.investigation.workflow import build_workflow
from app.services.knowledge_base import KnowledgeService
from app.services.video_analysis import VideoService


def knowledge_service(cfg, sessions):
    if not cfg.openai_api_key.get_secret_value():
        raise ValueError("Configure OPENAI_API_KEY in your local .env")
    return KnowledgeService(
        sessions,
        LocalStorage(cfg.data_dir / "files"),
        OpenAIEmbeddings(
            model=cfg.embedding_model, api_key=cfg.openai_api_key.get_secret_value(), request_timeout=60, max_retries=1
        ),
        QdrantIndex(cfg.qdrant_url, cfg.qdrant_collection),
    )


def execute(kind, resource_id, progress):
    cfg = settings()
    engine, sessions = make_sessions(cfg.database_url)
    try:
        if kind == "video":
            VideoService(
                sessions,
                LocalStorage(cfg.data_dir / "files"),
                lambda: YoloDetector(cfg.yolo_model),
                cfg.max_video_seconds,
                cfg.max_video_pixels,
            ).analyze(resource_id, progress)
        elif kind == "document":
            knowledge_service(cfg, sessions).ingest(resource_id)
        elif kind in ("investigate", "review"):
            tickets = McpTickets(cfg.mcp_server_path, cfg.data_dir / "tickets.db")
            investigator = Investigator(sessions, knowledge_service(cfg, sessions), tickets, cfg)

            def save(inv_id, status, report, ticket):
                with sessions() as db:
                    inv = db.get(Investigation, inv_id)
                    inv.status, inv.report, inv.ticket = status, report, ticket
                    db.commit()

            with open_checkpointer(cfg.database_url, cfg.data_dir) as saver:
                graph = build_workflow(
                    saver,
                    lambda incident_id: asyncio.run(investigator.run(incident_id)),
                    lambda inv_id, report: asyncio.run(tickets.publish(inv_id, report)),
                    save,
                )
                config = {"configurable": {"thread_id": resource_id}}
                snapshot = graph.get_state(config)
                with sessions() as db:
                    inv = db.get(Investigation, resource_id)
                    incident_id, decision = inv.incident_id, inv.decision
                if snapshot.values and not snapshot.next:
                    return  # A completed graph must not be started again on redelivery.
                if kind == "review":
                    if not snapshot.values:
                        raise ValueError("Missing investigation checkpoint")
                    if snapshot.next == ("human_review",):
                        graph.invoke(Command(resume=json.loads(decision)), config)
                    else:
                        graph.invoke(None, config)  # Retry failed finalize; decision is already checkpointed.
                else:
                    graph.invoke(
                        None if snapshot.values else {"incident_id": incident_id, "investigation_id": resource_id},
                        config,
                    )
        else:
            raise ValueError("Unknown job kind")
    finally:
        engine.dispose()
