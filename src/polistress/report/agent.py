"""The report agent: findings-register synthesis and grounded Q&A."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..simulation.eventlog import Event, EventLog
from ..worldgraph import WorldGraph
from ..worldgraph.types import NodeType
from .backend import ReportBackend
from .findings import Finding
from .signals import Signal, derive_signals

_FINDINGS_SYSTEM = (
    "You are a GRC analyst writing a findings register from a policy-simulation "
    "run. You are given grounded signals, each with real event ids as evidence. "
    "Produce findings ONLY from the evidence provided. Map each finding to "
    "control ids in NIST CSF, ISO 27001, and NIST AI RMF. Cite the given event "
    "ids in root_cause_events — never invent event ids. Respond with ONLY a JSON "
    "array; each element must have keys: id, title, description, severity "
    "(critical|high|medium|low|informational), affected_assets (array), "
    "root_cause_events (array of integers), domain, framework_mappings (object "
    "with keys 'NIST CSF', 'ISO 27001', 'NIST AI RMF' mapping to arrays of "
    "control-id strings), remediation_plan (array of steps), "
    "predicted_residual_risk (critical|high|medium|low)."
)

_QA_SYSTEM = (
    "You answer questions about a GRC policy-simulation run using ONLY the "
    "provided events. Every claim must cite the specific event ids it rests on, "
    "written inline as [evt-<id>]. If the events do not support an answer, say "
    "so. Be concise."
)


@dataclass
class Answer:
    """An answer to a Q&A question with the event ids it cites."""

    question: str
    text: str
    cited_event_ids: list[int] = field(default_factory=list)


class ReportAgent:
    """Reads the event log + graph and produces findings and answers."""

    def __init__(
        self,
        graph: WorldGraph,
        log: EventLog,
        backend: ReportBackend,
        domain: str = "ai_governance",
    ) -> None:
        self.graph = graph
        self.log = log
        self.backend = backend
        self.domain = domain
        self._asset_ids = set(graph.nodes_of_type(NodeType.ASSET))

    # -- findings ---------------------------------------------------------

    async def build_findings(self) -> list[Finding]:
        signals = derive_signals(self.log, self.graph)
        if not signals:
            return []
        valid_event_ids = {e.event_id for e in self.log.all()}
        user = self._findings_prompt(signals)
        raw = await self.backend.complete(_FINDINGS_SYSTEM, user, max_tokens=3000)
        findings = self._parse_findings(raw, valid_event_ids)
        if not findings:
            findings = self._deterministic_findings(signals)
        return findings

    def _findings_prompt(self, signals: list[Signal]) -> str:
        lines = ["Signals (evidence):"]
        for s in signals[:12]:
            ids = ", ".join(str(i) for i in s.event_ids[:25])
            targets = ", ".join(s.affected_targets[:10]) or "(none)"
            lines.append(
                f"- kind={s.kind} action={s.action} count={s.count} "
                f"targets=[{targets}] event_ids=[{ids}]"
            )
        lines.append(
            "\nWrite 3 to 6 findings as a JSON array. Cite only the event ids "
            "listed above in root_cause_events."
        )
        return "\n".join(lines)

    def _parse_findings(
        self, raw: str, valid_event_ids: set[int]
    ) -> list[Finding]:
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1 or end < start:
            return []
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        findings: list[Finding] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            root = [
                int(e)
                for e in item.get("root_cause_events", [])
                if _as_int(e) in valid_event_ids
            ]
            findings.append(
                Finding(
                    id=str(item.get("id") or f"POLI-{i + 1:03d}"),
                    title=str(item.get("title", "Untitled finding")),
                    description=str(item.get("description", "")),
                    severity=str(item.get("severity", "medium")),
                    affected_assets=[str(a) for a in item.get("affected_assets", [])],
                    root_cause_events=root,
                    domain=str(item.get("domain", self.domain)),
                    framework_mappings=_clean_mappings(item.get("framework_mappings", {})),
                    remediation_plan=[str(r) for r in item.get("remediation_plan", [])],
                    predicted_residual_risk=str(
                        item.get("predicted_residual_risk", "medium")
                    ),
                )
            )
        return findings

    def _deterministic_findings(self, signals: list[Signal]) -> list[Finding]:
        """Fallback: build findings directly from grounded signals (no LLM prose)."""
        findings: list[Finding] = []
        for i, s in enumerate(signals[:6]):
            assets = [t for t in s.affected_targets if t in self._asset_ids]
            findings.append(
                Finding(
                    id=f"POLI-{i + 1:03d}",
                    title=f"Policy stress: {s.kind.replace('_', ' ')}",
                    description=s.description,
                    severity="high" if s.kind in ("exploit_attempt_cluster", "shadow_ai") else "medium",
                    affected_assets=assets or s.affected_targets[:5],
                    root_cause_events=s.event_ids[:25],
                    domain=self.domain,
                    framework_mappings={
                        "NIST CSF": ["GV.PO-01", "PR.AA-05"],
                        "ISO 27001": ["A.5.1", "A.8.16"],
                        "NIST AI RMF": ["GOVERN-1.1", "MANAGE-2.3"],
                    },
                    remediation_plan=[
                        "Review affected controls and exceptions",
                        "Communicate policy intent and approved alternatives",
                        "Add monitoring for the observed circumvention pattern",
                    ],
                    predicted_residual_risk="medium",
                )
            )
        return findings

    # -- Q&A --------------------------------------------------------------

    async def answer(self, question: str, max_events: int = 40) -> Answer:
        relevant = self._relevant_events(question, max_events)
        if not relevant:
            return Answer(question, "No events in the log relate to that question.", [])
        user = self._qa_prompt(question, relevant)
        text = await self.backend.complete(_QA_SYSTEM, user, max_tokens=1000)
        cited = _extract_citations(text, {e.event_id for e in relevant})
        return Answer(question, text.strip(), cited)

    def _relevant_events(self, question: str, max_events: int) -> list[Event]:
        terms = {t for t in re.findall(r"[a-z0-9]+", question.lower()) if len(t) >= 2}
        events = self.log.all()
        scored: list[tuple[int, Event]] = []
        for ev in events:
            hay = f"{ev.agent_id} {ev.action} {ev.target or ''} {ev.rationale}".lower()
            score = sum(1 for t in terms if t in hay)
            if score:
                scored.append((score, ev))
        scored.sort(key=lambda pair: (pair[0], pair[1].event_id), reverse=True)
        selected = [ev for _, ev in scored[:max_events]]
        selected.sort(key=lambda e: e.event_id)
        return selected

    def _qa_prompt(self, question: str, events: list[Event]) -> str:
        lines = [f"Question: {question}", "", "Events:"]
        for ev in events:
            lines.append(
                f"[evt-{ev.event_id}] tick={ev.tick} {ev.agent_id} {ev.action}"
                + (f" -> {ev.target}" if ev.target else "")
                + f": {ev.rationale}"
            )
        lines.append("\nAnswer, citing event ids inline as [evt-<id>].")
        return "\n".join(lines)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return -1


def _clean_mappings(raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key in ("NIST CSF", "ISO 27001", "NIST AI RMF"):
        vals = raw.get(key, [])
        if isinstance(vals, list):
            out[key] = [str(v) for v in vals]
        elif vals:
            out[key] = [str(vals)]
    return out


def _extract_citations(text: str, valid: set[int]) -> list[int]:
    ids = {int(m) for m in re.findall(r"evt-(\d+)", text)}
    return sorted(i for i in ids if i in valid)
