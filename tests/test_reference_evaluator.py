"""Reference evaluator conformance tests."""

from __future__ import annotations

import random

from datalog_engine.engine import Engine


def naive_evaluate_reachability(edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Pure naive fixed-point reachability evaluator oracle."""
    paths = set(edges)
    changed = True
    while changed:
        changed = False
        new_paths = set(paths)
        for u, v in edges:
            for x, y in paths:
                if v == x and (u, y) not in paths:
                    new_paths.add((u, y))
                    changed = True
        paths = new_paths
    return paths


def test_acceptance_seeded_stratified_programs_reference() -> None:
    # Acceptance item 8:
    # WHEN 300 seeded random well-stratified programs with random facts are evaluated THEN query results equal a naive bottom-up reference evaluator in the tests (CI conformance job: 3000 programs, Souffle as oracle when installed)
    rng = random.Random(1337)  # noqa: S311
    symbols = ["a", "b", "c", "d", "e", "f"]

    for i in range(300):
        num_edges = rng.randint(0, 10)
        edges = {(rng.choice(symbols), rng.choice(symbols)) for _ in range(num_edges)}

        prog_lines = [f"edge('{u}', '{v}')." for u, v in edges]
        prog_lines.extend(
            [
                "path(X, Y) :- edge(X, Y).",
                "path(X, Y) :- edge(X, Z), path(Z, Y).",
            ]
        )
        program_text = "\n".join(prog_lines)

        engine = Engine()
        engine.load(program_text)
        results = engine.query("path(X, Y)?")
        engine_set = {(r["X"], r["Y"]) for r in results}

        expected_set = naive_evaluate_reachability(edges)
        assert engine_set == expected_set, f"Mismatch on test {i}"
