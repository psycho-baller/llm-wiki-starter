# YouTube Triage Raycast Extension

This local Raycast extension runs the same pending YouTube workflow as:

```bash
scripts/auto_youtube_triage.sh
```

The command is `Process Pending YouTube Videos`. It lists the pending queue, starts the Bash workflow, streams visible output, and shows the final runtime log tail.

Install dependencies from this folder:

```bash
npm install
```

Run during development:

```bash
npm run dev
```

Build for Raycast:

```bash
npm run build
```

The extension preferences map to the existing Bash script environment knobs:

- `YOUTUBE_TRIAGE_PROVIDER`
- `YOUTUBE_TRIAGE_MODEL`
- `YOUTUBE_TRIAGE_LIMIT`
- `YOUTUBE_TRIAGE_TIMEOUT`
- `YOUTUBE_TRIAGE_MAX_BODY_CHARS`
- `YOUTUBE_TRIAGE_SETTLE_SECONDS`
- `YOUTUBE_TRIAGE_DRY_RUN`
- `YOUTUBE_TRIAGE_NO_BUILD`
