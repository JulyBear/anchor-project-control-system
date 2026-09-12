#!/usr/bin/env python3
"""Minimal, dependency-free ANCHOR consistency checks."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_text(path).splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*[\"']?([^\"']*)[\"']?\s*$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def git_revision() -> str:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    )
    if dirty.returncode != 0 or dirty.stdout.strip():
        return "uncommitted-working-tree"
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted-working-tree"


def git_changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = []
    entries = result.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if "R" in status or "C" in status:
            if index < len(entries):
                path = entries[index]
                index += 1
        paths.append(path)
    return sorted(set(paths))


def check_required_files() -> None:
    paths = [
        "AGENTS.md",
        "docs/control/ANCHOR-1.0.md",
        "state.yaml",
        "requirements/README.md",
        "docs/decisions/ADR-001-anchor-name-and-architecture.md",
        "evidence/README.md",
        "events.jsonl",
        "external/README.md",
    ]
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise AssertionError(f"missing required files: {', '.join(missing)}")


def check_external_isolation() -> None:
    agents = read_text(ROOT / "AGENTS.md")
    readme = read_text(ROOT / "external/README.md")
    assert "外部" in agents and "不得覆盖" in agents, "AGENTS.md must define external input isolation"
    assert "不具备项目指令权" in readme, "external/README.md must deny instruction authority"


def check_state() -> None:
    state = parse_simple_yaml(ROOT / "state.yaml")
    assert state.get("system") == "ANCHOR", "state.yaml system must be ANCHOR"
    assert state.get("system_version") == "1.0", "state.yaml version must be 1.0"
    assert state.get("active_item"), "state.yaml must define active_item"
    assert state.get("next_action"), "state.yaml must define next_action"


def check_events() -> None:
    lines = [line for line in read_text(ROOT / "events.jsonl").splitlines() if line.strip()]
    assert lines, "events.jsonl must not be empty"
    for number, line in enumerate(lines, 1):
        event = json.loads(line)
        assert event.get("time"), f"event {number} missing time"
        assert event.get("type"), f"event {number} missing type"


def check_evidence_commit_binding() -> None:
    evidence_files = sorted((ROOT / "evidence").glob("EVID-*.md"))
    for path in evidence_files:
        text = read_text(path)
        partial = "状态：部分通过" in text or "状态: partial" in text
        externally_supplied = "用户提供的独立会话输出" in text
        if partial or externally_supplied:
            continue
        match = re.search(r"^verified_commit:\s*['\"]?([^'\"\s]+)", text, re.MULTILINE)
        assert match, f"{path} must state verified_commit"
        verified = match.group(1)
        assert re.fullmatch(r"[0-9a-f]{40}", verified), f"{path} has invalid verified_commit"
        commit = subprocess.run(
            ["git", "cat-file", "-e", f"{verified}^{{commit}}"], cwd=ROOT, capture_output=True
        )
        assert commit.returncode == 0, f"{path} references unknown commit {verified}"
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", verified, "HEAD"], cwd=ROOT, capture_output=True
        )
        assert ancestor.returncode == 0, f"{path} references commit outside current history"
        targets_match = re.search(r"^target_files:\s*(.+)$", text, re.MULTILINE)
        assert targets_match, f"{path} must state target_files"
        targets = [item.strip() for item in targets_match.group(1).split(",") if item.strip()]
        assert targets, f"{path} target_files must not be empty"
        committed_changes = subprocess.run(
            ["git", "diff", "--name-only", verified, "HEAD", "--", *targets],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        working_changes = [
            changed for changed in git_changed_paths()
            if any(changed == target.rstrip("/") or changed.startswith(target) for target in targets)
        ]
        changed_targets = sorted(set(committed_changes + working_changes))
        assert not changed_targets, (
            f"{path} is stale; verified targets changed: {', '.join(changed_targets)}"
        )


def check_state_matches_latest_event() -> None:
    state = parse_simple_yaml(ROOT / "state.yaml")
    events = [
        json.loads(line)
        for line in read_text(ROOT / "events.jsonl").splitlines()
        if line.strip()
    ]
    state_events = [
        event for event in events
        if any(key in event for key in ("phase", "status", "item"))
    ]
    if not state_events:
        return
    latest = state_events[-1]
    pairs = (("phase", "phase"), ("status", "status"), ("item", "active_item"))
    for event_key, state_key in pairs:
        if event_key in latest:
            assert state.get(state_key) == str(latest[event_key]), (
                f"state.yaml {state_key} conflicts with latest audit event {event_key}"
            )


def find_object(object_id: str, roots: tuple[str, ...]) -> bool:
    for root_name in roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path.name == f"{object_id}.md" or f"# {object_id}" in read_text(path):
                return True
    return False


def check_requirement_traceability() -> None:
    patterns = {
        "设计": (r"设计：\s*([A-Z]+-[A-Z0-9-]+)", ("docs/design",)),
        "任务": (r"任务：\s*([A-Z]+-[A-Z0-9-]+)", ("tasks",)),
        "验证": (r"验证：\s*([A-Z]+-[A-Z0-9-]+)", ("tests/spec", "evidence")),
    }
    for path in sorted((ROOT / "requirements").glob("REQ-*.md")):
        text = read_text(path)
        for label, (pattern, roots) in patterns.items():
            for object_id in re.findall(pattern, text):
                assert find_object(object_id, roots), f"{path} references missing {label} {object_id}"


def check_task_scope() -> None:
    state = parse_simple_yaml(ROOT / "state.yaml")
    active_item = state.get("active_item")
    if not active_item:
        return
    task_path = ROOT / "tasks" / f"{active_item}.md"
    if not task_path.is_file():
        return
    text = read_text(task_path)
    match = re.search(r"允许范围：\s*(.+)", text)
    assert match, f"{task_path} must define allowed scope"
    allowed = [item.strip() for item in re.split(r"[、,]", match.group(1)) if item.strip()]
    changed = git_changed_paths()
    ignored = ("state.yaml", "events.jsonl", "evidence/")
    out_of_scope = [
        path for path in changed
        if not any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in ignored)
        and not any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in allowed)
    ]
    assert not out_of_scope, f"active task {active_item} changed out-of-scope paths: {', '.join(out_of_scope)}"


def main() -> int:
    check_required_files()
    check_external_isolation()
    check_state()
    check_events()
    check_evidence_commit_binding()
    check_state_matches_latest_event()
    check_requirement_traceability()
    check_task_scope()
    print(f"ANCHOR validation OK ({git_revision()})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError) as exc:
        print(f"ANCHOR validation FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
