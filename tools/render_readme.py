#!/usr/bin/env python3
"""
Validates stats.json against an independent copy of the exporter's schema,
and regenerates the generated region of README.md from content.json and
stats.json.

Two separate modes, not one, on purpose: "validate" and "regenerate README"
cannot be the same invocation, because on a legitimate stats push the
README is by definition out of date, so a combined check-mode gate would
go red on every ordinary push. `validate` never touches README.md and
never succeeds on bad input. `render` never fails on stale content, only
on input it cannot parse or validate, and is idempotent: a second run
against its own output is a byte-for-byte no-op, so this script's own
commit cannot retrigger itself.

Schema note: this file's ALLOWED/SCHEMA below is a second, independently
written copy of scripts/showcase-export.py's table in the brain repo,
deliberately not shared code, the same discipline as
agent-queue-runner.sh's independent allowlist. A schema bump must land
here before the exporter starts emitting it, or every push goes red the
moment it does: this validator pins schema == 1 and refuses anything else
by design.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT_JSON = REPO / "content.json"
STATS_JSON = REPO / "stats.json"
README = REPO / "README.md"

BEGIN_MARKER = "<!-- BEGIN GENERATED -->"
END_MARKER = "<!-- END GENERATED -->"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATUS = frozenset({"healthy", "degraded"})
SCHEMA = 1

ALLOWED = {
    "schema": int,
    "lastVerified": "date",
    "dockerStacks": int,
    "scheduledJobs": int,
    "jobRuns14d": int,
    "jobSuccessRate14d": float,
    "status": "status",
}


class Invalid(Exception):
    """stats.json fails validation. Caller of --validate exits non-zero."""


def _check_type(key: str, value, expected) -> str | None:
    if expected is int:
        # bool is a subclass of int in Python, so this must be an exact-type
        # check, not isinstance, or a stray True/False slips through as an
        # int and serialises as true/false.
        if type(value) is not int:
            return f"{key} is {type(value).__name__}, expected int"
        return None
    if expected is float:
        if type(value) is not float:
            return f"{key} is {type(value).__name__}, expected float"
        return None
    if expected == "date":
        if type(value) is not str or not DATE_RE.match(value):
            return f"{key} is not a YYYY-MM-DD date string"
        return None
    if expected == "status":
        if value not in STATUS:
            return f"{key} is not a member of {sorted(STATUS)}"
        return None
    return f"{key} has no known validator for {expected!r}"


def validate_stats(raw: str) -> dict:
    """Returns the parsed, validated payload, or raises Invalid."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise Invalid(f"stats.json is not valid JSON: {e}")

    if not isinstance(payload, dict):
        raise Invalid("stats.json is not a JSON object")

    extra = set(payload) - set(ALLOWED)
    if extra:
        raise Invalid(f"stats.json has key(s) outside the schema: {sorted(extra)}")
    missing = set(ALLOWED) - set(payload)
    if missing:
        raise Invalid(f"stats.json is missing key(s): {sorted(missing)}")

    for key, expected in ALLOWED.items():
        err = _check_type(key, payload[key], expected)
        if err:
            raise Invalid(err)

    if payload["schema"] != SCHEMA:
        raise Invalid(f"stats.json schema is {payload['schema']}, "
                       f"this validator pins schema == {SCHEMA}")

    for key in ("dockerStacks", "scheduledJobs"):
        if not (0 < payload[key] < 10_000):
            raise Invalid(f"{key} is out of range: {payload[key]}")

    return payload


def render_incidents(incidents: list[dict]) -> str:
    parts = []
    for inc in incidents:
        title = inc["title"]
        story = inc["story"]
        parts.append(f"### {title}\n\n{story}")
    return "\n\n".join(parts)


def render_generated_block(content: dict, stats: dict) -> str:
    s = content.get("stats", {})
    lines = [
        BEGIN_MARKER,
        "",
        "## Current stats",
        "",
        f"- **{stats['dockerStacks']}** Docker Compose stacks",
        f"- **{stats['scheduledJobs']}** scheduled jobs",
        f"- **{stats['jobRuns14d']}** job runs in the last 14 days, "
        f"**{stats['jobSuccessRate14d']:.2%}** success rate",
        f"- Status: **{stats['status']}**",
        f"- Open inbound ports: **{s.get('openInboundPorts', '?')}**",
        f"- Secrets encryption: **{s.get('secretsEncryption', '?')}**",
        f"- Last verified: **{stats['lastVerified']}**",
        "",
        "## Incidents",
        "",
        render_incidents(content.get("incidents", [])),
        "",
        END_MARKER,
    ]
    return "\n".join(lines)


def splice_readme(readme_text: str, generated_block: str) -> str:
    if BEGIN_MARKER not in readme_text or END_MARKER not in readme_text:
        raise Invalid(f"README.md is missing {BEGIN_MARKER} / {END_MARKER}")
    before = readme_text.split(BEGIN_MARKER)[0]
    after = readme_text.split(END_MARKER)[1]
    return before + generated_block + after


def cmd_validate(args) -> int:
    raw = Path(args.stats).read_text()
    try:
        validate_stats(raw)
    except Invalid as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print("stats.json is valid")
    return 0


def cmd_render(args) -> int:
    content = json.loads(Path(args.content).read_text())
    raw_stats = Path(args.stats).read_text()
    try:
        stats = validate_stats(raw_stats)
    except Invalid as e:
        print(f"INVALID, not rendering: {e}", file=sys.stderr)
        return 1

    readme_path = Path(args.readme)
    before = readme_path.read_text()
    block = render_generated_block(content, stats)
    after = splice_readme(before, block)

    if after == before:
        print("no-op: README.md already reflects content.json + stats.json")
        return 0

    readme_path.write_text(after)
    print(f"wrote {readme_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    v = sub.add_parser("validate")
    v.add_argument("--stats", default=str(STATS_JSON))
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("render")
    r.add_argument("--content", default=str(CONTENT_JSON))
    r.add_argument("--stats", default=str(STATS_JSON))
    r.add_argument("--readme", default=str(README))
    r.set_defaults(func=cmd_render)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
