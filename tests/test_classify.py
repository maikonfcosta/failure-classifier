import pytest

from failure_classifier.classify import Category, Confidence, classify
from failure_classifier.report import Failure, NetworkError


def failure(error: str, network: tuple[NetworkError, ...] = ()) -> Failure:
    return Failure("t", "chromium", "a.spec.ts", 1, "unexpected", error, network)


@pytest.mark.parametrize(
    "error",
    [
        "Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:4200/",
        "Error: page.goto: net::ERR_NAME_NOT_RESOLVED at http://app.test/",
        "Error: apiRequestContext.get: connect ECONNREFUSED 127.0.0.1:3000",
        "Error: getaddrinfo ENOTFOUND api.internal",
    ],
)
def test_unreachable_app_is_environment_even_if_the_probe_says_healthy(error: str) -> None:
    verdict = classify(failure(error), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.ENVIRONMENT, Confidence.HIGH)


def test_failed_probe_wins_over_what_the_error_looks_like() -> None:
    verdict = classify(failure("Error: expect(locator).toHaveText(expected) failed"), healthy=False)

    assert verdict.category is Category.ENVIRONMENT
    assert "health probe" in verdict.reason


def test_network_errors_from_the_page_mean_environment() -> None:
    network = (NetworkError("GET", "http://a/api/tags", status=503),)

    verdict = classify(failure("Error: expect(locator).toBeVisible() failed", network), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.ENVIRONMENT, Confidence.HIGH)
    assert "503" in verdict.reason


@pytest.mark.parametrize(
    "error",
    [
        "Error: expect(received).toBe(expected)\n\nExpected: 200\nReceived: 502",
        "Error: register failed: 503 <html>Service Unavailable</html>",
    ],
)
def test_5xx_quoted_in_the_message_is_environment(error: str) -> None:
    assert classify(failure(error), healthy=None).category is Category.ENVIRONMENT


def test_4xx_quoted_in_the_message_is_not_environment() -> None:
    error = "Error: expect(received).toBe(expected)\n\nExpected: 403\nReceived: 404"

    assert classify(failure(error), healthy=True).category is Category.PRODUCT


def test_action_timeout_is_an_outdated_test_but_never_with_confidence() -> None:
    error = (
        "TimeoutError: locator.click: Timeout 3000ms exceeded.\nCall log:\n - waiting for getByRole('button')"
    )

    verdict = classify(failure(error), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.TEST, Confidence.LOW)


def test_value_mismatch_on_a_healthy_app_is_a_product_bug() -> None:
    error = 'Error: expect(locator).toHaveText(expected) failed\n\nExpected: "Title"\nReceived: "TITLE"'

    verdict = classify(failure(error), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.PRODUCT, Confidence.HIGH)


def test_value_mismatch_without_a_probe_drops_to_low_confidence() -> None:
    error = 'Error: expect(locator).toHaveText(expected) failed\n\nExpected: "a"\nReceived: "b"'

    verdict = classify(failure(error), healthy=None)

    assert (verdict.category, verdict.confidence) == (Category.PRODUCT, Confidence.LOW)
    assert "no health probe" in verdict.reason


def test_missing_element_in_an_assertion_is_product_with_low_confidence() -> None:
    error = "Error: expect(locator).toBeVisible() failed\n\nTimeout: 3000ms\nError: element(s) not found"

    verdict = classify(failure(error), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.PRODUCT, Confidence.LOW)
    assert "may be outdated" in verdict.reason


@pytest.mark.parametrize(
    "error", ["Test timeout of 30000ms exceeded.", "TypeError: undefined is not a function", ""]
)
def test_anything_else_is_unknown(error: str) -> None:
    verdict = classify(failure(error), healthy=True)

    assert (verdict.category, verdict.confidence) == (Category.UNKNOWN, Confidence.LOW)
