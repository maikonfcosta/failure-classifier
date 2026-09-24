from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from failure_classifier.classify import Category, Verdict, classify
from failure_classifier.report import Failure, Report, ReportError, load, load_health

DEFAULT_FAIL_ON = f"{Category.PRODUCT},{Category.UNKNOWN}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="failure-classifier",
        description="Classify failed Playwright tests as product, environment, test or unknown.",
    )
    parser.add_argument("report", type=Path, help="Playwright JSON report")
    parser.add_argument("--health", type=Path, help="health probe result: JSON with an 'ok' boolean")
    parser.add_argument("--json", type=Path, dest="json_out", help="write the verdicts to this file")
    parser.add_argument(
        "--fail-on",
        default=DEFAULT_FAIL_ON,
        help=f"comma-separated categories that exit with 1 (default: {DEFAULT_FAIL_ON}; '' = never)",
    )
    args = parser.parse_args(argv)

    try:
        fail_on = {Category(c) for c in args.fail_on.split(",") if c}
        healthy = load_health(args.health)
        report = load(args.report)
    except (ReportError, ValueError) as err:
        print(f"failure-classifier: {err}", file=sys.stderr)
        return 2

    results = [(f, classify(f, healthy)) for f in report.failures]

    table = render(report, results, healthy)
    print(table)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(table + "\n")
    if args.json_out:
        args.json_out.write_text(json.dumps([to_json(f, v) for f, v in results], indent=1), encoding="utf-8")

    # A run that tested nothing is not a green run, whatever the categories say.
    if report.errors or report.ran == 0:
        return 1
    # Flaky tests passed in the end: they are reported, but only real failures can block.
    return 1 if any(f.status == "unexpected" and v.category in fail_on for f, v in results) else 0


def render(report: Report, results: list[tuple[Failure, Verdict]], healthy: bool | None) -> str:
    probe = {True: "healthy", False: "unhealthy", None: "not provided"}[healthy]
    flaky = sum(f.status == "flaky" for f, _ in results)
    lines = [
        "## Failure classification",
        "",
        f"{report.ran} tests ran, {len(results) - flaky} failed, {flaky} flaky, {report.skipped} skipped. "
        f"Health probe: {probe}.",
    ]
    for error in report.errors:
        lines += ["", f"**The run itself failed:** {error.splitlines()[0]}"]
    if report.ran == 0 and not report.errors:
        lines += ["", "**No test ran.** A pipeline that tested nothing is not green."]
    if report.skipped and results:
        lines += [
            "",
            f"{report.skipped} tests were skipped, usually because a setup test they depend on failed.",
        ]
    if not results:
        return "\n".join([*lines, "", "Nothing to classify."] if report.ran else lines)
    lines += ["", "| Category | Confidence | Test | Why | First error |", "|---|---|---|---|---|"]
    for failure, verdict in results:
        title = f"[{failure.project}] {failure.title}" + (" (flaky)" if failure.status == "flaky" else "")
        cells = [verdict.category, verdict.confidence, title, verdict.reason, _first_line(failure)]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |")
    return "\n".join(lines)


def to_json(failure: Failure, verdict: Verdict) -> dict[str, object]:
    return {
        "test": failure.title,
        "project": failure.project,
        "location": f"{failure.file}:{failure.line}",
        "status": failure.status,
        **asdict(verdict),
        "error": _first_line(failure),
    }


def _first_line(failure: Failure) -> str:
    return failure.error.splitlines()[0] if failure.error else ""


if __name__ == "__main__":
    sys.exit(main())
