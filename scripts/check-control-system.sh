#!/usr/bin/env bash
set -euo pipefail

required_files=(
  "AGENTS.md"
  "docs/control/ANCHOR-1.0.md"
  "state.yaml"
  "requirements/README.md"
  "docs/decisions/ADR-001-anchor-name-and-architecture.md"
  "evidence/README.md"
  "events.jsonl"
)

for file in "${required_files[@]}"; do
  test -s "$file"
done

grep -q 'system_version: "1.0"' state.yaml
grep -q 'system: "ANCHOR"' state.yaml
grep -q '项目原生控制层' docs/control/ANCHOR-1.0.md
grep -q '待人类决策者确认' docs/decisions/ADR-001-anchor-name-and-architecture.md

python3 - <<'PY'
import json
from pathlib import Path

for line_number, line in enumerate(Path("events.jsonl").read_text().splitlines(), 1):
    if line.strip():
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"events.jsonl line {line_number}: {exc}")
PY

echo "ANCHOR 1.0 control files: OK"
