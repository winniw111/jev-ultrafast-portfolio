"""Offline tests for the portfolio run-report feature."""

import json

from jev_ultrafast.report import main, summarize, to_markdown


def test_summarize_live_state():
    result = summarize(
        {
            "goal": "Find a book",
            "status": "done",
            "elapsed_ms": 900,
            "history": [
                {"operation": "TYPE_TEXT"},
                {"operation": "CLICK"},
                {"kind": "wait"},
            ],
            "decisions": [{"latency_ms": 120}, {"latency_ms": 180}],
            "text_calls": [{"usage": {"cost": 0.00003}}],
            "verification": {"passed": True},
        }
    )

    assert result == {
        "kind": "run",
        "task": "Find a book",
        "status": "done",
        "verified": True,
        "elapsed_ms": 900,
        "actions": 3,
        "decision_requests": 2,
        "decision_median_ms": 150.0,
        "text_calls": 1,
        "text_cost_usd": 0.00003,
        "operations": {"CLICK": 1, "TYPE_TEXT": 1, "WAIT": 1},
    }


def test_summarize_benchmark():
    result = summarize(
        {
            "task": "Search",
            "runs": [
                {"elapsed_ms": 1000, "actions": [{}, {}], "verification": {"passed": True}},
                {"elapsed_ms": 2000, "actions": [{}], "verification": {"passed": False}},
                {"elapsed_ms": 1500, "actions": [{}, {}, {}]},
            ],
        }
    )

    assert result["runs"] == 3
    assert result["verified_runs"] == 2
    assert result["passed_runs"] == 1
    assert result["median_elapsed_ms"] == 1500.0
    assert result["median_actions"] == 2.0


def test_markdown_and_cli_output(tmp_path):
    source = tmp_path / "state.json"
    output = tmp_path / "report.md"
    source.write_text(
        json.dumps({"elapsed_ms": 700, "actions": [{"operation": "CLICK"}]}),
        encoding="utf-8",
    )

    assert main([str(source), "--output", str(output)]) == 0
    report = output.read_text(encoding="utf-8")
    assert "# Jev run report: state.json" in report
    assert "| Browser actions | 1 |" in report
    assert "## Operations" in to_markdown(
        summarize(json.loads(source.read_text(encoding="utf-8"))), source.name
    )
