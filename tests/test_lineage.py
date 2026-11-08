"""Integration tests with trysac-md-knowledge-graph."""

from __future__ import annotations

import pytest

from datalog_engine.engine import Engine

try:
    from md_knowledge_graph import build_graph, parse_note

    HAS_MD_KG = True
except ImportError:
    HAS_MD_KG = False


@pytest.mark.skipif(not HAS_MD_KG, reason="trysac-md-knowledge-graph not installed")
def test_md_knowledge_graph_lineage() -> None:
    n1 = parse_note("a.md", "# A\nSee [[b]]")
    n2 = parse_note("b.md", "# B\nSee [[c]]")
    n3 = parse_note("c.md", "# C\nLeaf note")
    graph = build_graph([n1, n2, n3])

    engine = Engine()
    engine.load("""
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- edge(X, Z), path(Z, Y).
    """)

    facts = [(e.source, e.target) for e in graph.edges]
    engine.add_facts("edge", facts)

    results = engine.query("path('a', X)?")
    destinations = {r["X"] for r in results}
    assert destinations == {"b", "c"}
