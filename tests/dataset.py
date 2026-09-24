"""Loads the labeled dataset built by scripts/build_dataset.py."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from failure_classifier.report import Failure, load, load_health

DATASET = Path(__file__).resolve().parent.parent / "dataset"
SCENARIOS = ("app-up", "api-down", "web-down")


@dataclass(frozen=True)
class Case:
    scenario: str
    failure: Failure
    healthy: bool | None
    truth: str


def cases() -> list[Case]:
    result: list[Case] = []
    for scenario in SCENARIOS:
        folder = DATASET / scenario
        expected: dict[str, str] = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        healthy = load_health(folder / "health.json")
        for failure in load(folder / "report.json").failures:
            # Expected labels are keyed by the test's own title, without the describe() path.
            result.append(Case(scenario, failure, healthy, expected[failure.title.split(" > ")[-1]]))
    return result
