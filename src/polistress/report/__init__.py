"""report — synthesize a findings register and answer questions over a run.

The :class:`ReportAgent` reads the full event log plus the world graph, derives
grounded signals, and uses a real LLM backend to produce structured findings
(with framework mappings and event-id citations) and to answer questions.
"""

from .agent import Answer, ReportAgent
from .backend import AnthropicReportBackend, ReportBackend
from .findings import Finding, findings_to_csv, findings_to_json, write_csv, write_json
from .signals import Signal, derive_signals

__all__ = [
    "ReportAgent",
    "Answer",
    "ReportBackend",
    "AnthropicReportBackend",
    "Finding",
    "findings_to_json",
    "findings_to_csv",
    "write_json",
    "write_csv",
    "Signal",
    "derive_signals",
]
