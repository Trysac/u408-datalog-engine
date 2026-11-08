# Project Record

## Objective

Provide an enterprise-grade pure-Python stratified Datalog engine featuring semi-naive bottom-up evaluation, DRed incremental view updates, head aggregates, and derivation explanations.

## Scope

- Datalog lexer and recursive descent parser (predicates, integers, strings, variables, comparisons, negative literals).
- Safety validation (range restriction).
- Stratification using Tarjan's SCC algorithm.
- Semi-naive bottom-up evaluator.
- DRed (Delete and Rederive) incremental maintenance.
- Derivation tree construction for explanations.
- CLI and interactive REPL.

## Out-of-Scope

- Function symbols or non-ground compound terms.
- Distributed evaluation across multiple nodes.
- Persistent disk storage engines.
- Disjunctive logic programming.
- Abduction.

## Line comparison metrics

| Model | Line | Fix rounds | Input tokens | Output tokens | Cost | Time | Failing checks per round | Conformance percentage | Integrations achieved | Public API only |
|---|---|---|---|---|---|---|---|---|---|---|

## Factory run u408 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| analyst | gemini-3.8-flash | no | 3496 | 1410 | 0 | 0 | 0.0079 |
| generation | gemini-3.8-flash | yes | 9282 | 22823 | 0 | 0 | 0.0463 |
| fix-1 | gemini-3.8-flash | no | 125269 | 5243 | 0 | 1717566 | 0.2424 |
| fix-2 | gemini-3.8-flash | no | 93322 | 1764 | 0 | 884583 | 0.1429 |
| fix-3 | gemini-3.8-flash | no | 32591 | 353 | 0 | 72423 | 0.0312 |
| fix-4 | gemini-3.8-flash | no | 127408 | 1318 | 0 | 849400 | 0.1642 |
| fix-5 | gemini-3.8-flash | no | 73957 | 6489 | 0 | 607540 | 0.1254 |
| fix-6 | gemini-3.8-flash | no | 54703 | 669 | 0 | 274079 | 0.0641 |
| fix-1 | gemini-3.8-flash | no | 31460 | 679 | 0 | 49722 | 0.0299 |
| fix-2 | gemini-3.8-flash | no | 37151 | 793 | 0 | 105688 | 0.0388 |
| audit | gemini-3.8-flash | no | 157123 | 1352 | 0 | 1709325 | 0.2511 |
| docs | gemini-3.1-flash-lite | no | 137857 | 1676 | 0 | 0 | 0.0370 |

Total: $1.1811. Prices: Anthropic list prices.
