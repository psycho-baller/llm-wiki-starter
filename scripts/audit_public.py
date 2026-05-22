#!/usr/bin/env python3
"""Fail on obvious private or machine-local content before sharing."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".obsidian", "__pycache__"}
IGNORED_NAMES = {".DS_Store", ".env", ".env.local"}
IGNORED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".sqlite", ".db"}
PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic secret assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("machine-local user path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("ssh key path", re.compile(r"\.ssh/(?:id_|config|known_hosts)")),
    ("obsidian plugin/cache state", re.compile(r"\.obsidian/(?:plugins|cache|logs|workspace)")),
]
STARTER_CONTENT_ALLOWLIST = {
    "Raw/Files/.gitkeep",
    "Raw/Sources/YouTube/how to outlearn everyone.md",
    "Raw/Sources/llm-wiki-starter-demo-source.md",
    "Wiki/Concepts/.gitkeep",
    "Wiki/Concepts/index.md",
    "Wiki/Concepts/raw-vs-compiled-knowledge.md",
    "Wiki/Entities/.gitkeep",
    "Wiki/Entities/index.md",
    "Wiki/Logs/.gitkeep",
    "Wiki/Logs/index.md",
    "Wiki/Logs/initial-demo-ingest.md",
    "Wiki/Projects/.gitkeep",
    "Wiki/Projects/build-core-llm-wiki.md",
    "Wiki/Projects/index.md",
    "Wiki/Topics/.gitkeep",
    "Wiki/Topics/index.md",
    "Wiki/Topics/llm-wiki-workflow.md",
    "Wiki/catalog.jsonl",
    "Wiki/index.md",
}


def should_skip(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if path.name in IGNORED_NAMES:
        return True
    if relative.as_posix() == ".gitignore":
        return True
    if any(part in IGNORED_PARTS for part in relative.parts):
        return True
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return True
    return False


def main() -> int:
    findings: list[str] = []
    tracked_content = subprocess.check_output(
        ["git", "ls-files", "Raw", "Wiki"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    for path in tracked_content:
        if path not in STARTER_CONTENT_ALLOWLIST:
            findings.append(
                f"{path}: tracked Raw/Wiki content is not in the public starter allowlist"
            )
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"binary or non-utf8 file should be reviewed: {path.relative_to(ROOT).as_posix()}")
            continue
        for label, pattern in PATTERNS:
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT).as_posix()}: matched {label}")
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}", file=sys.stderr)
        return 1
    print("public audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
