import asyncio
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.core.config import Settings
from app.database.models import Base, Incident, Video
from app.database.session import make_sessions
from app.investigation.investigator import Investigator


class ScriptedModel(BaseChatModel):
    """Only the provider is replaced: the actual LangChain tool loop runs."""

    @property
    def _llm_type(self):
        return "scripted-test-provider"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        observed = any(isinstance(m, ToolMessage) and m.name == "get_evidence" for m in messages)
        name = "Report" if observed else "get_evidence"
        args = (
            {
                "summary": "Presence observed",
                "findings": ["Trajectoire en zone A"],
                "recommendation": "Check the video",
                "citation_ids": ["source-1"],
                "limitations": ["Simulation de test"],
            }
            if observed
            else {}
        )
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[{"id": "call-report" if observed else "call-evidence", "name": name, "args": args}],
                    )
                )
            ]
        )


class Knowledge:
    def search(self, query):
        return [{"id": "source-1", "document": "procedure.txt", "page": 1, "text": "Check the video."}]


class Tickets:
    async def read_tools(self):
        return []


def test_actual_langchain_agent_calls_tool_and_returns_validated_report(tmp_path):
    engine, sessions = make_sessions(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add(Video(id="v", name="v.mp4", storage_key="v.mp4", zone={}))
        db.commit()
        db.add(Incident(id="i", video_id="v", track_id=1, seconds=5, evidence_key="e.jpg", details={}))
        db.commit()
    cfg = Settings(jwt_secret="x" * 40, skill_path=Path(__file__).resolve().parents[3] / "skills/investigate/SKILL.md")
    agent = Investigator(sessions, Knowledge(), Tickets(), cfg, model_factory=lambda _: ScriptedModel())
    report = asyncio.run(agent.run("i"))
    assert "get_evidence" in report["tool_trace"]
    assert report["sources"][0]["id"] == "source-1"
    assert report["evidence"]["incident_id"] == "i"
