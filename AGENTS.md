# LLM Wiki Agent Rules

This vault uses a two-layer LLM Wiki structure: `Raw/` stores source material, and `Wiki/` stores reusable compiled knowledge.

## Core Rules

- Treat `Raw/Sources/` as source material, not as compiled notes.
- Write reusable knowledge only under `Wiki/`.
- Keep every compiled Wiki note linked to one or more Raw sources through its `sources` frontmatter.
- Search `Wiki/catalog.jsonl` before opening broad Raw context.
- Run `python3 scripts/wiki_tool.py build`, `python3 scripts/wiki_tool.py lint`, and `python3 scripts/wiki_tool.py source-lint` before commits.
- Do not invent citations or create unsupported claims.
- Prefer short, focused notes over long copied source summaries.
- Open Raw sources only when compiled Wiki notes are insufficient or source-level verification is needed.

## Working Pattern

1. Search the compiled Wiki first with `python3 scripts/wiki_tool.py search-catalog --query "topic"`.
2. Read the most relevant notes under `Wiki/`.
3. If needed, inspect cited files under `Raw/Sources/`.
4. Create or update focused notes under `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, `Wiki/Projects/`, or `Wiki/Logs/`.
5. Keep `sources` and `source_count` accurate.
6. Rebuild indexes and run lint/source checks before committing.

## Public Safety

Do not commit private keys, secrets, machine-local paths, plugin caches, Obsidian workspace churn, or binary source files. Run `python3 scripts/audit_public.py` before publishing or sharing the vault.
