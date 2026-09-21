"""Browser-backed smoke check for an offline HTML report. No model calls."""

import sys
from pathlib import Path

from jev_ultrafast.browser import Browser


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/sample-report.html").resolve()
    if not path.is_file():
        raise SystemExit(f"Report not found: {path}")

    browser = Browser(path.as_uri())
    try:
        steps = browser.evaluate("document.querySelectorAll('.trace-step').length")
        assert steps > 0, "Expected at least one timeline step"

        filter_count = browser.evaluate("document.querySelectorAll('.filter').length")
        assert filter_count > 1, "Expected operation filters"
        browser.evaluate("document.querySelectorAll('.filter')[1].click()")
        visible = browser.evaluate("[...document.querySelectorAll('.trace-step')].filter(row => !row.hidden).length")
        assert 0 < visible <= steps, "Filtering hid every timeline step"

        browser.evaluate("document.querySelector('#replay').click()")
        current = browser.evaluate("document.querySelectorAll('.trace-step.current').length")
        assert current == 1, "Replay did not activate the first visible step"
        browser.evaluate("document.querySelector('#replay').click()")
    finally:
        browser.close()

    print(f"Report interactions passed: {steps} steps, {filter_count} filters")


if __name__ == "__main__":
    main()
