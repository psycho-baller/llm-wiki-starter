---
tags:
  - "topic"
topics:
  - "llm wiki"
status: seed
origin: external
created: 2026-05-19
updated: 2026-05-20
sources:
  - "Raw/Sources/llm-wiki-starter-demo-source.md"
source_count: 1
aliases:
  - "LLM Wiki"
---

# LLM Wiki Workflow

## Overview

An LLM Wiki workflow separates captured source material from compiled notes so future agents can query concise knowledge before opening broad source context.

## Core Sequence

- Preserve source material in `Raw/Sources/`.
- Compile useful claims into short notes under `Wiki/`.
- Search compiled Wiki notes first.
- Open Raw sources only when more evidence or detail is needed.

## Related Notes

- [[raw-vs-compiled-knowledge]]
- [[build-core-llm-wiki]]
