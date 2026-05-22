/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Vault Path - Absolute path to the knowledge-base vault. */
  "vaultPath": string,
  /** Triage Provider - AI provider passed to scripts/wiki_tool.py youtube-triage. */
  "provider": "codex" | "gemini" | "claude" | "manual",
  /** Model Override - Optional provider model override. */
  "model"?: string,
  /** Limit - Maximum pending videos to process in one run. */
  "limit": string,
  /** Timeout Seconds - Provider timeout in seconds for each triage call. */
  "timeout": string,
  /** Settle Seconds - Seconds to wait after pending files are found before processing. */
  "settleSeconds": string,
  /** Max Body Characters - Optional cap for source body characters sent to the provider. */
  "maxBodyChars"?: string,
  /** Dry Run - Print provider results without editing source files. */
  "dryRun": boolean,
  /** Skip Rebuild - Skip catalog/source manifest rebuild after updates. */
  "noBuild": boolean
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `process-pending` command */
  export type ProcessPending = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `process-pending` command */
  export type ProcessPending = {}
}

