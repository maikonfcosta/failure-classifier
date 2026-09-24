import json
from pathlib import Path

import pytest

from failure_classifier.cli import main

DATASET = Path(__file__).resolve().parent.parent / "dataset"
MINIMAL = Path(__file__).parent / "fixtures" / "minimal-report.json"


def test_product_failure_blocks_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [str(DATASET / "app-up" / "report.json"), "--health", str(DATASET / "app-up" / "health.json")]
    )

    out = capsys.readouterr().out
    assert code == 1
    assert "Health probe: healthy." in out
    assert "| product | high |" in out


def test_outage_does_not_block_when_the_probe_confirms_it() -> None:
    folder = DATASET / "api-down"

    assert main([str(folder / "report.json"), "--health", str(folder / "health.json")]) == 0


def test_same_outage_blocks_without_a_probe_because_the_cause_is_unknown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(DATASET / "api-down" / "report.json")])

    assert code == 1
    assert "| unknown | low |" in capsys.readouterr().out


def test_fail_on_can_be_turned_off() -> None:
    assert main([str(DATASET / "app-up" / "report.json"), "--fail-on", ""]) == 0


def test_writes_json_and_github_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    out = tmp_path / "verdicts.json"

    main([str(MINIMAL), "--json", str(out), "--fail-on", ""])

    verdicts = json.loads(out.read_text(encoding="utf-8"))
    assert [v["category"] for v in verdicts] == ["product", "test"]
    assert verdicts[1]["location"] == "e2e/articles.spec.ts:20"
    assert summary.read_text(encoding="utf-8").startswith("## Failure classification")


FIXTURES = Path(__file__).parent / "fixtures"


def test_run_with_no_tests_found_is_not_green(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(FIXTURES / "no-tests-report.json")])

    assert code == 1
    assert "The run itself failed:** Error: No tests found" in capsys.readouterr().out


def test_empty_report_without_errors_is_not_green_either(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text('{"suites": [], "stats": {}}', encoding="utf-8")

    assert main([str(empty)]) == 1
    assert "No test ran" in capsys.readouterr().out


def test_all_passing_run_is_green(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    passing = tmp_path / "passing.json"
    passing.write_text(
        '{"suites": [], "stats": {"expected": 3, "unexpected": 0, "flaky": 0}}', encoding="utf-8"
    )

    assert main([str(passing)]) == 0
    assert "Nothing to classify." in capsys.readouterr().out


def test_broken_setup_blocks_and_explains_the_skipped_tests(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(FIXTURES / "setup-failed-report.json")])

    out = capsys.readouterr().out
    assert code == 1
    assert "1 tests were skipped" in out
    assert "broken global setup" in out


def test_flaky_tests_are_reported_but_do_not_block(tmp_path: Path) -> None:
    report = json.loads(MINIMAL.read_text(encoding="utf-8"))
    comments = report["suites"][0]["suites"][0]
    comments["specs"] = [s for s in comments["specs"] if s["tests"][0]["status"] == "flaky"]
    only_flaky = tmp_path / "flaky.json"
    only_flaky.write_text(json.dumps(report), encoding="utf-8")

    assert main([str(only_flaky)]) == 0


@pytest.mark.parametrize(
    ("content", "message"),
    [("not json", "cannot read"), ('{"results": []}', "not a Playwright JSON report")],
)
def test_bad_report_exits_2_with_a_clear_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str, message: str
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(content, encoding="utf-8")

    assert main([str(bad)]) == 2
    assert message in capsys.readouterr().err


def test_missing_report_exits_2(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.json")]) == 2


def test_bad_health_probe_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    probe = tmp_path / "health.json"
    probe.write_text('{"status": 200}', encoding="utf-8")

    assert main([str(MINIMAL), "--health", str(probe)]) == 2
    assert "health probe" in capsys.readouterr().err


def test_unknown_fail_on_category_exits_2() -> None:
    assert main([str(MINIMAL), "--fail-on", "product,flaky"]) == 2


def test_on_github_actions_each_verdict_becomes_an_annotation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    main([str(MINIMAL)])

    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("::")]
    assert lines[0].startswith("::error title=product (low)%3A comments > posts a comment::")
    # Flaky tests never block, so they are warnings even when their category would.
    assert lines[1].startswith("::warning title=test (low)%3A comments > deletes a comment::")
