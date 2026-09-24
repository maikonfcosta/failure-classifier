"""Checks that the dataset itself is sound before any classifier is measured against it."""

from collections import Counter

from tests.dataset import cases


def test_dataset_has_at_least_20_labeled_failures_in_every_category() -> None:
    labels = Counter(case.truth for case in cases())

    assert sum(labels.values()) >= 20
    assert set(labels) == {"environment", "test", "product"}
    assert min(labels.values()) >= 4


def test_every_failure_has_an_error_message() -> None:
    assert all(case.failure.error for case in cases())


def test_browser_side_outages_carry_network_errors_and_the_rest_do_not() -> None:
    app_up = [case for case in cases() if case.scenario == "app-up"]

    for case in app_up:
        has_network_errors = bool(case.failure.network_errors)
        assert has_network_errors == (case.truth == "environment"), case.failure.title


def test_health_probe_matches_the_scenario() -> None:
    health = {case.scenario: case.healthy for case in cases()}

    assert health == {"app-up": True, "api-down": False, "web-down": False}
