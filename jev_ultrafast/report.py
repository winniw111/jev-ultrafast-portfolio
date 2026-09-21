"""Build reproducible, offline summaries from Jev run and benchmark JSON."""

from __future__ import annotations

import argparse
import html
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
    raw_actions = payload.get("actions", payload.get("history", []))
    actions = raw_actions if isinstance(raw_actions, list) else []
    action_count = len(actions)
    if not actions and isinstance(payload.get("browser_actions"), int):
        action_count = payload["browser_actions"]
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
        "actions": action_count,
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


def _metric_card(label: str, value: Any, detail: str = "") -> str:
    detail_html = f'<span class="detail">{html.escape(detail)}</span>' if detail else ""
    return (
        '<article class="metric">'
        f'<span class="label">{html.escape(label)}</span>'
        f'<strong>{html.escape(_value(value))}</strong>{detail_html}'
        "</article>"
    )


def _verification_badge(value: bool | None) -> str:
    if value is True:
        label, css_class = "Verified", "success"
    elif value is False:
        label, css_class = "Failed", "failure"
    else:
        label, css_class = "Not verified", "neutral"
    return f'<span class="badge {css_class}">{label}</span>'


def _run_html(summary: dict[str, Any]) -> tuple[str, str]:
    elapsed = summary["elapsed_ms"]
    elapsed_value = f"{elapsed / 1000:.2f} s" if isinstance(elapsed, (int, float)) else "n/a"
    cards = "".join(
        [
            _metric_card("Elapsed", elapsed_value, "decision start to completion"),
            _metric_card("Browser actions", summary["actions"]),
            _metric_card("Decision requests", summary["decision_requests"]),
            _metric_card("Median decision", f"{_value(summary['decision_median_ms'])} ms"),
            _metric_card("Text calls", summary["text_calls"]),
            _metric_card("Text cost", f"${summary['text_cost_usd']:.8f}"),
        ]
    )
    operations = summary["operations"]
    maximum = max(operations.values(), default=1)
    bars = "".join(
        '<div class="bar-row">'
        f'<span>{html.escape(name)}</span><div class="bar-track">'
        f'<div class="bar" style="width:{count / maximum * 100:.1f}%"></div></div>'
        f"<strong>{count}</strong></div>"
        for name, count in operations.items()
    )
    section = (
        '<section><div class="section-title"><h2>Operation mix</h2><span>Observed browser mutations</span></div>'
        f'<div class="bars">{bars or "<p>No actions recorded.</p>"}</div></section>'
    )
    return cards, section


def _benchmark_html(summary: dict[str, Any]) -> tuple[str, str]:
    cards = "".join(
        [
            _metric_card("Runs", summary["runs"]),
            _metric_card("Verified", summary["verified_runs"]),
            _metric_card("Passed", summary["passed_runs"]),
            _metric_card("Median elapsed", f"{_value(summary['median_elapsed_ms'])} ms"),
            _metric_card("Median actions", summary["median_actions"]),
        ]
    )
    elapsed_values = [
        run["elapsed_ms"] for run in summary["runs_detail"] if isinstance(run.get("elapsed_ms"), (int, float))
    ]
    maximum = max(elapsed_values, default=1)
    rows = []
    for index, run in enumerate(summary["runs_detail"], start=1):
        elapsed = run.get("elapsed_ms")
        width = elapsed / maximum * 100 if isinstance(elapsed, (int, float)) else 0
        rows.append(
            "<tr>"
            f"<td>Run {index}</td><td>{_verification_badge(run['verified'])}</td>"
            f'<td><div class="inline-bar"><i style="width:{width:.1f}%"></i></div>'
            f"{html.escape(_value(elapsed))} ms</td>"
            f"<td>{run['actions']}</td><td>{run['decision_requests']}</td>"
            "</tr>"
        )
    section = (
        '<section><div class="section-title"><h2>Run comparison</h2><span>Relative elapsed time per run</span></div>'
        '<div class="table-wrap"><table><thead><tr><th>Run</th><th>Result</th><th>Elapsed</th>'
        f'<th>Actions</th><th>Decisions</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )
    return cards, section


def to_html(summary: dict[str, Any], source: str = "run.json") -> str:
    """Render a self-contained, responsive HTML report with no remote assets."""
    cards, detail = _benchmark_html(summary) if summary["kind"] == "benchmark" else _run_html(summary)
    task = html.escape(str(summary.get("task") or "No task description recorded."))
    source_label = html.escape(source)
    badge = "" if summary["kind"] == "benchmark" else _verification_badge(summary["verified"])
    styles = """
:root {
  color-scheme: dark; --bg: #07111f; --line: #20364d; --text: #ecf4ff; --muted: #91a7bd;
  --cyan: #5eead4; --blue: #60a5fa; --green: #34d399; --red: #fb7185;
}
* { box-sizing: border-box; }
body {
  margin: 0; color: var(--text); font: 15px/1.6 Inter, ui-sans-serif, system-ui, sans-serif;
  background: radial-gradient(circle at 90% 0, #123054 0, transparent 32rem), var(--bg);
}
main { width: min(1080px, calc(100% - 36px)); margin: 0 auto; padding: 64px 0 48px; }
.eyebrow { color: var(--cyan); font-size: 12px; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }
h1 { font-size: clamp(34px, 6vw, 64px); line-height: 1.05; margin: 10px 0 18px; letter-spacing: -.04em; }
.lede { max-width: 820px; color: #bdd0e4; font-size: 17px; }
.topline { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.source { color: var(--muted); font-family: ui-monospace, monospace; }
.badge {
  display: inline-flex; padding: 5px 10px; border: 1px solid; border-radius: 999px;
  font-size: 12px; font-weight: 800;
}
.success { color: var(--green); background: #0b2d28; }
.failure { color: var(--red); background: #351624; }
.neutral { color: var(--muted); background: #172536; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 38px 0; }
.metric, section {
  border: 1px solid var(--line); background: linear-gradient(145deg, rgba(18,39,61,.92), rgba(9,24,39,.96));
  box-shadow: 0 24px 70px rgba(0,0,0,.22);
}
.metric { min-height: 140px; padding: 22px; border-radius: 18px; display: flex; flex-direction: column; }
.metric .label { color: var(--muted); font-size: 13px; }
.metric strong { font-size: 30px; margin-top: auto; letter-spacing: -.03em; }
.detail { color: var(--muted); font-size: 11px; }
section { padding: 26px; border-radius: 22px; }
.section-title { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.section-title h2 { margin: 0; font-size: 22px; }
.section-title span { color: var(--muted); font-size: 12px; }
.bars { display: grid; gap: 15px; }
.bar-row { display: grid; grid-template-columns: 110px 1fr 34px; align-items: center; gap: 14px; }
.bar-row > span { font: 12px ui-monospace, monospace; color: #c7d7e8; }
.bar-row > strong { text-align: right; }
.bar-track, .inline-bar { height: 9px; border-radius: 999px; background: #182c40; overflow: hidden; }
.bar { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--cyan), var(--blue)); }
.table-wrap { overflow: auto; }
table { width: 100%; border-collapse: collapse; white-space: nowrap; }
th, td { text-align: left; padding: 14px 12px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; }
.inline-bar { display: inline-block; width: 130px; margin-right: 12px; vertical-align: middle; }
.inline-bar i { display: block; height: 100%; background: linear-gradient(90deg, var(--blue), var(--cyan)); }
footer { color: var(--muted); font-size: 12px; margin-top: 22px; text-align: right; }
@media(max-width: 720px) {
  main { padding-top: 36px; } .grid { grid-template-columns: repeat(2, 1fr); }
  .topline, .section-title { align-items: flex-start; flex-direction: column; }
  .bar-row { grid-template-columns: 86px 1fr 30px; }
}
@media(max-width: 450px) { .grid { grid-template-columns: 1fr; } .metric { min-height: 112px; } }
"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jev report · {source_label}</title><style>{styles}</style></head>
<body><main><div class="topline"><span class="eyebrow">Jev · Run intelligence</span>
<span class="source">{source_label}</span></div>
<h1>Browser agent<br>execution report</h1><p class="lede">{task}</p>{badge}
<div class="grid">{cards}</div>{detail}
<footer>Generated offline by jev-report · no API calls</footer></main></body></html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize Jev run or benchmark JSON without API calls.")
    parser.add_argument("input", type=Path, help="state.json or measurement JSON")
    parser.add_argument("-o", "--output", type=Path, help="write the report to this file")
    parser.add_argument("--format", choices=("markdown", "json", "html"), default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = summarize(payload)
    if args.format == "json":
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    elif args.format == "html":
        rendered = to_html(result, args.input.name)
    else:
        rendered = to_markdown(result, args.input.name)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
