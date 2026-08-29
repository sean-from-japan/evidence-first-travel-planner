#!/usr/bin/env python3
"""Fail on likely private data or secrets in files and Git blobs."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Tuple

PATTERNS = {
    "email": re.compile(rb"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
    "absolute-local-path": re.compile(rb"/(?:Users|home)/[^\s'\"]+"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "api-key-assignment": re.compile(
        rb"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{8,}"
    ),
    "card-like-number": re.compile(rb"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    "booking-reference": re.compile(
        rb"(?i)(?:booking|reservation|confirmation)[_-]?(?:id|ref|number)"
        rb"\s*[:=]\s*['\"][A-Z0-9]{6,}['\"]"
    ),
    "student-number": re.compile(
        rb"(?i)(?:student|matriculation)[_-]?(?:id|number)"
        rb"\s*[:=]\s*['\"][A-Z0-9]{6,}['\"]"
    ),
}

TEXT_SUFFIXES = {
    ".py",
    ".toml",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".gitignore",
    ".editorconfig",
}
EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "__pycache__",
}


def tracked_files(root: Path) -> Iterator[Tuple[str, bytes]]:
    if (root / ".git").exists():
        output = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        for raw_path in sorted(output.split(b"\0")):
            if not raw_path:
                continue
            relative = Path(raw_path.decode("utf-8"))
            if not (root / relative).is_file():
                continue
            if (
                relative.suffix.lower() in TEXT_SUFFIXES
                or relative.name in TEXT_SUFFIXES
            ):
                yield str(relative), (root / relative).read_bytes()
        return
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        ignored = any(
            part in EXCLUDED_DIRS or part.endswith(".egg-info")
            for part in relative.parts
        )
        if not path.is_file() or ignored:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_SUFFIXES:
            yield str(path.relative_to(root)), path.read_bytes()


def history_blobs(root: Path) -> Iterator[Tuple[str, bytes]]:
    objects = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    seen = set()
    for line in objects:
        parts = line.split(" ", 1)
        if len(parts) != 2 or parts[0] in seen:
            continue
        seen.add(parts[0])
        path = parts[1]
        if (
            Path(path).suffix.lower() not in TEXT_SUFFIXES
            and Path(path).name not in TEXT_SUFFIXES
        ):
            continue
        data = subprocess.run(
            ["git", "cat-file", "blob", parts[0]],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
        yield f"git:{parts[0][:12]}:{path}", data


def scan(items: Iterable[Tuple[str, bytes]]) -> int:
    findings = []
    for label, data in items:
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append((label, name))
    for label, name in findings:
        print(f"FAIL {name}: {label}")
    return len(findings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--git-history", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    findings = scan(tracked_files(root))
    if args.git_history:
        findings += scan(history_blobs(root))
    print(f"audit findings: {findings}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
