"""Audit adapter integrating with trysac-tamper-evident-log and trysac-audit-event-schema."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

try:
    from audit_event_schema import Actor, AuditEvent, Target, new_event
    from tamper_evident_log import AuditLog
except ImportError as err:
    raise ImportError(
        "The 'audit' extra is required to use datalog_engine.adapters.audit. "
        "Install with: pip install trysac-datalog-engine[audit]"
    ) from err

from datalog_engine.ast import DerivationNode


class AuditLogger:
    """Records authorization decisions with derivation trees into a tamper-evident log."""

    def __init__(
        self,
        log: AuditLog,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.log = log
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory

    def record_decision(
        self,
        actor_id: str,
        action: str,
        resource: str,
        allowed: bool,
        proof: DerivationNode | None = None,
    ) -> AuditEvent:
        """Record an authorization decision event."""
        actor = Actor("user", actor_id)
        target = Target("resource", resource)
        outcome = "success" if allowed else "denied"

        # Prepare serializable proof data
        data: dict[str, Any] = {"allowed": allowed}
        if proof is not None:
            data["proof"] = proof.to_dict()

        kwargs: dict[str, Any] = {
            "actor": actor,
            "action": action,
            "target": target,
            "outcome": outcome,
            "clock": self.clock,
        }
        if self.id_factory is not None:
            kwargs["id_factory"] = self.id_factory

        event = new_event(**kwargs)
        # Append to tamper-evident audit log
        self.log.append(actor_id, action, data)
        return event
