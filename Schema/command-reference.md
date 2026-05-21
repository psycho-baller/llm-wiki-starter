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

## YouTube Triage Schema

`Schema/youtube-triage-schema.json` defines the structured output expected from AI-backed YouTube triage providers such as Codex, Gemini, or Claude. Providers return the individual scores, risks, decision, `triage_reason`, and `expected_gain`; `combined_score` is calculated deterministically by Python.

## YouTube Triage

```bash
python3 scripts/wiki_tool.py youtube-pending
python3 scripts/wiki_tool.py youtube-pending --json
python3 scripts/wiki_tool.py youtube-triage --pending
python3 scripts/wiki_tool.py youtube-triage --pending --provider gemini
python3 scripts/wiki_tool.py youtube-triage Raw/Sources/YouTube/example.md --provider claude --model sonnet
python3 scripts/wiki_tool.py youtube-triage --pending --provider manual
```

`youtube-triage` uses Codex by default. Supported providers are `codex`, `gemini`, `claude`, and `manual`.

The AI provider only returns structured JSON. `scripts/wiki_tool.py` validates the output against `Schema/youtube-triage-schema.json`, calculates `combined_score`, writes the scoring fields into the Raw source frontmatter, updates the `## Triage Notes` body section, rebuilds generated Wiki artifacts, and runs source lint.

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
