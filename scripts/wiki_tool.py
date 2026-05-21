#!/usr/bin/env python3
"""Deterministic maintenance tool for the core LLM Wiki."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from youtube_triage import ProviderConfig, TriageError, triage_source


ROOT = Path(__file__).resolve().parents[1]
RAW_SOURCES = ROOT / "Raw" / "Sources"
WIKI = ROOT / "Wiki"
SCHEMA = ROOT / "Schema"
CATALOG = WIKI / "catalog.jsonl"
MANIFEST = SCHEMA / "source-manifest.jsonl"
YOUTUBE_TRIAGE_SCHEMA = SCHEMA / "youtube-triage-schema.json"
ALLOWED_TAGS = {"topic", "concept", "entity", "project", "log"}
ALLOWED_ORIGINS = {"external", "personal", "mixed"}
SOURCE_TYPE_ORIGINS = {
    "youtube": "external",
    "article": "external",
    "book": "external",
    "podcast": "external",
    "markdown": "external",
    "journal": "personal",
    "conversation": "personal",
}
ALLOWED_DECISIONS = {"pending", "skip", "watch", "skim", "process", "later"}
RISK_LEVELS = {"low", "medium", "high"}
SCORE_FIELDS = (
    "relevance_score",
    "actionability_score",
    "novelty_score",
    "credibility_score",
    "density_score",
    "personal_resonance_score",
)
RISK_FIELDS = ("redundancy_risk", "time_cost", "clickbait_risk")
TRIAGE_FIELDS = (
    *SCORE_FIELDS,
    *RISK_FIELDS,
    "combined_score",
    "triage_reason",
    "expected_gain",
)
LEGACY_SOURCE_KEYS = {
    "Title",
    "Author",
    "Reference",
    "ContentType",
    "Created",
    "Processed",
    "Ignored",
    "TriageStatus",
    "Decision",
    "SourceType",
}
WIKI_FOLDERS = {
    "Topics": "topic",
    "Concepts": "concept",
    "Entities": "entity",
    "Projects": "project",
    "Logs": "log",
}
REQUIRED_FOLDERS = [
    RAW_SOURCES,
    ROOT / "Raw" / "Files",
    WIKI / "Topics",
    WIKI / "Concepts",
    WIKI / "Entities",
    WIKI / "Projects",
    WIKI / "Logs",
    SCHEMA,
    ROOT / "_templates",
    ROOT / ".agents" / "skills",
    ROOT / "scripts",
    ROOT / "tutorial",
]


class WikiError(Exception):
    """Raised for expected validation failures."""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def today() -> str:
    return date.today().isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        path
        for path in folder.rglob("*.md")
        if path.is_file() and path.name != ".gitkeep"
    )


def compiled_note_files() -> list[Path]:
    notes: list[Path] = []
    for folder in WIKI_FOLDERS:
        base = WIKI / folder
        notes.extend(
            path
            for path in markdown_files(base)
            if path.name != "index.md"
        )
    return sorted(notes)


def source_files() -> list[Path]:
    return markdown_files(RAW_SOURCES)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            current = data.setdefault(current_key, [])
            if not isinstance(current, list):
                current = []
                data[current_key] = current
            current.append(parse_scalar(line[4:]))
            continue
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = [] if value == "" else parse_scalar(value)
    return data, body


def first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def note_title(path: Path, frontmatter: dict[str, Any], body: str) -> str:
    value = frontmatter.get("title")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return first_heading(body, path.stem.replace("-", " ").title())


def note_summary(body: str, max_chars: int = 420) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if sum(len(item) for item in lines) >= max_chars:
            break
    text = " ".join(lines)
    return text[:max_chars].strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def has_value(value: Any) -> bool:
    return value not in (None, "", [])


def int_value(value: Any) -> int | None:
    if not has_value(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compiled_tag(frontmatter: dict[str, Any]) -> str | None:
    tags = [str(tag) for tag in as_list(frontmatter.get("tags"))]
    allowed = [tag for tag in tags if tag in ALLOWED_TAGS]
    if len(allowed) == 1:
        return allowed[0]
    return None


def source_type_for_path(source: str) -> str:
    source_path = ROOT / source
    if not source_path.exists():
        return ""
    fm, _body = parse_frontmatter(read_text(source_path))
    return str(fm.get("source_type", ""))


def origin_for_source_type(source_type: str) -> str | None:
    return SOURCE_TYPE_ORIGINS.get(source_type)


def derived_origin_for_sources(sources: list[str]) -> str | None:
    origins = set()
    for source in sources:
        source_type = source_type_for_path(source)
        origin = origin_for_source_type(source_type)
        if origin is None:
            return None
        origins.add(origin)
    if not origins:
        return None
    if len(origins) == 1:
        return origins.pop()
    return "mixed"


def catalog_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in compiled_note_files():
        fm, body = parse_frontmatter(read_text(path))
        tag = compiled_tag(fm) or ""
        sources = [str(item) for item in as_list(fm.get("sources"))]
        entries.append(
            {
                "path": rel(path),
                "title": note_title(path, fm, body),
                "tag": tag,
                "origin": derived_origin_for_sources(sources) or str(fm.get("origin", "")),
                "topics": [str(item) for item in as_list(fm.get("topics"))],
                "sources": sources,
                "updated": str(fm.get("updated", "")),
                "aliases": [str(item) for item in as_list(fm.get("aliases"))],
                "summary": note_summary(body),
            }
        )
    return sorted(entries, key=lambda item: item["path"])


def source_coverage_map() -> dict[str, list[str]]:
    coverage: dict[str, list[str]] = {}
    for entry in catalog_entries():
        for source in entry.get("sources", []):
            coverage.setdefault(str(source), []).append(str(entry["path"]))
    return {key: sorted(set(value)) for key, value in sorted(coverage.items())}


def source_entries(accept_covered: bool = False) -> list[dict[str, Any]]:
    coverage = source_coverage_map()
    entries: list[dict[str, Any]] = []
    for path in source_files():
        fm, body = parse_frontmatter(read_text(path))
        source_path = rel(path)
        covered_by = coverage.get(source_path, [])
        processed = bool(fm.get("processed", False))
        if accept_covered and covered_by:
            processed = True
        entries.append(
            {
                "path": source_path,
                "title": note_title(path, fm, body),
                "source_type": str(fm.get("source_type", "")),
                "decision": str(fm.get("decision", "pending")),
                "processed": processed,
                **{field: int_value(fm.get(field)) for field in SCORE_FIELDS},
                **{field: str(fm.get(field, "")) if has_value(fm.get(field)) else "" for field in RISK_FIELDS},
                "combined_score": int_value(fm.get("combined_score")),
                "triage_reason": str(fm.get("triage_reason", "")) if has_value(fm.get("triage_reason")) else "",
                "expected_gain": str(fm.get("expected_gain", "")) if has_value(fm.get("expected_gain")) else "",
                "covered_by": covered_by,
                "updated": today(),
            }
        )
    return entries


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    write_text(path, text)


def render_index(title: str, entries: list[dict[str, Any]]) -> str:
    lines = [
        f"# {title}",
        "",
        f"Generated: {today()}",
        "",
    ]
    if not entries:
        lines.extend(["No compiled Wiki notes yet.", ""])
        return "\n".join(lines)
    for entry in entries:
        path = entry["path"]
        lines.append(f"- [{entry['title']}]({Path(path).name if title != 'Wiki Index' else path}) - `{entry['tag']}`")
    lines.append("")
    return "\n".join(lines)


def cmd_build(_args: argparse.Namespace) -> int:
    entries = catalog_entries()
    write_jsonl(CATALOG, entries)
    write_text(WIKI / "index.md", render_index("Wiki Index", entries))
    for folder, expected_tag in WIKI_FOLDERS.items():
        folder_entries = [entry for entry in entries if entry["path"].startswith(f"Wiki/{folder}/")]
        write_text(WIKI / folder / "index.md", render_index(f"{folder} Index", folder_entries))
    print(f"built catalog with {len(entries)} compiled notes")
    return 0


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_compiled_note(path: Path) -> list[str]:
    errors: list[str] = []
    fm, _body = parse_frontmatter(read_text(path))
    require(bool(fm), f"{rel(path)} missing frontmatter", errors)
    for key in LEGACY_SOURCE_KEYS:
        require(key not in fm, f"{rel(path)} uses legacy non-snake-case key `{key}`", errors)
    tags = [str(tag) for tag in as_list(fm.get("tags"))]
    allowed = [tag for tag in tags if tag in ALLOWED_TAGS]
    require(len(allowed) == 1, f"{rel(path)} must use exactly one allowed compiled tag", errors)
    folder_name = path.parent.name
    expected_tag = WIKI_FOLDERS.get(folder_name)
    if expected_tag and allowed:
        require(allowed[0] == expected_tag, f"{rel(path)} tag `{allowed[0]}` does not match folder `{folder_name}`", errors)
    sources = [str(source) for source in as_list(fm.get("sources"))]
    require("source_count" in fm, f"{rel(path)} missing source_count", errors)
    require(int(fm.get("source_count", -1)) == len(sources), f"{rel(path)} source_count does not match sources", errors)
    require(bool(sources), f"{rel(path)} must cite at least one Raw source", errors)
    for source in sources:
        source_path = ROOT / source
        require(source.startswith("Raw/Sources/"), f"{rel(path)} source `{source}` must be under Raw/Sources/", errors)
        require(source_path.exists(), f"{rel(path)} source `{source}` does not exist", errors)
    for key in ("topics", "status", "origin", "created", "updated", "aliases"):
        require(key in fm, f"{rel(path)} missing `{key}`", errors)
    if "origin" in fm:
        require(str(fm.get("origin")) in ALLOWED_ORIGINS, f"{rel(path)} origin must be one of {sorted(ALLOWED_ORIGINS)}", errors)
    derived_origin = derived_origin_for_sources(sources)
    require(derived_origin is not None, f"{rel(path)} origin could not be derived from source_type values", errors)
    if derived_origin is not None and "origin" in fm:
        require(str(fm.get("origin")) == derived_origin, f"{rel(path)} origin `{fm.get('origin')}` should be `{derived_origin}` based on cited Raw source_type values", errors)
    return errors


def cmd_lint(_args: argparse.Namespace) -> int:
    errors: list[str] = []
    for path in compiled_note_files():
        errors.extend(validate_compiled_note(path))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"lint passed for {len(compiled_note_files())} compiled notes")
    return 0


def validate_source(path: Path, manifest_by_path: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    fm, _body = parse_frontmatter(read_text(path))
    source_path = rel(path)
    require(bool(fm), f"{source_path} missing frontmatter", errors)
    for key in LEGACY_SOURCE_KEYS:
        require(key not in fm, f"{source_path} uses legacy non-snake-case key `{key}`", errors)
    for key in ("title", "author", "url", "source_type", "created", "processed", "decision", "tags"):
        require(key in fm, f"{source_path} missing `{key}`", errors)
    tags = [str(tag) for tag in as_list(fm.get("tags"))]
    require("source" in tags, f"{source_path} tags must include `source`", errors)
    if "decision" in fm:
        require(str(fm.get("decision")) in ALLOWED_DECISIONS, f"{source_path} decision must be one of {sorted(ALLOWED_DECISIONS)}", errors)
    source_processed = bool(fm.get("processed", False))
    manifest_entry = manifest_by_path.get(source_path, {})
    covered_by = as_list(manifest_entry.get("covered_by"))
    manifest_processed = bool(manifest_entry.get("processed", False))
    if source_processed:
        require(bool(covered_by), f"{source_path} is processed but has no Wiki coverage", errors)
    if manifest_processed:
        require(bool(covered_by), f"{source_path} manifest is processed but has no Wiki coverage", errors)
    if str(fm.get("decision", "pending")) != "pending":
        for key in TRIAGE_FIELDS:
            require(key in fm, f"{source_path} triaged source missing `{key}`", errors)
    for key in SCORE_FIELDS:
        score = int_value(fm.get(key))
        if score is not None:
            require(1 <= score <= 5, f"{source_path} {key} must be between 1 and 5", errors)
    combined_score = int_value(fm.get("combined_score"))
    if combined_score is not None:
        require(0 <= combined_score <= 100, f"{source_path} combined_score must be between 0 and 100", errors)
    for key in RISK_FIELDS:
        value = fm.get(key)
        if has_value(value):
            require(str(value) in RISK_LEVELS, f"{source_path} {key} must be one of {sorted(RISK_LEVELS)}", errors)
    if "source_type" in fm:
        require(str(fm.get("source_type")) in SOURCE_TYPE_ORIGINS, f"{source_path} source_type must be mapped in SOURCE_TYPE_ORIGINS", errors)
    return errors


def read_manifest() -> list[dict[str, Any]]:
    if not MANIFEST.exists():
        return []
    rows = []
    for line_number, line in enumerate(read_text(MANIFEST).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise WikiError(f"{rel(MANIFEST)} line {line_number} is invalid JSON: {exc}") from exc
    return rows


def cmd_source_scan(args: argparse.Namespace) -> int:
    entries = source_entries(accept_covered=args.accept_covered)
    if args.update:
        write_jsonl(MANIFEST, entries)
        print(f"updated source manifest with {len(entries)} sources")
    else:
        for entry in entries:
            print(json.dumps(entry, sort_keys=True))
    return 0


def cmd_source_lint(_args: argparse.Namespace) -> int:
    errors: list[str] = []
    try:
        manifest = read_manifest()
    except WikiError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    manifest_by_path = {str(row.get("path")): row for row in manifest}
    for path in source_files():
        errors.extend(validate_source(path, manifest_by_path))
    for row in manifest:
        path = str(row.get("path", ""))
        require(path.startswith("Raw/Sources/"), f"manifest path `{path}` must be under Raw/Sources/", errors)
        require((ROOT / path).exists(), f"manifest path `{path}` does not exist", errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"source-lint passed for {len(source_files())} Raw sources")
    return 0


def cmd_source_delta(_args: argparse.Namespace) -> int:
    manifest_paths = {str(row.get("path")) for row in read_manifest()}
    current_paths = {rel(path) for path in source_files()}
    missing = sorted(current_paths - manifest_paths)
    stale = sorted(manifest_paths - current_paths)
    if missing:
        print("Raw sources not represented in manifest:")
        for path in missing:
            print(f"- {path}")
    if stale:
        print("Manifest entries without Raw source files:")
        for path in stale:
            print(f"- {path}")
    if not missing and not stale:
        print("source manifest matches Raw sources")
    return 0 if not stale else 1


def cmd_source_coverage(_args: argparse.Namespace) -> int:
    coverage = source_coverage_map()
    for path in source_files():
        source_path = rel(path)
        covered_by = coverage.get(source_path, [])
        print(json.dumps({"path": source_path, "covered_by": covered_by}, sort_keys=True))
    return 0


def youtube_sources(decision: str | None = None) -> list[Path]:
    matches: list[Path] = []
    for path in source_files():
        fm, _body = parse_frontmatter(read_text(path))
        if str(fm.get("source_type", "")) != "youtube":
            continue
        if decision is not None and str(fm.get("decision", "pending")) != decision:
            continue
        matches.append(path)
    return sorted(matches)


def resolve_source_arg(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise WikiError(f"source path does not exist: {path_text}")
    return path


def cmd_youtube_pending(args: argparse.Namespace) -> int:
    matches = youtube_sources(decision="pending")
    if args.json:
        rows = []
        for path in matches:
            fm, _body = parse_frontmatter(read_text(path))
            rows.append(
                {
                    "path": rel(path),
                    "title": str(fm.get("title", "")),
                    "author": str(fm.get("author", "")),
                    "url": str(fm.get("url", "")),
                    "created": str(fm.get("created", "")),
                }
            )
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    for path in matches:
        print(rel(path))
    if not matches:
        print("no pending YouTube sources")
    return 0


def cmd_youtube_triage(args: argparse.Namespace) -> int:
    try:
        paths = [resolve_source_arg(path) for path in args.paths]
        if args.pending or not paths:
            pending = youtube_sources(decision="pending")
            if args.limit:
                pending = pending[: args.limit]
            paths.extend(path for path in pending if path not in paths)
        if not paths:
            print("no YouTube sources to triage")
            return 0
        config = ProviderConfig(provider=args.provider, model=args.model, timeout=args.timeout)
        for path in paths:
            result = triage_source(
                root=ROOT,
                source_path=path,
                schema_path=YOUTUBE_TRIAGE_SCHEMA,
                config=config,
                dry_run=args.dry_run,
            )
            if args.provider == "manual":
                print(f"--- prompt for {rel(path)} ---")
                print(result["prompt"])
                continue
            if args.dry_run:
                print(json.dumps({"path": rel(path), "result": result}, indent=2, sort_keys=True))
            else:
                print(f"{rel(path)} -> {result['decision']} ({result['combined_score']})")
        if not args.dry_run and args.provider != "manual" and not args.no_build:
            cmd_build(argparse.Namespace())
            cmd_source_scan(argparse.Namespace(update=True, accept_covered=True))
            return cmd_source_lint(argparse.Namespace())
        return 0
    except (TriageError, WikiError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def searchable_text(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("path", "")),
        str(entry.get("title", "")),
        str(entry.get("tag", "")),
        " ".join(str(item) for item in entry.get("topics", [])),
        " ".join(str(item) for item in entry.get("aliases", [])),
        str(entry.get("summary", "")),
    ]
    return " ".join(parts).lower()


def cmd_search_catalog(args: argparse.Namespace) -> int:
    query_terms = [term for term in re.split(r"\W+", args.query.lower()) if term]
    if CATALOG.exists():
        rows = [json.loads(line) for line in read_text(CATALOG).splitlines() if line.strip()]
    else:
        rows = catalog_entries()
    scored = []
    for row in rows:
        haystack = searchable_text(row)
        score = sum(haystack.count(term) for term in query_terms)
        if score:
            scored.append((score, row))
    for score, row in sorted(scored, key=lambda item: (-item[0], item[1]["path"])):
        print(f"{row['path']} | {row['title']} | {row.get('tag', '')} | score={score}")
    if not scored:
        print("no catalog matches")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    log_path = WIKI / "log.md"
    existing = read_text(log_path) if log_path.exists() else "# Wiki Log\n\n"
    entry = f"## {today()} - {args.title}\n\n{args.details}\n\n"
    write_text(log_path, existing.rstrip() + "\n\n" + entry)
    print(f"appended log entry to {rel(log_path)}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    if sys.version_info < (3, 10):
        errors.append("Python 3.10+ is recommended")
    for folder in REQUIRED_FOLDERS:
        if not folder.exists():
            errors.append(f"missing folder {rel(folder)}")
    if not CATALOG.exists():
        warnings.append(f"missing generated catalog {rel(CATALOG)}; run build")
    if not MANIFEST.exists():
        warnings.append(f"missing source manifest {rel(MANIFEST)}; run source-scan --update")
    compiled_count = len(compiled_note_files())
    source_count = len(source_files())
    print(f"python: {sys.version.split()[0]}")
    print(f"raw sources: {source_count}")
    print(f"compiled wiki notes: {compiled_count}")
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("lint").set_defaults(func=cmd_lint)
    scan = sub.add_parser("source-scan")
    scan.add_argument("--update", action="store_true")
    scan.add_argument("--accept-covered", action="store_true")
    scan.set_defaults(func=cmd_source_scan)
    sub.add_parser("source-lint").set_defaults(func=cmd_source_lint)
    sub.add_parser("source-delta").set_defaults(func=cmd_source_delta)
    sub.add_parser("source-coverage").set_defaults(func=cmd_source_coverage)
    pending = sub.add_parser("youtube-pending")
    pending.add_argument("--json", action="store_true", help="Print pending YouTube sources as JSON")
    pending.set_defaults(func=cmd_youtube_pending)
    triage = sub.add_parser("youtube-triage")
    triage.add_argument("paths", nargs="*", help="Specific Raw/Sources YouTube files to triage")
    triage.add_argument("--pending", action="store_true", help="Triage all pending YouTube sources")
    triage.add_argument("--provider", choices=["codex", "gemini", "claude", "manual"], default="codex")
    triage.add_argument("--model", help="Optional provider model override")
    triage.add_argument("--limit", type=int, help="Maximum pending sources to triage")
    triage.add_argument("--timeout", type=int, default=300, help="Provider timeout in seconds")
    triage.add_argument("--dry-run", action="store_true", help="Print provider result without editing files")
    triage.add_argument("--no-build", action="store_true", help="Do not rebuild catalog or source manifest after updates")
    triage.set_defaults(func=cmd_youtube_triage)
    search = sub.add_parser("search-catalog")
    search.add_argument("--query", required=True)
    search.set_defaults(func=cmd_search_catalog)
    log = sub.add_parser("log")
    log.add_argument("--title", required=True)
    log.add_argument("--details", required=True)
    log.set_defaults(func=cmd_log)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
