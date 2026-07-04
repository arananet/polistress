"""The action vocabulary agents can emit each tick."""

from __future__ import annotations

from enum import StrEnum


class Action(StrEnum):
    """A decision an agent can take in response to observed events."""

    COMPLY = "comply"
    WORKAROUND = "workaround"
    REQUEST_EXCEPTION = "request_exception"
    ESCALATE = "escalate"
    EXPLOIT_ATTEMPT = "exploit_attempt"
    REPORT_CONCERN = "report_concern"
    IGNORE = "ignore"


ACTIONS: frozenset[str] = frozenset(a.value for a in Action)

# The synthetic policy-injection marker action (system-emitted at tick 0).
POLICY_INJECTION = "policy_injection"
