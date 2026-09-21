"""Build reproducible, offline summaries from Jev run and benchmark JSON."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def _passed(payload: dict[str, Any]) -> bool | None:
    verification = payload.get("verification")
    if isinstance(verification, dict) and isinstance(verification.get("passed"), bool):
        return verification["passed"]
    return None


def summarize_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a live state.json or a compact measurement object."""
    actions = payload.get("actions", payload.get("history", []))
    decisions = payload.get("decisions", [])
    text_calls = payload.get("text_calls", [])
    decision_latencies = [
        float(item["latency_ms"])
        for item in decisions
        if isinstance(item, dict) and isinstance(item.get("latency_ms"), (int, float))
    ]
    operations = Counter(
        str(item.get("operation") or item.get("kind", "unknown")).upper()
        for item in actions
        if isinstance(item, dict)
    )
    text_cost = sum(
        float(item.get("usage", {}).get("cost", 0))
        for item in text_calls
        if isinstance(item, dict) and isinstance(item.get("usage"), dict)
    )
    decision_requests = payload.get("decision_requests", len(decisions))
    decision_median_ms = payload.get("decision_median_ms", _median(decision_latencies))

    return {
        "kind": "run",
        "task": payload.get("task") or payload.get("goal"),
        "status": payload.get("status"),
        "verified": _passed(payload),
        "elapsed_ms": payload.get("elapsed_ms"),
        "actions": len(actions),
        "decision_requests": decision_requests,
        "decision_median_ms": decision_median_ms,
        "text_calls": len(text_calls),
        "text_cost_usd": round(text_cost, 8),
        "operations": dict(sorted(operations.items())),
    }


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize either one run or a benchmark containing multiple runs."""
    runs = payload.get("runs")
    if not isinstance(runs, list):
        return summarize_run(payload)

    normalized = [summarize_run(run) for run in runs if isinstance(run, dict)]
    elapsed = [float(run["elapsed_ms"]) for run in normalized if isinstance(run.get("elapsed_ms"), (int, float))]
    action_counts = [float(run["actions"]) for run in normalized]
    verified = [run["verified"] for run in normalized if run["verified"] is not None]
    return {
        "kind": "benchmark",
        "task": payload.get("task"),
        "runs": len(normalized),
        "verified_runs": len(verified),
        "passed_runs": sum(value is True for value in verified),
        "median_elapsed_ms": _median(elapsed),
        "median_actions": _median(action_counts),
        "runs_detail": normalized,
    }


def _value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def to_markdown(summary: dict[str, Any], source: str = "run.json") -> str:
    """Render a compact Markdown report suitable for CI artifacts or reviews."""
    lines = [f"# Jev run report: {source}", ""]
    if summary.get("task"):
        lines.extend([f"**Task:** {summary['task']}", ""])

    if summary["kind"] == "benchmark":
        rows = [
            ("Runs", summary["runs"]),
            ("Verified runs", summary["verified_runs"]),
            ("Passed runs", summary["passed_runs"]),
            ("Median elapsed", f"{_value(summary['median_elapsed_ms'])} ms"),
            ("Median actions", summary["median_actions"]),
        ]
    else:
        rows = [
            ("Status", summary["status"]),
            ("Verified", summary["verified"]),
            ("Elapsed", f"{_value(summary['elapsed_ms'])} ms"),
            ("Browser actions", summary["actions"]),
            ("Decision requests", summary["decision_requests"]),
            ("Median decision latency", f"{_value(summary['decision_median_ms'])} ms"),
            ("Text helper calls", summary["text_calls"]),
            ("Text helper cost", f"${summary['text_cost_usd']:.8f}"),
        ]

    lines.extend(["| Metric | Value |", "| --- | --- |"])
    lines.extend(f"| {name} | {_value(value)} |" for name, value in rows)
    if summary["kind"] == "run" and summary["operations"]:
        lines.extend(["", "## Operations", "", "| Operation | Count |", "| --- | ---: |"])
        lines.extend(f"| {name} | {count} |" for name, count in summary["operations"].items())
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Jev run or benchmark JSON without API calls.")
    parser.add_argument("input", type=Path, help="state.json or measurement JSON")
    parser.add_argument("-o", "--output", type=Path, help="write the report to this file")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = summarize(payload)
    rendered = (
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else to_markdown(result, args.input.name)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
