"""Tests for signal extraction, findings serialization, and Q&A citations."""

from __future__ import annotations

import csv
import io
import json

from polistress.report import ReportAgent, derive_signals
from polistress.report.findings import Finding, findings_to_csv, findings_to_json
from polistress.simulation import EventLog
from polistress.worldgraph import WorldGraph


def _seed_log(tmp_path) -> EventLog:
    log = EventLog(tmp_path / "e.db")
    log.append(tick=0, agent_id="system", action="policy_injection", rationale="AI policy")
    log.append(tick=1, agent_id="agent:person:dev", action="workaround", rationale="used unapproved AI tool", target="control:mfa")
    log.append(tick=2, agent_id="agent:ai:001", action="ignore", rationale="kept using copilot", target="asset:repo")
    log.append(tick=3, agent_id="agent:attacker:0", action="exploit_attempt", rationale="probed control", target="control:mfa")
    return log


def test_derive_signals_are_grounded(small_graph: WorldGraph, tmp_path) -> None:
    log = _seed_log(tmp_path)
    signals = derive_signals(log, small_graph)
    assert signals
    # shadow-AI signal present and cites real event ids
    shadow = [s for s in signals if s.kind == "shadow_ai"]
    assert shadow
    assert all(isinstance(i, int) for i in shadow[0].event_ids)
    log.close()


def test_findings_json_and_csv_shape() -> None:
    f = Finding(
        id="POLI-001",
        title="Shadow AI",
        description="Copilots kept running",
        severity="high",
        affected_assets=["asset:repo"],
        root_cause_events=[2, 3],
        domain="ai_governance",
        framework_mappings={
            "NIST CSF": ["GV.PO-01"],
            "ISO 27001": ["A.5.1"],
            "NIST AI RMF": ["GOVERN-1.1"],
        },
        remediation_plan=["Review copilots", "Communicate policy"],
        predicted_residual_risk="medium",
    )
    data = json.loads(findings_to_json([f]))
    assert data[0]["id"] == "POLI-001"
    assert data[0]["root_cause_events"] == [2, 3]
    assert set(data[0]["framework_mappings"]) == {"NIST CSF", "ISO 27001", "NIST AI RMF"}

    rows = list(csv.DictReader(io.StringIO(findings_to_csv([f]))))
    assert rows[0]["id"] == "POLI-001"
    assert rows[0]["nist_ai_rmf"] == "GOVERN-1.1"
    assert rows[0]["root_cause_events"] == "2; 3"


def test_finding_severity_normalized() -> None:
    assert Finding(id="x", title="t", description="d", severity="SEVERE").severity == "medium"


class FakeBackend:
    """Backend returning canned JSON / answers — no LLM calls in tests."""

    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return self.reply


async def test_build_findings_filters_invalid_event_ids(small_graph: WorldGraph, tmp_path) -> None:
    log = _seed_log(tmp_path)
    # model cites one real event (2) and one bogus event (9999)
    reply = json.dumps(
        [
            {
                "id": "POLI-001",
                "title": "Shadow AI emergence",
                "description": "d",
                "severity": "high",
                "affected_assets": ["asset:repo"],
                "root_cause_events": [2, 9999],
                "domain": "ai_governance",
                "framework_mappings": {"NIST AI RMF": ["GOVERN-1.1"]},
                "remediation_plan": ["review"],
                "predicted_residual_risk": "medium",
            }
        ]
    )
    agent = ReportAgent(small_graph, log, FakeBackend(reply))
    findings = await agent.build_findings()
    assert len(findings) == 1
    assert findings[0].root_cause_events == [2]  # 9999 filtered out
    log.close()


async def test_build_findings_fallback_when_unparseable(small_graph: WorldGraph, tmp_path) -> None:
    log = _seed_log(tmp_path)
    agent = ReportAgent(small_graph, log, FakeBackend("not json at all"))
    findings = await agent.build_findings()
    assert findings  # deterministic fallback still produces grounded findings
    assert all(f.root_cause_events for f in findings)
    log.close()


async def test_answer_cites_event_ids(small_graph: WorldGraph, tmp_path) -> None:
    log = _seed_log(tmp_path)
    agent = ReportAgent(small_graph, log, FakeBackend("Shadow AI emerged in dev [evt-2]."))
    ans = await agent.answer("where did shadow AI emerge?")
    assert ans.cited_event_ids == [2]
    log.close()
