# Command Reference

Run commands from the vault root.

## Health

```bash
python3 scripts/wiki_tool.py doctor
```

Checks required folders, Python version, generated catalog/manifest presence, and basic note counts.

## Build

```bash
python3 scripts/wiki_tool.py build
```

Generates `Wiki/catalog.jsonl`, `Wiki/index.md`, and per-folder `index.md` files.

## Lint

```bash
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
```

Validates compiled Wiki frontmatter, allowed tags, `origin`, source links, `source_count`, snake_case source frontmatter, source decisions, triage scores, and processed-source coverage.

## Sources

```bash
python3 scripts/wiki_tool.py source-scan
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-delta
python3 scripts/wiki_tool.py source-coverage
```

Lists Raw sources, updates `Schema/source-manifest.jsonl`, shows manifest deltas, and reports which Wiki notes cover each source.

## Search

```bash
python3 scripts/wiki_tool.py search-catalog --query "text"
```

Searches compiled Wiki notes through `Wiki/catalog.jsonl`.

## Log

```bash
python3 scripts/wiki_tool.py log --title "title" --details "details"
```

Appends a short entry to `Wiki/log.md`.

## Public Audit

```bash
python3 scripts/audit_public.py
```

Fails on obvious secrets, machine-local paths, private keys, and plugin/cache state.
