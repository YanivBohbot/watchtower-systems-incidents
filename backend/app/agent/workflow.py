"""Persistent deterministic envelope around one tool-using investigation agent."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class State(TypedDict, total=False):
    incident_id: str
    investigation_id: str
    report: dict
    decision: dict
    ticket: dict | None


def build_workflow(checkpointer, draft_report, publish_ticket, save):
    def draft(state):
        report = draft_report(state["incident_id"])
        save(state["investigation_id"], "awaiting_review", report, None)
        return {"report": report}

    def review(state):
        decision = interrupt({"report": state["report"], "action": "approve_or_reject"})
        if not isinstance(decision, dict) or type(decision.get("approved")) is not bool:
            raise ValueError("Invalid review decision")
        if decision.get("create_ticket") and not decision["approved"]:
            raise ValueError("Rejected reports cannot create tickets")
        return {"decision": decision}

    def finalize(state):
        decision = state["decision"]
        ticket = None
        if decision["approved"] and decision.get("create_ticket"):
            ticket = publish_ticket(state["investigation_id"], state["report"])
        save(state["investigation_id"], "approved" if decision["approved"] else "rejected", state["report"], ticket)
        return {"ticket": ticket}

    graph = StateGraph(State)
    graph.add_node("investigate", draft)
    graph.add_node("human_review", review)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "investigate")
    graph.add_edge("investigate", "human_review")
    graph.add_edge("human_review", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
