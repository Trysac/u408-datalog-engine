# Architecture

## Overview

`trysac-datalog-engine` implements an in-memory stratified Datalog engine with:
1. **Lexer and Parser**: Recursive descent parser supporting literals, integers, strings, variables, comparisons, negative literals, and head aggregate expressions (`count`, `sum`, `min`, `max`).
2. **Safety Validator**: Enforces range restriction ensuring all variables in rule heads, negated literals, and comparisons are bound by positive relational body literals.
3. **Stratification via Tarjan's SCC Algorithm**: Builds a dependency graph between predicate symbols. Disallows cycles containing negation or aggregation and assigns stratum layers.
4. **Semi-naive Bottom-up Evaluator**: Efficient fixpoint loop evaluating only new tuples (deltas) generated in each iteration.
5. **Incremental Maintenance (DRed)**: Implements Delete and Rederive algorithm for fact retractions, maintaining derived relations without recomputing from scratch.
6. **Derivation Proofs**: `engine.explain(fact)` reconstructs the full derivation tree showing which rules and facts proved the query.
7. **Optional Audit Adapter**: Pluggable integration with `trysac-tamper-evident-log` and `trysac-audit-event-schema`.
