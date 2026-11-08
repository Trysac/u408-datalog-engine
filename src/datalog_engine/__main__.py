"""CLI entry point for datalog-engine."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from datalog_engine.engine import Engine
from datalog_engine.errors import DatalogError


def run_eval(engine: Engine, text: str) -> int:
    """Run an evaluation from an inline string or file."""
    # Split queries vs program
    # Any statement ending with '?' is evaluated as a query
    # We first load the text to let the engine parse and evaluate rules
    try:
        engine.load(text)
    except DatalogError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1

    # Look for query statements in the text
    # Simple heuristic to extract queries from text
    lines = text.splitlines()
    query_lines = [line.strip() for line in lines if line.strip().endswith("?")]
    if not query_lines and "?" in text:
        parts = text.split(".")
        for part in parts:
            p = part.strip()
            if p.endswith("?"):
                query_lines.append(p)

    results: list[dict[str, Any]] = []
    for q in query_lines:
        try:
            res = engine.query(q)
            results.extend(res)
        except DatalogError as err:
            sys.stderr.write(f"Error querying {q}: {err}\n")
            return 1

    sys.stdout.write(json.dumps(results) + "\n")
    return 0


def repl(engine: Engine) -> int:
    """Interactive REPL loop."""
    sys.stdout.write("Datalog Engine REPL. Type 'exit' or Ctrl-D to quit.\n")
    while True:
        try:
            line = input("datalog> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write("\n")
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        try:
            if line.endswith("?"):
                res = engine.query(line)
                sys.stdout.write(json.dumps(res, indent=2) + "\n")
            else:
                engine.load(line)
                sys.stdout.write("OK\n")
        except DatalogError as err:
            sys.stderr.write(f"Error: {err}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datalog-engine", description="stratified Datalog engine")
    parser.add_argument("--eval", type=str, help="Datalog program text to evaluate and query")
    parser.add_argument("file", nargs="?", type=str, help="Optional Datalog program file to load")

    args = parser.parse_args(argv)
    engine = Engine()

    if args.eval:
        return run_eval(engine, args.eval)

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                content = f.read()
            return run_eval(engine, content)
        except (OSError, UnicodeDecodeError) as err:
            sys.stderr.write(f"IO Error: {err}\n")
            return 2

    return repl(engine)


if __name__ == "__main__":
    sys.exit(main())
