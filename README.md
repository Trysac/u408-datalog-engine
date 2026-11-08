# datalog-engine

[![PyPI version](https://img.shields.io/pypi/v/trysac-datalog-engine)](https://pypi.org/project/trysac-datalog-engine/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-datalog-engine)](LICENSE)
[![CI](https://github.com/Trysac/u408-datalog-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u408-datalog-engine/actions/workflows/ci.yml)

In-memory stratified Datalog engine in pure Python with semi-naive bottom-up evaluation, DRed incremental view updates, aggregates, and derivation explanations.

## Problem

Access control policies and graph lineage systems require recursive reasoning that responds quickly to changing facts without high-latency re-evaluation. Full deductive recomputation on single fact insertions or deletions causes unacceptable latency spikes and inconsistent authorization states. This engine provides stratified negation, incremental rederivation, and derivation proofs without external binary dependencies.

## Installation

```sh
pip install trysac-datalog-engine
# Optional audit logging support
pip install trysac-datalog-engine[audit]
```

Requires Python 3.10 or newer.

## Usage

```python
from datalog_engine import Engine

engine = Engine()
engine.load("""
edge('a', 'b').
edge('b', 'c').
path(X, Y) :- edge(X, Y).
path(X, Y) :- edge(X, Z), path(Z, Y).
""")
print(engine.query("path('a', X)?"))
# [{'X': 'b'}, {'X': 'c'}]
```

## Public API Summary

### Core Classes
- `datalog_engine.Engine`: Primary API.
    - `load(text: str) -> None`: Parses, stratifies, and evaluates a program.
    - `add_facts(predicate: str, rows: Iterable[tuple[Any, ...]]) -> int`: Incremental addition.
    - `retract_facts(predicate: str, rows: Iterable[tuple[Any, ...]]) -> int`: Incremental retraction (DRed).
    - `query(query_str: str) -> list[dict[str, Any]]`: Returns variable bindings.
    - `explain(fact: tuple[str, tuple[Any, ...]]) -> DerivationNode`: Returns an explanation tree.
- `datalog_engine.DerivationNode`: Tree structure for explanations.

### Limits and Options
- `max_program_bytes`: 1,000,000 bytes default.
- `max_iterations`: 10,000 per fixpoint.
- `max_strata`: 100 maximum negation layers.
- `max_arity`: 32 columns per predicate.

### Errors
- `DatalogError`: Base class for engine exceptions.
- `ParseError`: Syntax or arity limit violations.
- `SafetyError`: Raised for unsafe variables.
- `StratificationError`: Cycles through negation or aggregation.
- `ProgramLimitError`: Exceeded size or iteration counts.

## Why not <best-known alternative>

Unlike Souffle, `datalog-engine` requires no external C++ toolchains or native compilation steps, ensuring 100% portability. Unlike pyDatalog, it enforces stratified negation cycle rejection and sound DRed incremental derivation maintenance without full process restarts.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and resource constraints.
