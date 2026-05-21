# LLM Wiki Query

Use this skill when answering questions from the compiled Wiki.

## Workflow

1. Open `Wiki/index.md`.
2. Search the catalog:

```bash
python3 scripts/wiki_tool.py search-catalog --query "user question"
```

3. Read relevant compiled Wiki notes.
4. Open Raw sources only when the compiled note lacks enough detail or the user requests source-level verification.
5. Cite compiled Wiki note paths and Raw source paths for source-backed answers.

Prefer compiled notes over broad Raw source reading.

Use Raw source `source_type` and deterministic compiled note `origin` metadata to distinguish personal notes, external media, articles, videos, and mixed-source compiled notes.
