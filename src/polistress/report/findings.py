"""The findings register data model and its JSON / CSV serializations."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_SEVERITIES = frozenset({"critical", "high", "medium", "low", "informational"})


@dataclass
class Finding:
    """A single GRC finding with framework mappings and event-id citations."""

    id: str
    title: str
    description: str
    severity: str
    affected_assets: list[str] = field(default_factory=list)
    root_cause_events: list[int] = field(default_factory=list)
    domain: str = "ai_governance"
    framework_mappings: dict[str, list[str]] = field(default_factory=dict)
    remediation_plan: list[str] = field(default_factory=list)
    predicted_residual_risk: str = "medium"

    def __post_init__(self) -> None:
        sev = self.severity.lower()
        self.severity = sev if sev in _SEVERITIES else "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def findings_to_json(findings: list[Finding], indent: int = 2) -> str:
    return json.dumps([f.to_dict() for f in findings], indent=indent)


def write_json(findings: list[Finding], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(findings_to_json(findings), encoding="utf-8")


_CSV_COLUMNS = [
    "id",
    "title",
    "severity",
    "domain",
    "affected_assets",
    "root_cause_events",
    "nist_csf",
    "iso_27001",
    "nist_ai_rmf",
    "remediation_plan",
    "predicted_residual_risk",
    "description",
]


def findings_to_csv(findings: list[Finding]) -> str:
    """Serialize findings to CSV suitable for GRC-tool import."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    for f in findings:
        fm = f.framework_mappings or {}
        writer.writerow(
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity,
                "domain": f.domain,
                "affected_assets": "; ".join(f.affected_assets),
                "root_cause_events": "; ".join(str(e) for e in f.root_cause_events),
                "nist_csf": "; ".join(fm.get("NIST CSF", [])),
                "iso_27001": "; ".join(fm.get("ISO 27001", [])),
                "nist_ai_rmf": "; ".join(fm.get("NIST AI RMF", [])),
                "remediation_plan": " | ".join(f.remediation_plan),
                "predicted_residual_risk": f.predicted_residual_risk,
                "description": f.description,
            }
        )
    return buf.getvalue()


def write_csv(findings: list[Finding], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(findings_to_csv(findings), encoding="utf-8")
