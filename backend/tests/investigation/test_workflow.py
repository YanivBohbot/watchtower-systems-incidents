import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.investigation.workflow import build_workflow
from app.investigation.schemas import Report, validate_report


def test_report_rejects_invented_citation():
    report = Report(
        summary="Observed presence",
        findings=["Presence"],
        recommendation="Review",
        citation_ids=["invented"],
        limitations=[],
    )
    with pytest.raises(ValueError, match="citation"):
        validate_report(report, {})


def test_graph_persists_pause_and_resumes_without_repeating_agent(tmp_path):
    calls, tickets, saved = [], [], []

    def draft(incident_id):
        calls.append(incident_id)
        return {"summary": "Presence observed", "sources": []}

    def publish(investigation_id, report):
        tickets.append(investigation_id)
        return {"id": "ticket-1"}

    path = str(tmp_path / "graph.db")
    config = {"configurable": {"thread_id": "inv-1"}}
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = build_workflow(SqliteSaver(conn), draft, publish, lambda *args: saved.append(args))
        result = graph.invoke({"incident_id": "incident-1", "investigation_id": "inv-1"}, config)
        assert result["__interrupt__"]
        assert tickets == []
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = build_workflow(SqliteSaver(conn), draft, publish, lambda *args: saved.append(args))
        result = graph.invoke(Command(resume={"approved": True, "create_ticket": True}), config)
        assert result["ticket"]["id"] == "ticket-1"
        assert len(calls) == 1
        assert tickets == ["inv-1"]
        assert saved[-1][1] == "approved"


def test_rejection_does_not_publish(tmp_path):
    tickets = []
    with sqlite3.connect(tmp_path / "graph.db", check_same_thread=False) as conn:
        graph = build_workflow(
            SqliteSaver(conn), lambda _: {"summary": "draft"}, lambda *args: tickets.append(args), lambda *args: None
        )
        config = {"configurable": {"thread_id": "reject"}}
        graph.invoke({"incident_id": "i", "investigation_id": "r"}, config)
        graph.invoke(Command(resume={"approved": False, "create_ticket": False}), config)
    assert tickets == []


def test_failed_publication_retries_finalize_without_redrafting(tmp_path):
    drafts, calls = [], []

    def draft(_):
        drafts.append(1)
        return {"summary": "Presence"}

    def publish(inv_id, report):
        calls.append(inv_id)
        if len(calls) == 1:
            raise ConnectionError("Response lost")
        return {"id": "stable-ticket"}

    with sqlite3.connect(tmp_path / "graph.db", check_same_thread=False) as conn:
        graph = build_workflow(SqliteSaver(conn), draft, publish, lambda *args: None)
        cfg = {"configurable": {"thread_id": "retry"}}
        graph.invoke({"incident_id": "i", "investigation_id": "retry"}, cfg)
        with pytest.raises(ConnectionError):
            graph.invoke(Command(resume={"approved": True, "create_ticket": True}), cfg)
        assert graph.get_state(cfg).next == ("finalize",)
        result = graph.invoke(None, cfg)
    assert result["ticket"]["id"] == "stable-ticket"
    assert len(drafts) == 1
    assert calls == ["retry", "retry"]
