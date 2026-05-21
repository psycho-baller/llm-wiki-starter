# Lint Checklist

Before committing Wiki changes:

- Compiled notes live only under `Wiki/`.
- Raw source notes live only under `Raw/Sources/`.
- Compiled notes use exactly one allowed tag: `topic`, `concept`, `entity`, `project`, or `log`.
- Compiled notes include `origin` as `external`, `personal`, or `mixed`.
- Compiled note `origin` matches the origin derived from cited Raw source `source_type` values.
- Compiled note `sources` point to existing files under `Raw/Sources/`.
- Compiled note `source_count` equals the number of `sources`.
- Raw source notes include `title`, `author`, `url`, `source_type`, `created`, `processed`, `decision`, and `tags`.
- Sources marked `processed: true` have at least one covering Wiki note.
- Triaged Raw sources use `decision: skip`, `watch`, `skim`, `process`, or `later`.
- Triaged Raw sources include score fields, `combined_score`, `triage_reason`, and `expected_gain`.
- Source and Wiki metadata keys use lowercase snake_case.
- Generated indexes and `Wiki/catalog.jsonl` are rebuilt.
- `Schema/source-manifest.jsonl` is updated after source ingestion.
- `scripts/audit_public.py` passes before public sharing.
