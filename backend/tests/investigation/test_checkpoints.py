import os
from uuid import uuid4

import pytest

from app.investigation.checkpoints import checkpoint_url, open_checkpointer
from app.investigation.workflow import build_workflow


def test_checkpoint_url_strips_driver():
    assert checkpoint_url("postgresql+psycopg://u:p@db:5432/w") == "postgresql://u:p@db:5432/w"
    assert checkpoint_url("postgresql://u:p@db/w") == "postgresql://u:p@db/w"
    assert checkpoint_url("sqlite:///./data/w.db") is None


def run_until_review(database_url, data_dir, thread_id):
    config = {"configurable": {"thread_id": thread_id}}
    with open_checkpointer(database_url, data_dir) as saver:
        graph = build_workflow(saver, lambda _: {"summary": "draft"}, lambda *args: None, lambda *args: None)
        graph.invoke({"incident_id": "i", "investigation_id": thread_id}, config)
    with open_checkpointer(database_url, data_dir) as saver:
        graph = build_workflow(saver, lambda _: {"summary": "draft"}, lambda *args: None, lambda *args: None)
        return graph.get_state(config).next


def test_sqlite_checkpointer_persists_between_openings(tmp_path):
    assert run_until_review(f"sqlite:///{tmp_path}/app.db", tmp_path, "inv-1") == ("human_review",)


@pytest.mark.skipif(not os.environ.get("WATCHTOWER_TEST_POSTGRES_URL"), reason="needs PostgreSQL")
def test_postgres_checkpointer_round_trip(tmp_path):
    url = os.environ["WATCHTOWER_TEST_POSTGRES_URL"]
    assert run_until_review(url, tmp_path, f"inv-{uuid4()}") == ("human_review",)
