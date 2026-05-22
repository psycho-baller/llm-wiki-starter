#!/usr/bin/env python3
"""AI-backed YouTube triage helpers for the LLM Wiki."""

from __future__ import annotations

import json
import os
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
BODY_FIELDS = ("summary", "skim_plan", "what_to_look_for", "things", "next_actions")
METADATA_RESULT_FIELDS = (
    *SCORE_FIELDS,
    *RISK_FIELDS,
    "decision",
    "confidence",
    "triage_reason",
    "expected_gain",
    "combined_score",
)
DECISIONS = {"skip", "watch", "skim", "process", "later"}
DECISION_RANKS = {"skip": 0, "later": 0, "skim": 1, "watch": 2, "process": 3}
RISK_LEVELS = {"low", "medium", "high"}
RISK_PENALTIES = {"low": 0, "medium": 1, "high": 2}
DEFAULT_RAMI_CONTEXT = """Rami is building an LLM Wiki in Obsidian. He wants to filter YouTube videos before watching or processing them. He cares about converting learning into action, rejection therapy, storytelling, communication, courage, habit formation, business/product/AI, and building a useful personal knowledge system."""


class TriageError(Exception):
    """Raised when a triage provider fails or returns invalid data."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "codex"
    model: str | None = None
    timeout: int = 300
    max_body_chars: int | None = None


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
        inner = value[1:-1]
        if inner.lower() == "true":
            return True
        if inner.lower() == "false":
            return False
        return inner
    if value.startswith("'") and value.endswith("'"):
        inner = value[1:-1]
        if inner.lower() == "true":
            return True
        if inner.lower() == "false":
            return False
        return inner
    if value.startswith("[") and value.endswith("]") and not value.startswith("[["):
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
        raise TriageError(
            f"provider result missing required keys: {', '.join(missing)}"
        )
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
        if expected_type == "string":
            if not isinstance(value, str):
                raise TriageError(f"{key} must be a string")
            if "maxLength" in spec and len(value) > int(spec["maxLength"]):
                raise TriageError(f"{key} must be <= {spec['maxLength']} characters")
            if "pattern" in spec and not re.search(str(spec["pattern"]), value):
                raise TriageError(f"{key} must match pattern {spec['pattern']}")
        if expected_type == "array":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise TriageError(f"{key} must be an array of strings")
            if "minItems" in spec and len(value) < int(spec["minItems"]):
                raise TriageError(f"{key} must have at least {spec['minItems']} items")
            if "maxItems" in spec and len(value) > int(spec["maxItems"]):
                raise TriageError(f"{key} must have at most {spec['maxItems']} items")
            item_spec = spec.get("items", {})
            for index, item in enumerate(value, start=1):
                if "maxLength" in item_spec and len(item) > int(item_spec["maxLength"]):
                    raise TriageError(
                        f"{key}[{index}] must be <= {item_spec['maxLength']} characters"
                    )
                if "pattern" in item_spec and not re.search(
                    str(item_spec["pattern"]), item
                ):
                    raise TriageError(
                        f"{key}[{index}] must match pattern {item_spec['pattern']}"
                    )
        if expected_type == "object":
            if not isinstance(value, dict):
                raise TriageError(f"{key} must be an object")
            nested_required = spec.get("required", [])
            nested_properties = spec.get("properties", {})
            nested_missing = [
                nested_key for nested_key in nested_required if nested_key not in value
            ]
            if nested_missing:
                raise TriageError(
                    f"{key} missing required keys: {', '.join(nested_missing)}"
                )
            if spec.get("additionalProperties") is False:
                nested_extra = sorted(set(value) - set(nested_properties))
                if nested_extra:
                    raise TriageError(
                        f"{key} returned unexpected keys: {', '.join(nested_extra)}"
                    )
            for nested_key, nested_value in value.items():
                nested_spec = nested_properties.get(nested_key, {})
                if nested_spec.get("type") == "array" and (
                    not isinstance(nested_value, list)
                    or not all(isinstance(item, str) for item in nested_value)
                ):
                    raise TriageError(f"{key}.{nested_key} must be an array of strings")
        if "enum" in spec and value not in set(spec["enum"]):
            raise TriageError(f"{key} must be one of {spec['enum']}")
    return result


def calculate_combined_score(result: dict[str, Any]) -> int:
    positive_score = sum(int(result[field]) for field in SCORE_FIELDS)
    penalty = sum(RISK_PENALTIES[str(result[field])] for field in RISK_FIELDS)
    adjusted_score = max(0, positive_score - penalty)
    return round((adjusted_score / 30) * 100)


def decision_cap_for_score(score: int) -> str:
    if score >= 75:
        return "process"
    if score >= 65:
        return "watch"
    if score >= 40:
        return "skim"
    return "later"


def cap_decision_by_score(result: dict[str, Any]) -> None:
    """Prevent optimistic decisions that contradict deterministic score inputs."""
    decision = str(result["decision"])
    cap = decision_cap_for_score(int(result["combined_score"]))
    if DECISION_RANKS[decision] <= DECISION_RANKS[cap]:
        return
    result["decision"] = cap
    result["triage_reason"] = (
        f"Decision downgraded from {decision} to {cap} by deterministic score guard. "
        + str(result["triage_reason"]).strip()
    )
    result["summary"] = (
        f"Treat this as {cap}, not {decision}: " + str(result["summary"]).strip()
    )


def unquote_env_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def load_env_file(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = unquote_env_value(value)


def load_rami_context(root: Path, max_chars: int = 8000) -> str:
    load_env_file(root)
    context_path = os.environ.get("RAMI_CONTEXT_PATH", "").strip()
    if not context_path:
        return DEFAULT_RAMI_CONTEXT
    path = Path(context_path).expanduser()
    if not path.exists():
        raise TriageError(f"RAMI_CONTEXT_PATH does not exist: {context_path}")
    text = path.read_text(encoding="utf-8").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[context truncated]"


def body_excerpt(body: str, max_chars: int | None = None) -> str:
    body = body.strip()
    if max_chars is None or max_chars <= 0:
        return body
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[excerpt truncated]"


def build_prompt(
    source_path: Path,
    frontmatter: dict[str, Any],
    body: str,
    rami_context: str,
    max_body_chars: int | None = None,
) -> str:
    return (
        textwrap.dedent(
            f"""
        You are scoring whether a YouTube video is worth watching for Rami.

        Do not edit files. Do not run commands. Return only valid JSON matching the provided schema.
        Do not include combined_score. It is calculated deterministically by the Python tooling.
        Return body fields as structured JSON, not markdown. Do not create Recommendation, Why, why_process, or why_not_process sections.

        Evaluate whether this video beats the opportunity cost of Rami's attention. Optimize for behavior change, useful judgment, story material, reusable frameworks, and actionability. Be skeptical of redundancy, vague motivation, clickbait, and low-density content. Do not over-score a video just because it is relevant.

        Decision meanings:
        - skip: not worth attention by default
        - watch: worth watching personally, not necessarily Wiki material
        - skim: extract lightweight value without full watching
        - process: high-value source worth compiling into Wiki notes
        - later: maybe valuable, wrong timing

        Decision must be consistent with the scores and risks. Use process only for clearly high-value videos, watch for strong personal value, skim for lightweight extraction, and skip/later when the score inputs are mixed or weak. A deterministic score guard will downgrade overly optimistic decisions.

        Confidence means how reliable the triage judgment is, not how good the video is:
        - high: enough transcript/context to judge and the recommendation is stable
        - medium: enough signal to judge but credibility, density, or later sections remain uncertain
        - low: too little evidence, missing transcript, or decision is highly uncertain

        Writing style for body fields:
        - Be simple, direct, but thorough and personal to Rami.
        - Tie the value to Rami's real projects and ambitions when the transcript supports it: LLM Wiki, YouTube filtering, rejection therapy, storytelling, comedy/acting/improv, business/product/AI, courage-building, and turning learning into action.
        - Use timestamps or time ranges whenever possible so Rami can jump directly to the useful parts. If exact timestamps are unavailable, infer approximate ranges from transcript order and mark them with "approx.".
        - Prefer thorough practical instructions over explanation. Only explain when the context is beneficial

        Body field requirements:
        - summary: Say what the video is actually useful for and whether it is worth Rami's attention.
        - skim_plan: How should Rami approach skimming this video. What is the core value that he should strive to extract from it.
        - what_to_look_for: 3-5 specific items Rami should hunt for/avoid while skimming. Each item must start with a timestamp or time range, for example "12:40-15:10 - ...".
        - things.people: notable people mentioned; empty list if none.
        - things.places: notable places mentioned; empty list if none.
        - things.things_and_concepts: notable objects, ideas, frameworks, concepts, tools, companies, or projects.
        - next_actions: 1-5 concrete actions Rami should take based on the decision. Make each action fit one of these forms:
          1. A habit stack: "After [existing routine], I will [tiny action] for [time/amount] because [the deep, powerful why/motivation]."
          2. A one-time next step: "Do [specific task] in [specific place/tool] before [clear stopping point]."
          3. A principle: "Use this rule: [short operational rule]."

        Make expected_gain sharp and outcome-oriented. It should say what changes for Rami if he follows the recommendation.

        Video source path: {source_path.as_posix()}
        title: {frontmatter.get("title", "")}
        author: {frontmatter.get("author", "")}
        url: {frontmatter.get("url", "")}
        published: {frontmatter.get("published", "")}

        Rami context:
        {rami_context}

        Source body, description, transcript, or excerpt:
        {body_excerpt(body, max_chars=max_body_chars)}
        """
        )
        .strip()
        .replace("\n        ", "\n")
    )


def run_command(
    cmd: list[str], prompt: str | None, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_codex(
    root: Path, schema_path: Path, prompt: str, config: ProviderConfig
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        prefix="youtube_triage_", suffix=".json", delete=False
    ) as handle:
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
        raise TriageError(
            f"codex failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    text = (
        output_path.read_text(encoding="utf-8")
        if output_path.exists()
        else completed.stdout
    )
    output_path.unlink(missing_ok=True)
    return parse_json_from_text(text)


def run_gemini(
    _root: Path, _schema_path: Path, prompt: str, config: ProviderConfig
) -> dict[str, Any]:
    cmd = ["gemini", "--prompt", prompt, "--output-format", "json"]
    if config.model:
        cmd[1:1] = ["--model", config.model]
    completed = run_command(cmd, None, config.timeout)
    if completed.returncode != 0:
        raise TriageError(
            f"gemini failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    outer = parse_json_from_text(completed.stdout)
    response = outer.get("response", completed.stdout)
    return parse_json_from_text(str(response))


def run_claude(
    _root: Path, schema_path: Path, prompt: str, config: ProviderConfig
) -> dict[str, Any]:
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
        raise TriageError(
            f"claude failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    outer = parse_json_from_text(completed.stdout)
    response = outer.get("result", completed.stdout)
    return parse_json_from_text(str(response))


def run_provider(
    root: Path, schema_path: Path, prompt: str, config: ProviderConfig
) -> dict[str, Any]:
    provider = config.provider.lower()
    if provider == "codex":
        return run_codex(root, schema_path, prompt, config)
    if provider == "gemini":
        return run_gemini(root, schema_path, prompt, config)
    if provider == "claude":
        return run_claude(root, schema_path, prompt, config)
    raise TriageError(f"unsupported provider: {config.provider}")


def comma_list(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    return ", ".join(cleaned) if cleaned else "none"


def bullet_list(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    return "\n".join(f"- {item}" for item in cleaned) if cleaned else "- none"


def render_generated_sections(result: dict[str, Any]) -> str:
    things = result["things"]
    return "\n\n".join(
        [
            "## Summary\n\n" + result["summary"].strip(),
            "## Skim Plan\n\n" + result["skim_plan"].strip(),
            "## What To Look For\n\n" + bullet_list(result["what_to_look_for"]),
            "## Things\n\n"
            + "\n".join(
                [
                    f"- People: {comma_list(things['people'])}",
                    f"- Places: {comma_list(things['places'])}",
                    f"- Things & Concepts: {comma_list(things['things_and_concepts'])}",
                ]
            ),
            "## Next Actions\n\n" + bullet_list(result["next_actions"]),
        ]
    )


def remove_generated_sections(body: str) -> str:
    generated_headers = (
        "Triage Notes",
        "Summary",
        "Skim Plan",
        "What To Look For",
        "Things",
        "Next Action",
        "Next Actions",
    )
    pattern = re.compile(
        rf"^## ({'|'.join(re.escape(header) for header in generated_headers)})\s*$.*?(?=^## |^!\[|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    previous = None
    cleaned = body
    while previous != cleaned:
        previous = cleaned
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def upsert_generated_sections(body: str, result: dict[str, Any]) -> str:
    generated = render_generated_sections(result)
    original = remove_generated_sections(body)
    if not original:
        return generated + "\n"
    return generated + "\n\n" + original.rstrip() + "\n"


def frontmatter_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: result[key] for key in METADATA_RESULT_FIELDS if key in result}


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
    source_body = remove_generated_sections(body)
    prompt = build_prompt(
        source_path.relative_to(root),
        frontmatter,
        source_body,
        load_rami_context(root),
        max_body_chars=config.max_body_chars,
    )
    if config.provider == "manual":
        return {"prompt": prompt}
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    result = validate_result(run_provider(root, schema_path, prompt, config), schema)
    result["combined_score"] = calculate_combined_score(result)
    cap_decision_by_score(result)
    if dry_run:
        return result
    updated_frontmatter = dict(frontmatter)
    for key in BODY_FIELDS:
        updated_frontmatter.pop(key, None)
    updated_frontmatter.setdefault("consumption_status", "unwatched")
    updated_frontmatter.setdefault("consumed_at", None)
    updated_frontmatter.update(frontmatter_result(result))
    updated_body = upsert_generated_sections(body, result)
    source_path.write_text(
        dump_frontmatter(updated_frontmatter) + updated_body, encoding="utf-8"
    )
    return result
