"""In-memory stratified Datalog engine with semi-naive evaluation,
DRed incremental view updates, aggregates, and derivation explanations.
"""

from __future__ import annotations

from datalog_engine.ast import DerivationNode
from datalog_engine.engine import Engine
from datalog_engine.errors import (
    DatalogError,
    ParseError,
    ProgramLimitError,
    SafetyError,
    StratificationError,
)

__all__ = [
    "DatalogError",
    "DerivationNode",
    "Engine",
    "ParseError",
    "ProgramLimitError",
    "SafetyError",
    "StratificationError",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for datalog-engine."""
    from datalog_engine.__main__ import main as _main

    return _main(argv)
