"""Property tests for DRed incremental maintenance equivalence."""

from __future__ import annotations

import random

from datalog_engine.engine import Engine


def test_acceptance_random_add_retract_equivalence() -> None:
    # Acceptance item 9:
    # WHEN 200 seeded sequences of random add_facts and retract_facts run THEN every query result equals a full recomputation from scratch
    rng = random.Random(42)  # noqa: S311
    nodes = [f"n{i}" for i in range(1, 9)]

    program_rules = """
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- edge(X, Z), path(Z, Y).
    """

    engine = Engine()
    engine.load(program_rules)
    current_edges: set[tuple[str, str]] = set()

    for step in range(200):
        action = rng.choice(["add", "retract"])
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        fact = (u, v)

        if action == "add" or not current_edges:
            current_edges.add(fact)
            engine.add_facts("edge", [fact])
        else:
            # Retract an existing edge or random one
            chosen = rng.choice(list(current_edges))
            current_edges.remove(chosen)
            engine.retract_facts("edge", [chosen])

        # Verification against full recomputation from scratch
        scratch_engine = Engine()
        scratch_engine.load(program_rules)
        if current_edges:
            scratch_engine.add_facts("edge", list(current_edges))

        res_inc = engine.query("path(X, Y)?")
        res_scratch = scratch_engine.query("path(X, Y)?")
        assert res_inc == res_scratch, (
            f"Failed at step {step}: action={action}, edges={current_edges}"
        )
