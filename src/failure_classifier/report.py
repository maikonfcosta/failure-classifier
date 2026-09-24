"""Reads a Playwright JSON report (and the optional health probe) into plain data."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NETWORK_ATTACHMENT = "network-errors"


@dataclass(frozen=True)
class NetworkError:
    method: str
    url: str
    status: int | None = None  # set for 5xx responses
    failure: str | None = None  # set for requests that never got a response, e.g. net::ERR_CONNECTION_REFUSED


@dataclass(frozen=True)
class Failure:
    title: str
    project: str
    file: str
    line: int
    status: str  # "unexpected" (failed) or "flaky"
    error: str  # full message of the first error of the first failing attempt, without colors
    network_errors: tuple[NetworkError, ...] = field(default=())


@dataclass(frozen=True)
class Report:
    failures: list[Failure]
    errors: list[str]  # run-level errors, e.g. "No tests found" or a broken config
    ran: int  # tests that actually executed (passed, failed or flaky)
    skipped: int


class ReportError(Exception):
    """The file is missing or is not a Playwright JSON report."""


def load(path: Path) -> Report:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ReportError(f"cannot read {path}: {err}") from err
    if not isinstance(report, dict) or "suites" not in report:
        raise ReportError(f"{path} is not a Playwright JSON report (no 'suites' key)")
    stats = report.get("stats", {})
    return Report(
        failures=list(_failures(report["suites"], [])),
        errors=[ANSI.sub("", e.get("message", "")) for e in report.get("errors", [])],
        ran=sum(stats.get(k, 0) for k in ("expected", "unexpected", "flaky")),
        skipped=stats.get("skipped", 0),
    )


def load_health(path: Path | None) -> bool | None:
    """True/False from the probe file, None when there is no probe."""
    if path is None:
        return None
    try:
        probe = json.loads(path.read_text(encoding="utf-8"))
        return bool(probe["ok"])
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise ReportError(f"cannot read health probe {path}: {err!r}") from err


def _failures(suites: list[dict[str, Any]], path: list[str]) -> Iterator[Failure]:
    for suite in suites:
        title = suite.get("title", "")
        # File-level suites are named after the spec file; keep only describe() titles in the path.
        here = path if title.endswith(".ts") or not title else [*path, title]
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                if test.get("status") not in ("unexpected", "flaky"):
                    continue
                attempt = _first_failing(test.get("results", []))
                yield Failure(
                    title=" > ".join([*here, spec["title"]]),
                    project=test.get("projectName", ""),
                    file=spec.get("file", ""),
                    line=spec.get("line", 0),
                    status=test["status"],
                    error=_first_error(attempt),
                    network_errors=_network_errors(attempt),
                )
        yield from _failures(suite.get("suites", []), here)


def _first_failing(results: list[dict[str, Any]]) -> dict[str, Any]:
    return next((r for r in results if r.get("status") != "passed"), {})


def _first_error(attempt: dict[str, Any]) -> str:
    for error in attempt.get("errors", []):
        message = error.get("message") or ""
        if message:
            return ANSI.sub("", message)
    return ""


def _network_errors(attempt: dict[str, Any]) -> tuple[NetworkError, ...]:
    for attachment in attempt.get("attachments", []):
        if attachment.get("name") == NETWORK_ATTACHMENT and "body" in attachment:
            entries = json.loads(base64.b64decode(attachment["body"]))
            return tuple(
                NetworkError(e["method"], e["url"], e.get("status"), e.get("failure")) for e in entries
            )
    return ()
