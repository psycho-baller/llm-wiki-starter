# Lint Checklist

Before committing Wiki changes:

- Compiled notes live only under `Wiki/`.
- Raw source notes live only under `Raw/Sources/`.
- Compiled notes use exactly one allowed tag: `topic`, `concept`, `entity`, `project`, or `log`.
- Compiled note `sources` point to existing files under `Raw/Sources/`.
- Compiled note `source_count` equals the number of `sources`.
- Raw source notes include `Title`, `Reference`, `Created`, `Processed`, and `tags`.
- Sources marked `Processed: true` have at least one covering Wiki note.
- Generated indexes and `Wiki/catalog.jsonl` are rebuilt.
- `Schema/source-manifest.jsonl` is updated after source ingestion.
- `scripts/audit_public.py` passes before public sharing.
