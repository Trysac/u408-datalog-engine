# Security

## Threat Model

### Defended Limits
- **Program Size**: Inputs are capped at 1,000,000 bytes. The engine raises `ProgramLimitError(code='program_size_exceeded')` if this is exceeded.
- **Iteration Count**: Fixpoint loops cap at 10,000 iterations to prevent resource exhaustion from non-terminating policies. Exceeding this raises `ProgramLimitError(code='iteration_limit_exceeded')`.
- **Stratification Depth**: Cycles through negation or aggregation are rejected during parsing/stratification to ensure termination, limited to 100 strata.
- **Arity Limits**: Predicates are limited to 32 arguments per fact to prevent stack overflow or memory exhaustion.
- **Information Leakage**: Error messages are strictly bounded to 200 characters and are designed to avoid leaking internal state or sensitive data values.

### Not Defended
- Maliciously constructed programs designed to be computationally expensive within the iteration/strata limits remain a risk.
- Arbitrary user input in external integrations (if adapters are used).
