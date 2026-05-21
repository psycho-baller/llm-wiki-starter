# Frontmatter Schema

## Raw Source Notes

Raw source notes live in `Raw/Sources/` and preserve source context.

Required fields:

```yaml
---
title: ""
author: ""
url: ""
source_type: youtube
created: YYYY-MM-DD
processed: false
decision: pending
published: YYYY-MM-DD
relevance_score:
actionability_score:
novelty_score:
credibility_score:
density_score:
personal_resonance_score:
redundancy_risk:
time_cost:
clickbait_risk:
combined_score:
triage_reason:
expected_gain:
tags:
  - source
---
```

`processed` means the source is represented by at least one compiled Wiki note and appears in `Schema/source-manifest.jsonl` with non-empty `covered_by`.

`decision` is the source filtering state. Allowed values are `pending`, `skip`, `watch`, `skim`, `process`, and `later`.

Use `source_type` for the source format or channel, such as `youtube`, `article`, `book`, `podcast`, `journal`, `conversation`, or `markdown`.

Score fields are blank while `decision: pending`. Once a source has been triaged, scores should be filled in so Obsidian Bases can display and sort them.

Score fields use these ranges:

- `relevance_score`, `actionability_score`, `novelty_score`, `credibility_score`, `density_score`, and `personal_resonance_score`: `1` to `5`
- `redundancy_risk`, `time_cost`, and `clickbait_risk`: `low`, `medium`, or `high`
- `combined_score`: `0` to `100`
- `triage_reason` and `expected_gain`: short Bases-friendly text

## Compiled Wiki Notes

Compiled notes live under `Wiki/Topics/`, `Wiki/Concepts/`, `Wiki/Entities/`, `Wiki/Projects/`, or `Wiki/Logs/`.

Required fields:

```yaml
---
tags:
  - "concept"
topics: []
status: seed
origin: external
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

`origin` must be `external`, `personal`, or `mixed`.

Compiled note `origin` is deterministic. It is derived from the `source_type` values of cited Raw sources:

- `youtube`, `article`, `book`, `podcast`, and `markdown` imply `external`
- `journal` and `conversation` imply `personal`
- mixed cited source origins imply `mixed`
