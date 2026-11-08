#!/usr/bin/env bash
set -euo pipefail

echo "CI conformance setup: checking tools and prerequisites."
if command -v souffle >/dev/null 2>&1; then
  echo "Souffle is already installed."
else
  echo "Souffle not present. Reference tests will use internal Python oracle."
fi
