"""Unit and acceptance tests for datalog_engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datalog_engine.ast import DerivationNode
from datalog_engine.engine import Engine
from datalog_engine.errors import (
    DatalogError,
    ParseError,
    ProgramLimitError,
    SafetyError,
    StratificationError,
)


def test_acceptance_transitive_closure() -> None:
    # Acceptance item 1:
    # WHEN evaluating a recursive transitive closure over edge('a', 'b') and edge('b', 'c') THEN query("path('a', X)?") yields exactly [{'X': 'b'}, {'X': 'c'}]
    engine = Engine()
    engine.load("""
    edge('a', 'b').
    edge('b', 'c').
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- edge(X, Z), path(Z, Y).
    """)
    results = engine.query("path('a', X)?")
    assert results == [{"X": "b"}, {"X": "c"}]


def test_acceptance_unstratified_negation() -> None:
    # Acceptance item 2:
    # IF a rule contains unstratified negation such as 'p(X) :- q(X), not p(X).' THEN validate_program raises StratificationError with code 'stratification_cycle'
    engine = Engine()
    with pytest.raises(StratificationError) as exc_info:
        engine.load("""
        q(1).
        p(X) :- q(X), not p(X).
        """)
    assert exc_info.value.code == "stratification_cycle"


def test_acceptance_dred_retraction() -> None:
    # Acceptance item 3:
    # WHEN a fact is retracted via retract_facts('edge', [('a', 'b')]) THEN the incremental DRed algorithm updates path derivations so query("path('a', 'c')?") returns an empty list []
    engine = Engine()
    engine.load("""
    edge('a', 'b').
    edge('b', 'c').
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- edge(X, Z), path(Z, Y).
    """)
    assert len(engine.query("path('a', 'c')?")) == 1
    count = engine.retract_facts("edge", [("a", "b")])
    assert count == 1
    assert engine.query("path('a', 'c')?") == []


def test_acceptance_head_aggregates() -> None:
    # Acceptance item 4:
    # WHEN computing head aggregates on score facts 10 and 20 with rule 'total(sum<S>) :- score(S).' THEN query("total(T)?") returns exactly [{'T': 30}]
    engine = Engine()
    engine.load("""
    score(10).
    score(20).
    total(sum<S>) :- score(S).
    """)
    results = engine.query("total(T)?")
    assert results == [{"T": 30}]


def test_acceptance_explain() -> None:
    # Acceptance item 5:
    # WHEN explain(('path', ('a', 'c'))) is called on the derived fact THEN it returns a DerivationNode with rule_id 'path/2' whose children are the nodes for ('edge', ('a', 'b')) and ('path', ('b', 'c'))
    engine = Engine()
    engine.load("""
    edge('a', 'b').
    edge('b', 'c').
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- edge(X, Z), path(Z, Y).
    """)
    node = engine.explain(("path", ("a", "c")))
    assert isinstance(node, DerivationNode)
    assert node.rule_id == "path/2"
    child_facts = [c.fact for c in node.children]
    assert child_facts == [("edge", ("a", "b")), ("path", ("b", "c"))]


def test_acceptance_max_program_bytes() -> None:
    # Acceptance item 6:
    # IF input Datalog text exceeds max_program_bytes of 1000000 bytes THEN Engine.load raises ProgramLimitError with code 'program_size_exceeded'
    engine = Engine(max_program_bytes=100)
    oversized_input = "% " + ("x" * 101)
    with pytest.raises(ProgramLimitError) as exc_info:
        engine.load(oversized_input)
    assert exc_info.value.code == "program_size_exceeded"


def test_acceptance_cli_eval(capsys: pytest.CaptureFixture[str]) -> None:
    # Acceptance item 7:
    # WHEN 'python -m datalog_engine --eval "p(1). p(X)?"' runs THEN the process exits with code 0 and prints '[{"X": 1}]' to stdout
    from datalog_engine.__main__ import main as cli_main

    code = cli_main(["--eval", "p(1). p(X)?"])
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out.strip()) == [{"X": 1}]


def test_safety_unsafe_variable() -> None:
    engine = Engine()
    with pytest.raises(SafetyError) as exc:
        engine.load("p(X) :- q(Y).")
    assert exc.value.code == "unsafe_variable"

    with pytest.raises(SafetyError) as exc:
        engine.load("p(X) :- q(X), not r(Y).")
    assert exc.value.code == "unsafe_variable"

    with pytest.raises(SafetyError) as exc:
        engine.load("p(X) :- q(X), Y > 10.")
    assert exc.value.code == "unsafe_variable"

    with pytest.raises(SafetyError) as exc:
        engine.load("p(X).")
    assert exc.value.code == "unsafe_variable"


def test_parse_errors() -> None:
    engine = Engine(max_arity=2)
    with pytest.raises(ParseError):
        engine.load("p(1, 2, 3).")

    with pytest.raises(ParseError):
        engine.load("p(.")


def test_iteration_limit() -> None:
    engine = Engine(max_iterations=5)
    # Generate chain longer than 5 iterations
    program = "edge(0, 1).\n"
    for i in range(1, 10):
        program += f"edge({i}, {i + 1}).\n"
    program += """
    reach(X, Y) :- edge(X, Y).
    reach(X, Y) :- reach(X, Z), edge(Z, Y).
    """
    with pytest.raises(ProgramLimitError) as exc:
        engine.load(program)
    assert exc.value.code == "iteration_limit_exceeded"


def test_aggregates_group_by() -> None:
    engine = Engine()
    engine.load("""
    item('apple', 10).
    item('apple', 20).
    item('banana', 5).
    item('banana', 15).
    total(Category, sum<Cost>) :- item(Category, Cost).
    cnt(Category, count<Cost>) :- item(Category, Cost).
    min_cost(Category, min<Cost>) :- item(Category, Cost).
    max_cost(Category, max<Cost>) :- item(Category, Cost).
    """)
    tot = engine.query("total(C, T)?")
    assert tot == [{"C": "apple", "T": 30}, {"C": "banana", "T": 20}]
    cnt = engine.query("cnt(C, K)?")
    assert cnt == [{"C": "apple", "K": 2}, {"C": "banana", "K": 2}]
    min_res = engine.query("min_cost(C, M)?")
    assert min_res == [{"C": "apple", "M": 10}, {"C": "banana", "M": 5}]
    max_res = engine.query("max_cost(C, M)?")
    assert max_res == [{"C": "apple", "M": 20}, {"C": "banana", "M": 15}]


def test_cyclic_same_generation() -> None:
    engine = Engine()
    engine.load("""
    parent('a', 'b').
    parent('a', 'c').
    parent('b', 'd').
    parent('c', 'e').
    sg(X, Y) :- parent(P, X), parent(P, Y), X != Y.
    sg(X, Y) :- parent(P1, X), parent(P2, Y), sg(P1, P2).
    """)
    res = engine.query("sg('d', X)?")
    assert res == [{"X": "e"}]


def test_empty_program_and_retract_nonexistent() -> None:
    engine = Engine()
    engine.load("// this is comment\n% another comment\n")
    assert engine.query("empty(X)?") == []
    assert engine.query("") == []
    # Retracting non-existent fact returns 0 without error
    ret = engine.retract_facts("edge", [("non", "existent")])
    assert ret == 0


def test_add_facts_incrementally() -> None:
    engine = Engine()
    engine.load("""
    path(X, Y) :- edge(X, Y).
    path(X, Y) :- path(X, Z), edge(Z, Y).
    """)
    assert engine.query("path('a', X)?") == []
    added = engine.add_facts("edge", [("a", "b"), ("b", "c")])
    assert added == 2
    assert engine.query("path('a', X)?") == [{"X": "b"}, {"X": "c"}]
    # Re-adding existing facts returns 0
    assert engine.add_facts("edge", [("a", "b")]) == 0


def test_explain_error_and_root_fact() -> None:
    engine = Engine()
    engine.load("fact(1).")
    node = engine.explain(("fact", (1,)))
    assert node.is_fact is True
    assert node.rule_id is None
    assert node.children == []
    assert node.to_dict()["predicate"] == "fact"

    with pytest.raises(DatalogError) as exc:
        engine.explain(("nonexistent", (999,)))
    assert exc.value.code == "unknown_fact"


def test_events_callback() -> None:
    events = []
    engine = Engine(on_event=lambda e: events.append(e))
    engine.load("p(1).")
    engine.add_facts("q", [(2,)])
    engine.query("p(X)?")
    engine.retract_facts("q", [(2,)])
    assert any(e["event"] == "load" for e in events)
    assert any(e["event"] == "add_facts" for e in events)
    assert any(e["event"] == "query" for e in events)
    assert any(e["event"] == "retract_facts" for e in events)


def test_top_level_main_and_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datalog_engine import main as top_main

    # Test top-level main calling CLI --eval
    ret = top_main(["--eval", "edge(1, 2). edge(X, Y)?"])
    captured = capsys.readouterr()
    assert ret == 0
    assert json.loads(captured.out.strip()) == [{"X": 1, "Y": 2}]

    # Test error in --eval
    ret_err = top_main(["--eval", "p(X) :- q(Y)."])
    assert ret_err == 1

    # Test file execution
    fdir = tmp_path / "dl"
    fdir.mkdir()
    fpath = fdir / "prog.dl"
    fpath.write_text("fact('hello'). fact(X)?", encoding="utf-8")
    ret_f = top_main([str(fpath)])
    captured_f = capsys.readouterr()
    assert ret_f == 0
    assert json.loads(captured_f.out.strip()) == [{"X": "hello"}]

    # Test missing file error
    ret_non = top_main(["non_existent_file.dl"])
    assert ret_non == 2

    # Test REPL
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("edge(1, 2).\nedge(X, Y)?\nexit\n"))
    ret_repl = top_main([])
    assert ret_repl == 0

    # Test REPL EOFError
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    ret_repl_eof = top_main([])
    assert ret_repl_eof == 0


def test_ast_and_eval_coverage() -> None:
    from datalog_engine.ast import AggregateTerm, Atom, Comparison, Constant, Rule, Variable

    # Test AST __repr__ methods
    c = Constant("val")
    v = Variable("X")
    agg = AggregateTerm("sum", v)
    atom_pos = Atom("p", (v,))
    atom_neg = Atom("p", (v,), is_negated=True)
    cmp_eq = Comparison("==", v, c)
    rule = Rule(head=atom_pos, body=(atom_neg, cmp_eq), rule_id="p/1")

    assert repr(c) == "'val'"
    assert repr(v) == "X"
    assert repr(agg) == "sum<X>"
    assert repr(atom_pos) == "p(X)"
    assert repr(atom_neg) == "not p(X)"
    assert repr(cmp_eq) == "X == 'val'"
    assert "p(X) :- not p(X), X == 'val'." in repr(rule)

    # Test parser tokens repr and build_indexes
    engine = Engine()
    engine.load("p(1, 2). p(1, 3).")
    indexes = engine.evaluator.build_indexes("p")
    assert len(indexes) == 2
    assert (1, 2) in indexes[1][(1, 2)]

    # Test comparison filters
    engine2 = Engine()
    engine2.load("""
    num(1). num(2). num(3).
    less(X) :- num(X), X < 2.
    lte(X) :- num(X), X <= 2.
    gt(X) :- num(X), X > 2.
    gte(X) :- num(X), X >= 2.
    eq(X) :- num(X), X = 2.
    neq(X) :- num(X), X != 2.
    """)
    assert engine2.query("less(X)?") == [{"X": 1}]
    assert len(engine2.query("lte(X)?")) == 2
    assert engine2.query("gt(X)?") == [{"X": 3}]
    assert len(engine2.query("gte(X)?")) == 2
    assert engine2.query("eq(X)?") == [{"X": 2}]
    assert len(engine2.query("neq(X)?")) == 2
