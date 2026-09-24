from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from failure_classifier.classify import Category, Verdict, classify
from failure_classifier.report import Failure, load, load_health

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

    fail_on = {Category(c) for c in args.fail_on.split(",") if c}
    healthy = load_health(args.health)
    results = [(f, classify(f, healthy)) for f in load(args.report)]

    table = render(results, healthy)
    print(table)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(table + "\n")
    if args.json_out:
        args.json_out.write_text(json.dumps([to_json(f, v) for f, v in results], indent=1), encoding="utf-8")

    return 1 if any(v.category in fail_on for _, v in results) else 0


def render(results: list[tuple[Failure, Verdict]], healthy: bool | None) -> str:
    probe = {True: "healthy", False: "unhealthy", None: "not provided"}[healthy]
    lines = [
        "## Failure classification",
        "",
        f"{len(results)} failed or flaky tests, health probe: {probe}",
        "",
    ]
    if not results:
        return "\n".join([*lines, "Nothing to classify."])
    lines += ["| Category | Confidence | Test | Why | First error |", "|---|---|---|---|---|"]
    for failure, verdict in results:
        cells = [verdict.category, verdict.confidence, f"[{failure.project}] {failure.title}", verdict.reason]
        cells.append(_first_line(failure))
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
