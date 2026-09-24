from pathlib import Path

from failure_classifier.report import Failure, load

MINIMAL = Path(__file__).parent / "fixtures" / "minimal-report.json"


def test_keeps_only_failed_and_flaky_tests_with_describe_path() -> None:
    failures = load(MINIMAL).failures

    assert [(f.title, f.project, f.status) for f in failures] == [
        ("comments > posts a comment", "chromium", "unexpected"),
        ("comments > deletes a comment", "firefox", "flaky"),
    ]


def test_error_is_the_first_failing_attempt_without_ansi_colors() -> None:
    failed, flaky = load(MINIMAL).failures

    assert failed.error.startswith("expect(locator).toHaveText() failed")
    assert flaky.error == "TimeoutError: locator.click: Timeout 5000ms exceeded."
    assert isinstance(failed, Failure)
