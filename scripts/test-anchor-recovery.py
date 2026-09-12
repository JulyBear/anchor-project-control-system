#!/usr/bin/env python3
"""Offline tests for deterministic ANCHOR recovery."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_project(target: Path) -> None:
    for relative in (
        "AGENTS.md",
        "state.yaml",
        "events.jsonl",
        "scripts/anchor-validate.py",
        "scripts/anchor-recover.py",
        "docs/control/ANCHOR-1.0.md",
        "requirements/README.md",
        "docs/decisions/ADR-001-anchor-name-and-architecture.md",
        "evidence/README.md",
        "external/README.md",
    ):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="anchor-recovery-") as directory:
        sandbox = Path(directory)
        copy_project(sandbox)
        result = subprocess.run(["python3", "scripts/anchor-recover.py"], cwd=sandbox, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        for expected in ("ANCHOR recovery brief", "active_item: INIT-001", "next_action:"):
            assert expected in result.stdout, expected
        state = sandbox / "state.yaml"
        state.write_text(state.read_text(encoding="utf-8").replace('phase: "discovery"', 'phase: "verify"'), encoding="utf-8")
        result = subprocess.run(["python3", "scripts/anchor-recover.py"], cwd=sandbox, capture_output=True, text=True)
        assert result.returncode != 0, "recovery must stop on state/audit conflict"
        assert "ANCHOR recovery STOPPED" in result.stderr
    print("ANCHOR recovery tests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
