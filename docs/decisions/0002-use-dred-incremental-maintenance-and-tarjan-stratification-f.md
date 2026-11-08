# Use DRed Incremental Maintenance and Tarjan Stratification for Datalog Engine

Status: accepted (generated, pending human review)

## Context

Dynamic authorization and graph lineage engines require immediate consistency when facts are inserted or retracted without the latency penalty of full re-evaluation. Additionally, recursive policies with negation must detect cyclical dependencies cleanly.

## Decision

Implement semi-naive bottom-up evaluation combined with Tarjan's Strongly Connected Components algorithm for stratum partitioning, and the Delete-and-Rederive (DRed) algorithm for incremental view maintenance.

## Consequences

Provides sound stratified negation and efficient sub-millisecond fact additions and retractions while remaining 100% pure Python without external compiler dependencies.
