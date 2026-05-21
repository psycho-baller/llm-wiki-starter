# Workflow Examples

## Ingest A New Source

1. Add cleaned Markdown to `Raw/Sources/`.
2. Run `python3 scripts/wiki_tool.py search-catalog --query "likely topic"`.
3. Read related compiled Wiki notes before opening broad Raw context.
4. Create or update focused notes under `Wiki/`.
5. Link each compiled note to Raw sources in frontmatter.
6. Set the Raw source `decision` to `process` or `skim` when it has been intentionally compiled.
7. Run `python3 scripts/wiki_tool.py build`.
8. Run `python3 scripts/wiki_tool.py lint`.
9. Run `python3 scripts/wiki_tool.py source-scan --update --accept-covered`.
10. Run `python3 scripts/wiki_tool.py source-lint`.

## Answer A Question

1. Start with `Wiki/index.md`.
2. Search the catalog with `python3 scripts/wiki_tool.py search-catalog --query "user topic"`.
3. Open the most relevant compiled notes.
4. Open Raw sources only if the compiled note is insufficient.
5. Cite both compiled notes and Raw source paths when source material supports the answer.

## Maintenance Gate

Before meaningful commits, run:

```bash
python3 scripts/wiki_tool.py doctor
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/audit_public.py
```
