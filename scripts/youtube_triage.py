#!/usr/bin/env python3
"""AI-backed YouTube triage helpers for the LLM Wiki."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCORE_FIELDS = (
    "relevance_score",
    "actionability_score",
    "novelty_score",
    "credibility_score",
    "density_score",
    "personal_resonance_score",
)
RISK_FIELDS = ("redundancy_risk", "time_cost", "clickbait_risk")
TEXT_FIELDS = ("triage_reason", "expected_gain")
DECISIONS = {"skip", "watch", "skim", "process", "later"}
RISK_LEVELS = {"low", "medium", "high"}
RISK_PENALTIES = {"low": 0, "medium": 2, "high": 4}


class TriageError(Exception):
    """Raised when a triage provider fails or returns invalid data."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "codex"
    model: str | None = None
    timeout: int = 300


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            current = data.setdefault(current_key, [])
            if not isinstance(current, list):
                current = []
                data[current_key] = current
            current.append(parse_scalar(line[4:]))
            continue
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = [] if value == "" else parse_scalar(value)
    return data, body


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return ""
    text = str(value)
    if text == "":
        return '""'
    if re.search(r"[:#\n]|^\s|\s$", text):
        return json.dumps(text)
    return text


def dump_frontmatter(data: dict[str, Any]) -> str:
    lines: list[str] = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return stripped


def parse_json_from_text(text: str) -> dict[str, Any]:
    stripped = strip_code_fence(text)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise TriageError("provider response did not contain JSON") from None
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise TriageError("provider response JSON must be an object")
    return parsed


def validate_result(result: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    extra = sorted(set(result) - set(properties))
    if schema.get("additionalProperties") is False and extra:
        raise TriageError(f"provider returned unexpected keys: {', '.join(extra)}")
    missing = [key for key in required if key not in result]
    if missing:
        raise TriageError(f"provider result missing required keys: {', '.join(missing)}")
    for key, spec in properties.items():
        if key not in result:
            continue
        value = result[key]
        expected_type = spec.get("type")
        if expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise TriageError(f"{key} must be an integer")
            if "minimum" in spec and value < int(spec["minimum"]):
                raise TriageError(f"{key} must be >= {spec['minimum']}")
            if "maximum" in spec and value > int(spec["maximum"]):
                raise TriageError(f"{key} must be <= {spec['maximum']}")
        if expected_type == "string" and not isinstance(value, str):
            raise TriageError(f"{key} must be a string")
        if "enum" in spec and value not in set(spec["enum"]):
            raise TriageError(f"{key} must be one of {spec['enum']}")
    return result


def calculate_combined_score(result: dict[str, Any]) -> int:
    positive_score = sum(int(result[field]) for field in SCORE_FIELDS)
    penalty = sum(RISK_PENALTIES[str(result[field])] for field in RISK_FIELDS)
    adjusted_score = max(0, positive_score - penalty)
    return round((adjusted_score / 30) * 100)


def body_excerpt(body: str, max_chars: int = 6000) -> str:
    body = body.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[excerpt truncated]"


def build_prompt(source_path: Path, frontmatter: dict[str, Any], body: str) -> str:
    return textwrap.dedent(
        f"""
        You are scoring whether a YouTube video is worth watching for Rami.

        Do not edit files. Do not run commands. Return only valid JSON matching the provided schema.
        Do not include combined_score. It is calculated deterministically by the Python tooling.

        Evaluate whether this video beats the opportunity cost of Rami's attention. Optimize for behavior change, useful judgment, story material, reusable frameworks, and actionability. Be skeptical of redundancy, vague motivation, clickbait, and low-density content. Do not over-score a video just because it is relevant.

        Decision meanings:
        - skip: not worth attention by default
        - watch: worth watching personally, not necessarily Wiki material
        - skim: extract lightweight value without full watching
        - process: high-value source worth compiling into Wiki notes
        - later: maybe valuable, wrong timing

        Video source path: {source_path.as_posix()}
        title: {frontmatter.get("title", "")}
        author: {frontmatter.get("author", "")}
        url: {frontmatter.get("url", "")}
        published: {frontmatter.get("published", "")}

        Rami context:
        Rami is building an LLM Wiki in Obsidian. He wants to filter YouTube videos before watching or processing them. He cares about converting learning into action, rejection therapy, storytelling, communication, courage, habit formation, business/product/AI, and building a useful personal knowledge system.

        Source body, description, transcript, or excerpt:
        {body_excerpt(body)}
        """
    ).strip()


def run_command(cmd: list[str], prompt: str | None, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_codex(root: Path, schema_path: Path, prompt: str, config: ProviderConfig) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(prefix="youtube_triage_", suffix=".json", delete=False) as handle:
        output_path = Path(handle.name)
    cmd = [
        "codex",
        "exec",
        "--cd",
        str(root),
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "-",
    ]
    if config.model:
        cmd[2:2] = ["--model", config.model]
    completed = run_command(cmd, prompt, config.timeout)
    if completed.returncode != 0:
        raise TriageError(f"codex failed: {completed.stderr.strip() or completed.stdout.strip()}")
    text = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
    output_path.unlink(missing_ok=True)
    return parse_json_from_text(text)


def run_gemini(_root: Path, _schema_path: Path, prompt: str, config: ProviderConfig) -> dict[str, Any]:
    cmd = ["gemini", "--prompt", prompt, "--output-format", "json"]
    if config.model:
        cmd[1:1] = ["--model", config.model]
    completed = run_command(cmd, None, config.timeout)
    if completed.returncode != 0:
        raise TriageError(f"gemini failed: {completed.stderr.strip() or completed.stdout.strip()}")
    outer = parse_json_from_text(completed.stdout)
    response = outer.get("response", completed.stdout)
    return parse_json_from_text(str(response))


def run_claude(_root: Path, schema_path: Path, prompt: str, config: ProviderConfig) -> dict[str, Any]:
    schema_text = schema_path.read_text(encoding="utf-8")
    cmd = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--json-schema",
        schema_text,
    ]
    if config.model:
        cmd.extend(["--model", config.model])
    cmd.append(prompt)
    completed = run_command(cmd, None, config.timeout)
    if completed.returncode != 0:
        raise TriageError(f"claude failed: {completed.stderr.strip() or completed.stdout.strip()}")
    outer = parse_json_from_text(completed.stdout)
    response = outer.get("result", completed.stdout)
    return parse_json_from_text(str(response))


def run_provider(root: Path, schema_path: Path, prompt: str, config: ProviderConfig) -> dict[str, Any]:
    provider = config.provider.lower()
    if provider == "codex":
        return run_codex(root, schema_path, prompt, config)
    if provider == "gemini":
        return run_gemini(root, schema_path, prompt, config)
    if provider == "claude":
        return run_claude(root, schema_path, prompt, config)
    raise TriageError(f"unsupported provider: {config.provider}")


def render_triage_section(result: dict[str, Any]) -> str:
    return textwrap.dedent(
        f"""
        ## Triage Notes

        - Decision: `{result["decision"]}`
        - Combined score: `{result["combined_score"]}`
        - Relevance: `{result["relevance_score"]}`
        - Actionability: `{result["actionability_score"]}`
        - Novelty: `{result["novelty_score"]}`
        - Credibility: `{result["credibility_score"]}`
        - Density: `{result["density_score"]}`
        - Personal resonance: `{result["personal_resonance_score"]}`
        - Redundancy risk: `{result["redundancy_risk"]}`
        - Time cost: `{result["time_cost"]}`
        - Clickbait risk: `{result["clickbait_risk"]}`

        ### Triage Reason

        {result["triage_reason"]}

        ### Expected Gain

        {result["expected_gain"]}
        """
    ).strip()


def upsert_triage_section(body: str, result: dict[str, Any]) -> str:
    section = render_triage_section(result)
    pattern = re.compile(r"(^## Triage Notes\s*$.*?)(?=^## |\Z)", flags=re.MULTILINE | re.DOTALL)
    if pattern.search(body):
        return pattern.sub(section + "\n\n", body).rstrip() + "\n"
    return body.rstrip() + "\n\n" + section + "\n"


def triage_source(
    root: Path,
    source_path: Path,
    schema_path: Path,
    config: ProviderConfig,
    dry_run: bool = False,
) -> dict[str, Any]:
    text = source_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    if str(frontmatter.get("source_type", "")) != "youtube":
        raise TriageError(f"{source_path} is not a YouTube source")
    prompt = build_prompt(source_path.relative_to(root), frontmatter, body)
    if config.provider == "manual":
        return {"prompt": prompt}
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    result = validate_result(run_provider(root, schema_path, prompt, config), schema)
    result["combined_score"] = calculate_combined_score(result)
    if dry_run:
        return result
    updated_frontmatter = dict(frontmatter)
    updated_frontmatter.update(result)
    updated_body = upsert_triage_section(body, result)
    source_path.write_text(dump_frontmatter(updated_frontmatter) + updated_body, encoding="utf-8")
    return result
