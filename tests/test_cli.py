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
    assert "health probe: healthy" in out
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


def test_empty_report_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text('{"suites": []}', encoding="utf-8")

    assert main([str(empty)]) == 0
    assert "Nothing to classify." in capsys.readouterr().out
