# Frontmatter Schema

## Raw Source Notes

Raw source notes live in `Raw/Sources/` and preserve source context.

Required fields:

```yaml
---
Title: ""
Author: ""
Reference: ""
ContentType:
  - "markdown"
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"
---
```

`Processed` means the source is represented by at least one compiled Wiki note and appears in `Schema/source-manifest.jsonl` with non-empty `covered_by`.

## Compiled Wiki Notes

Compiled notes live under `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, `Wiki/Projects/`, or `Wiki/Logs/`.

Required fields:

```yaml
---
tags:
  - "concept"
topics: []
status: seed
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
source_count: 0
aliases: []
---
```

Allowed compiled note tags:

- `topic`
- `concept`
- `entity`
- `project`
- `log`

Every item in `sources` must point to an existing file under `Raw/Sources/`. `source_count` must equal the number of entries in `sources`.
