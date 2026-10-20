"""Structured report the agent must return, and the check that its citations were retrieved."""

from pydantic import BaseModel, Field


class Report(BaseModel):
    summary: str = Field(max_length=2500)
    findings: list[str] = Field(max_length=12)
    recommendation: str = Field(max_length=2500)
    citation_ids: list[str] = Field(max_length=15)
    limitations: list[str] = Field(max_length=10)


def validate_report(report: Report, retrieved: dict[str, dict]) -> dict:
    missing = set(report.citation_ids) - retrieved.keys()
    if missing:
        raise ValueError("Report contains a citation not retrieved during this investigation")
    result = report.model_dump()
    result["sources"] = [retrieved[key] for key in dict.fromkeys(report.citation_ids)]
    if not report.citation_ids:
        result["limitations"].append("No documented procedure cited; human review required.")
    return result
