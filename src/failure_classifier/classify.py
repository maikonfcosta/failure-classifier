"""Deterministic rules that turn a failure into a category. First rule that matches wins."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from failure_classifier.report import Failure


class Category(StrEnum):
    ENVIRONMENT = "environment"
    TEST = "test"
    PRODUCT = "product"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class Verdict:
    category: Category
    confidence: Confidence
    reason: str


# Errors raised before the app answered at all: nothing about the product can be concluded.
UNREACHABLE = re.compile(
    r"net::ERR_(CONNECTION_\w+|NAME_NOT_RESOLVED|ADDRESS_UNREACHABLE|INTERNET_DISCONNECTED)|ECONNREFUSED|ENOTFOUND"
)
# A 5xx status quoted in the message, e.g. "Received: 502" from expect(status) or "register failed: 502".
SERVER_ERROR = re.compile(r"(Received:\s*|failed:\s*|status\s*)5\d\d\b")
# An action (click, fill...) that gave up waiting for its element.
ACTION_TIMEOUT = re.compile(r"locator\.\w+: Timeout \d+ms exceeded")
ASSERTION = re.compile(r"expect\((locator|received|page)\)\.\w+\(")
NOT_FOUND = "element(s) not found"


def classify(failure: Failure, healthy: bool | None) -> Verdict:
    error = failure.error

    if UNREACHABLE.search(error):
        return Verdict(Category.ENVIRONMENT, Confidence.HIGH, "the app could not be reached")
    if healthy is False:
        return Verdict(Category.ENVIRONMENT, Confidence.HIGH, "the health probe failed after the run")
    if failure.network_errors:
        first = failure.network_errors[0]
        detail = first.status or first.failure
        return Verdict(Category.ENVIRONMENT, Confidence.HIGH, f"the page saw a failed request ({detail})")
    if SERVER_ERROR.search(error):
        return Verdict(Category.ENVIRONMENT, Confidence.HIGH, "the API answered with a 5xx status")

    # From here on the app looked healthy, or there was no probe to say otherwise.
    probe = "" if healthy else " (no health probe, so an outage cannot be ruled out)"

    if ACTION_TIMEOUT.search(error):
        # A product bug that hides the element looks exactly the same, hence always low.
        return Verdict(Category.TEST, Confidence.LOW, "an action timed out waiting for an element" + probe)
    if ASSERTION.search(error):
        if NOT_FOUND in error:
            return Verdict(
                Category.PRODUCT,
                Confidence.LOW,
                "the asserted element does not exist; the test may be outdated" + probe,
            )
        return Verdict(
            Category.PRODUCT,
            Confidence.HIGH if healthy else Confidence.LOW,
            "a business assertion failed on a healthy app" + probe,
        )
    return Verdict(Category.UNKNOWN, Confidence.LOW, "no rule matched" + probe)
