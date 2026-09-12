#!/usr/bin/env python3
"""Run repeatable fault-injection tests for the ANCHOR 1.0 file protocol."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "AGENTS.md",
    "docs/control/ANCHOR-1.0.md",
    "state.yaml",
    "requirements/README.md",
    "docs/decisions/ADR-001-anchor-name-and-architecture.md",
    "evidence/README.md",
    "events.jsonl",
    "external/README.md",
    "scripts/anchor-validate.py",
]


def make_sandbox(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    for relative in REQUIRED:
        source = ROOT / relative
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (path / "requirements/REQ-SBX-001.md").write_text(
        "# REQ-SBX-001\n\n- 设计：DES-SBX-001\n- 任务：TASK-SBX-001\n- 验证：TEST-SBX-001\n",
        encoding="utf-8",
    )
    (path / "docs/design").mkdir(parents=True, exist_ok=True)
    (path / "docs/design/DES-SBX-001.md").write_text("# DES-SBX-001\n", encoding="utf-8")
    (path / "tasks").mkdir(parents=True, exist_ok=True)
    (path / "tasks/TASK-SBX-001.md").write_text(
        "# TASK-SBX-001\n\n允许范围：src/items/\n", encoding="utf-8"
    )
    (path / "tests/spec").mkdir(parents=True, exist_ok=True)
    (path / "tests/spec/TEST-SBX-001.md").write_text("# TEST-SBX-001\n", encoding="utf-8")
    (path / "src/items").mkdir(parents=True, exist_ok=True)
    (path / "src/auth").mkdir(parents=True, exist_ok=True)
    (path / "src/items/items.py").write_text("ITEMS = []\n", encoding="utf-8")
    (path / "src/auth/auth.py").write_text("AUTH = True\n", encoding="utf-8")
    (path / "state.yaml").write_text(
        'system: "ANCHOR"\nsystem_version: "1.0"\nphase: "design"\nstatus: "in-progress"\nactive_item: "TASK-SBX-001"\nnext_action: "complete verification design"\n',
        encoding="utf-8",
    )
    (path / "events.jsonl").write_text(
        '{"time":"2026-09-13","type":"state_snapshot","phase":"design","status":"in-progress","item":"TASK-SBX-001"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "ANCHOR Sandbox"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "anchor-sandbox@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "sandbox baseline"], cwd=path, check=True)


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "scripts/anchor-validate.py"],
        cwd=path,
        capture_output=True,
        text=True,
    )


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"fixture text not found in {path}: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def expect(name: str, passed: bool, detail: str) -> None:
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}: {detail}")
    if not passed:
        raise AssertionError(name)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="anchor-sandbox-") as directory:
        sandbox = Path(directory)
        make_sandbox(sandbox)

        result = run_validator(sandbox)
        expect("baseline structure", result.returncode == 0, result.stdout.strip())

        replace(sandbox / "state.yaml", 'next_action: "complete verification design"', "next_action:")
        result = run_validator(sandbox)
        expect("missing next action rejected", result.returncode != 0, result.stderr.strip())

        make_sandbox(sandbox)
        with (sandbox / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write('{"time":"2026-09-13","type":\n')
        result = run_validator(sandbox)
        expect("malformed audit event rejected", result.returncode != 0, result.stderr.strip())

        make_sandbox(sandbox)
        evidence = sandbox / "evidence/EVID-SBX-001.md"
        baseline_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=sandbox, text=True
        ).strip()
        evidence.write_text(
            f"# EVID-SBX-001\n\nstatus: passed\nverified_commit: {baseline_commit}\n"
            "target_files: src/items/, tests/items/\n",
            encoding="utf-8",
        )
        result = run_validator(sandbox)
        expect("current evidence accepted", result.returncode == 0, (result.stdout + result.stderr).strip())

        replace(evidence, f"verified_commit: {baseline_commit}", "verified_commit: " + "0" * 40)
        result = run_validator(sandbox)
        expect("stale evidence rejected", result.returncode != 0, result.stderr.strip())

        make_sandbox(sandbox)
        evidence = sandbox / "evidence/EVID-SBX-001.md"
        baseline_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=sandbox, text=True
        ).strip()
        evidence.write_text(
            f"# EVID-SBX-001\n\nstatus: passed\nverified_commit: {baseline_commit}\n"
            "target_files: src/items/, tests/items/\n",
            encoding="utf-8",
        )
        (sandbox / "src/items/items.py").write_text("ITEMS = [\"changed\"]\n", encoding="utf-8")
        result = run_validator(sandbox)
        expect("changed verified target rejected", result.returncode != 0, result.stderr.strip())

        make_sandbox(sandbox)
        replace(sandbox / "state.yaml", 'phase: "design"', 'phase: "verify"')
        result = run_validator(sandbox)
        expect("state/audit conflict rejected", result.returncode != 0, result.stderr.strip())

        make_sandbox(sandbox)
        replace(sandbox / "requirements/REQ-SBX-001.md", "- 设计：DES-SBX-001", "- 设计：MISSING-DESIGN")
        result = run_validator(sandbox)
        expect(
            "traceability broken link rejected",
            result.returncode != 0,
            result.stderr.strip(),
        )

        make_sandbox(sandbox)
        (sandbox / "src/auth/auth.py").write_text(
            "# unauthorized sandbox modification\n", encoding="utf-8"
        )
        result = run_validator(sandbox)
        expect(
            "scope boundary violation rejected",
            result.returncode != 0,
            result.stderr.strip(),
        )

    print("ANCHOR sandbox tests: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
