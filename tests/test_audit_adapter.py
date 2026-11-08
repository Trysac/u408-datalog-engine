"""Tests for the optional audit logging adapter."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

try:
    from tamper_evident_log import AuditLog

    from datalog_engine.adapters.audit import AuditLogger

    HAS_AUDIT = True
except ImportError:
    HAS_AUDIT = False

from datalog_engine.engine import Engine


@pytest.mark.skipif(not HAS_AUDIT, reason="Audit dependencies not installed")
def test_audit_adapter_logging() -> None:
    fixed_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    log = AuditLog(clock=lambda: fixed_time)
    logger = AuditLogger(log=log, clock=lambda: fixed_time, id_factory=lambda: "evt-001")

    engine = Engine()
    engine.load("""
    user_role('alice', 'admin').
    role_perm('admin', 'read').
    permit(U, P) :- user_role(U, R), role_perm(R, P).
    """)

    is_allowed = len(engine.query("permit('alice', 'read')?")) > 0
    proof = engine.explain(("permit", ("alice", "read")))

    event = logger.record_decision(
        actor_id="alice",
        action="invoice.read",
        resource="inv-123",
        allowed=is_allowed,
        proof=proof,
    )

    assert event.actor.id == "alice"
    assert event.outcome == "success"
    report = log.verify()
    assert report.ok is True
