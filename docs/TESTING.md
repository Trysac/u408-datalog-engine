# Testing

## Test Strategy

1. **Unit tests (`tests/test_datalog_engine.py`)**: Covers parser logic, safety validation, stratification cycle detection, head aggregate correctness, and CLI behavior.
2. **Incremental property tests (`tests/test_incremental_property.py`)**: Executes 200 seeded sequences of random additions and retractions, ensuring incremental DRed results match full re-evaluation from scratch.
3. **Reference evaluation (`tests/test_reference_evaluator.py`)**: Compares results of 300 seeded programs against a naive bottom-up reference evaluator.
4. **Audit adapter**: Verified for integration with `trysac-tamper-evident-log` and `trysac-audit-event-schema`.

## Running Tests

```sh
uv run pytest --cov=datalog_engine
```
