# LLM Wiki Maintain

Use this skill for routine upkeep of the LLM Wiki.

## Tasks

- Rebuild `Wiki/catalog.jsonl`, `Wiki/index.md`, and folder indexes.
- Validate compiled notes and Raw source coverage.
- Update `Schema/source-manifest.jsonl` after new sources are covered.
- Add short log entries for meaningful changes.
- Keep generated files committed with the notes they describe.
- Keep machine-readable frontmatter keys in lowercase snake_case.
- Keep Raw source `decision` and `processed` fields aligned with source coverage.

## Commands

```bash
python3 scripts/wiki_tool.py doctor
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
```
