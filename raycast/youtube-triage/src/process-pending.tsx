import {
  Action,
  ActionPanel,
  Detail,
  Icon,
  Toast,
  getPreferenceValues,
  open,
  openExtensionPreferences,
  showToast,
} from "@raycast/api";
import { spawn } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import * as path from "node:path";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Provider = "codex" | "gemini" | "claude" | "manual";

type ExtensionPrefs = {
  vaultPath: string;
  provider: Provider;
  model?: string;
  limit: string;
  timeout: string;
  settleSeconds: string;
  maxBodyChars?: string;
  dryRun: boolean;
  noBuild: boolean;
};

type PendingVideo = {
  path: string;
  title: string;
  author: string;
  url: string;
  created: string;
};

type RunState = "checking" | "running" | "succeeded" | "failed";

const MAX_VISIBLE_LOG_CHARS = 18000;
const DEFAULT_RUNTIME_DIR = ".wiki-runtime/youtube-triage";

export default function ProcessPendingYouTubeVideos() {
  const preferences = getPreferenceValues<ExtensionPrefs>();
  const vaultPath = preferences.vaultPath;
  const logPath = path.join(vaultPath, DEFAULT_RUNTIME_DIR, "run.log");

  const [state, setState] = useState<RunState>("checking");
  const [pending, setPending] = useState<PendingVideo[]>([]);
  const [output, setOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const hasStarted = useRef(false);

  const appendOutput = useCallback((chunk: string) => {
    setOutput((previous) => trimLog(previous + chunk));
  }, []);

  const runWorkflow = useCallback(async () => {
    setState("checking");
    setError(null);
    setOutput("");

    try {
      await assertVault(vaultPath);
      const pendingVideos = await loadPendingVideos(vaultPath);
      setPending(pendingVideos);

      if (pendingVideos.length === 0) {
        setState("succeeded");
        appendOutput("no pending YouTube sources\n");
        await showToast({ style: Toast.Style.Success, title: "No pending YouTube videos" });
        return;
      }

      setState("running");
      appendOutput(formatQueue(pendingVideos));
      await showToast({
        style: Toast.Style.Animated,
        title: "Processing pending YouTube videos",
        message: `${pendingVideos.length} queued`,
      });

      const result = await runScript(vaultPath, preferences, appendOutput);
      const logTail = await readLogTail(logPath);
      if (logTail) {
        appendOutput(`\n\n--- runtime log tail ---\n${logTail}`);
      }

      if (result.exitCode === 0) {
        setState("succeeded");
        await showToast({ style: Toast.Style.Success, title: "YouTube triage completed" });
      } else {
        setState("failed");
        setError(`Script exited with code ${result.exitCode}`);
        await showToast({
          style: Toast.Style.Failure,
          title: "YouTube triage failed",
          message: `Exit code ${result.exitCode}`,
        });
      }
    } catch (runError) {
      const message = runError instanceof Error ? runError.message : String(runError);
      setState("failed");
      setError(message);
      appendOutput(`ERROR: ${message}\n`);
      await showToast({ style: Toast.Style.Failure, title: "YouTube triage failed", message });
    }
  }, [appendOutput, logPath, preferences, vaultPath]);

  useEffect(() => {
    if (hasStarted.current) {
      return;
    }
    hasStarted.current = true;
    void runWorkflow();
  }, [runWorkflow]);

  const markdown = useMemo(
    () => renderMarkdown({ state, pending, output, error, preferences, logPath }),
    [error, logPath, output, pending, preferences, state],
  );

  return (
    <Detail
      isLoading={state === "checking" || state === "running"}
      markdown={markdown}
      actions={
        <ActionPanel>
          <Action title="Run Again" icon={Icon.ArrowClockwise} onAction={() => void runWorkflow()} />
          <Action title="Open Runtime Log" icon={Icon.Document} onAction={() => void open(logPath)} />
          <Action
            title="Open YouTube Sources"
            icon={Icon.Folder}
            onAction={() => void open(path.join(vaultPath, "Raw", "Sources", "YouTube"))}
          />
          <Action title="Open Extension Preferences" icon={Icon.Gear} onAction={openExtensionPreferences} />
        </ActionPanel>
      }
    />
  );
}

async function assertVault(vaultPath: string) {
  await access(path.join(vaultPath, "scripts", "auto_youtube_triage.sh"));
  await access(path.join(vaultPath, "scripts", "wiki_tool.py"));
}

async function loadPendingVideos(vaultPath: string): Promise<PendingVideo[]> {
  const result = await runCommand("python3", ["scripts/wiki_tool.py", "youtube-pending", "--json"], {
    cwd: vaultPath,
  });
  if (result.exitCode !== 0) {
    throw new Error(result.stderr.trim() || result.stdout.trim() || "failed to load pending YouTube sources");
  }
  return JSON.parse(result.stdout) as PendingVideo[];
}

async function runScript(
  vaultPath: string,
  preferences: ExtensionPrefs,
  onOutput: (chunk: string) => void,
): Promise<{ exitCode: number }> {
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    YOUTUBE_TRIAGE_PROVIDER: preferences.provider,
    YOUTUBE_TRIAGE_LIMIT: numericPreference(preferences.limit, "3"),
    YOUTUBE_TRIAGE_TIMEOUT: numericPreference(preferences.timeout, "300"),
    YOUTUBE_TRIAGE_SETTLE_SECONDS: numericPreference(preferences.settleSeconds, "15"),
    YOUTUBE_TRIAGE_DRY_RUN: preferences.dryRun ? "1" : "0",
    YOUTUBE_TRIAGE_NO_BUILD: preferences.noBuild ? "1" : "0",
  };

  const model = preferences.model?.trim();
  if (model) {
    env.YOUTUBE_TRIAGE_MODEL = model;
  }

  const maxBodyChars = preferences.maxBodyChars?.trim();
  if (maxBodyChars) {
    env.YOUTUBE_TRIAGE_MAX_BODY_CHARS = numericPreference(maxBodyChars, maxBodyChars);
  }

  return runCommand("bash", ["scripts/auto_youtube_triage.sh"], {
    cwd: vaultPath,
    env,
    onOutput,
  });
}

function runCommand(
  command: string,
  args: string[],
  options: {
    cwd: string;
    env?: NodeJS.ProcessEnv;
    onOutput?: (chunk: string) => void;
  },
): Promise<{ exitCode: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      shell: false,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data: Buffer) => {
      const chunk = data.toString();
      stdout += chunk;
      options.onOutput?.(chunk);
    });

    child.stderr.on("data", (data: Buffer) => {
      const chunk = data.toString();
      stderr += chunk;
      options.onOutput?.(chunk);
    });

    child.on("error", reject);
    child.on("close", (exitCode) => {
      resolve({ exitCode: exitCode ?? 1, stdout, stderr });
    });
  });
}

async function readLogTail(logPath: string): Promise<string> {
  try {
    const text = await readFile(logPath, "utf8");
    return text.split("\n").slice(-120).join("\n").trim();
  } catch {
    return "";
  }
}

function numericPreference(value: string | undefined, fallback: string): string {
  const cleaned = value?.trim();
  return cleaned && /^\d+$/.test(cleaned) ? cleaned : fallback;
}

function formatQueue(pendingVideos: PendingVideo[]): string {
  const lines = pendingVideos.map((video, index) => {
    const title = video.title || video.path;
    const author = video.author ? ` by ${video.author}` : "";
    return `${index + 1}. ${title}${author}\n   ${video.path}`;
  });
  return `queued pending YouTube sources:\n${lines.join("\n")}\n\n`;
}

function renderMarkdown({
  state,
  pending,
  output,
  error,
  preferences,
  logPath,
}: {
  state: RunState;
  pending: PendingVideo[];
  output: string;
  error: string | null;
  preferences: ExtensionPrefs;
  logPath: string;
}) {
  const status = {
    checking: "Checking pending YouTube sources",
    running: "Processing pending YouTube videos",
    succeeded: "YouTube triage finished",
    failed: "YouTube triage failed",
  }[state];

  const settings = [
    `provider: ${preferences.provider}`,
    `limit: ${numericPreference(preferences.limit, "3")}`,
    `timeout: ${numericPreference(preferences.timeout, "300")}s`,
    `settle: ${numericPreference(preferences.settleSeconds, "15")}s`,
    preferences.model?.trim() ? `model: ${preferences.model.trim()}` : null,
    preferences.maxBodyChars?.trim() ? `max_body_chars: ${preferences.maxBodyChars.trim()}` : null,
    preferences.dryRun ? "dry_run: true" : null,
    preferences.noBuild ? "no_build: true" : null,
  ].filter(Boolean);

  return [
    `# ${status}`,
    error ? `**Error:** ${escapeMarkdown(error)}` : null,
    `Pending queue: **${pending.length}**`,
    `Log: \`${logPath}\``,
    `Settings: \`${settings.join(" | ")}\``,
    "```text",
    output.trim() || "Starting...",
    "```",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function trimLog(text: string): string {
  if (text.length <= MAX_VISIBLE_LOG_CHARS) {
    return text;
  }
  return `[trimmed]\n${text.slice(text.length - MAX_VISIBLE_LOG_CHARS)}`;
}

function escapeMarkdown(value: string): string {
  return value.replace(/[\\`*_{}[\]()#+\-.!|>]/g, "\\$&");
}
