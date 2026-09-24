"""Measures the rules against the labeled dataset. These numbers go into the README."""

from collections import Counter

from failure_classifier.classify import Category, Confidence, classify
from tests.dataset import Case, cases


def verdicts() -> list[tuple[Case, Category, Confidence]]:
    return [(case, *_pair(case)) for case in cases()]


def _pair(case: Case) -> tuple[Category, Confidence]:
    verdict = classify(case.failure, case.healthy)
    return verdict.category, verdict.confidence


def test_no_confident_answer_is_wrong() -> None:
    wrong_high = [
        (case.failure.title, case.truth, category)
        for case, category, confidence in verdicts()
        if confidence is Confidence.HIGH and category != case.truth
    ]

    assert wrong_high == []


def test_accuracy_report() -> None:
    results = Counter(
        "high right"
        if confidence is Confidence.HIGH and category == case.truth
        else "low right"
        if category == case.truth
        else "low wrong or unknown"
        for case, category, confidence in verdicts()
    )
    print("\n", dict(results))

    assert results["high right"] >= len(cases()) // 2


def test_without_health_probe_an_api_outage_is_never_called_product_with_confidence() -> None:
    for case in cases():
        if case.scenario != "api-down":
            continue
        verdict = classify(case.failure, healthy=None)
        assert not (verdict.category is Category.PRODUCT and verdict.confidence is Confidence.HIGH)
