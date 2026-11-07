# datalog-engine

[![PyPI version](https://img.shields.io/pypi/v/trysac-datalog-engine)](https://pypi.org/project/trysac-datalog-engine/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-datalog-engine)](LICENSE)
[![CI](https://github.com/Trysac/u408-datalog-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u408-datalog-engine/actions/workflows/ci.yml)

In-memory stratified Datalog engine in pure Python with semi-naive evaluation, DRed incremental view updates, aggregates, and derivation explanations.

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-datalog-engine
# or
uv add trysac-datalog-engine
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import datalog_engine

# normalize() trims surrounding whitespace and lower-cases the text.
print(datalog_engine.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    datalog_engine.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
