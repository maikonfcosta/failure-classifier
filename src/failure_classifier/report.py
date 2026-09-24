"""Reads a Playwright JSON report into a flat list of failed tests."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class Failure:
    title: str
    project: str
    file: str
    line: int
    status: str  # "unexpected" (failed) or "flaky"
    error: str  # first error message of the first failing attempt, without colors


def load(path: Path) -> list[Failure]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return list(_failures(report.get("suites", []), []))


def _failures(suites: list[dict[str, Any]], path: list[str]) -> Iterator[Failure]:
    for suite in suites:
        title = suite.get("title", "")
        # File-level suites are named after the spec file; keep only describe() titles in the path.
        here = path if title.endswith(".ts") or not title else [*path, title]
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                if test.get("status") not in ("unexpected", "flaky"):
                    continue
                yield Failure(
                    title=" > ".join([*here, spec["title"]]),
                    project=test.get("projectName", ""),
                    file=spec.get("file", ""),
                    line=spec.get("line", 0),
                    status=test["status"],
                    error=_first_error(test.get("results", [])),
                )
        yield from _failures(suite.get("suites", []), here)


def _first_error(results: list[dict[str, Any]]) -> str:
    for result in results:
        for error in result.get("errors", []):
            message = error.get("message") or ""
            if message:
                return ANSI.sub("", message)
    return ""
