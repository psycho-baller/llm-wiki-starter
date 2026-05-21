# LLM Wiki Ingest

Use this skill when adding or compiling new source material into the LLM Wiki.

## Workflow

1. Place cleaned Markdown source notes in `Raw/Sources/`.
2. Search existing compiled notes first:

```bash
python3 scripts/wiki_tool.py search-catalog --query "source topic"
```

3. Read only the most relevant compiled notes.
4. Create or update concise notes under `Wiki/`.
5. Link every compiled note to Raw source paths in `sources`.
6. Keep `source_count` equal to the number of `sources`.
7. Use lowercase snake_case for frontmatter keys.
8. Set Raw source `decision` to match the ingest result.
9. Set compiled note `origin` from cited Raw source `source_type` values: external, personal, or mixed.
10. Rebuild and validate:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
```

Do not invent citations. If a claim cannot be traced to a Raw source, omit it or mark it as an open question outside the compiled Wiki.
