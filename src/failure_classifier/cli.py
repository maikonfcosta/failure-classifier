from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from failure_classifier.report import load


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="failure-classifier", description="Classify failed Playwright tests."
    )
    parser.add_argument("report", type=Path, help="Playwright JSON report")
    args = parser.parse_args(argv)

    failures = load(args.report)
    print(f"{len(failures)} failed or flaky tests")
    for failure in failures:
        first_line = failure.error.splitlines()[0] if failure.error else ""
        print(f"- [{failure.project}] {failure.title}: {first_line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
