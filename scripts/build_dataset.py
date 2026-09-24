"""Builds the labeled dataset by breaking playwright-reference-suite on purpose.

Usage: uv run python scripts/build_dataset.py ../playwright-reference-suite

Needs the suite's app running (`npm run app:up` in the suite) and its dependencies installed.
Each scenario writes dataset/<scenario>/{report.json, health.json, expected.json}.
Nothing is committed to the suite: the dataset specs are copied in and removed at the end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
HEALTH_URL = "http://localhost:4200/api/tags"
SHELL = os.name == "nt"  # npx and docker are .cmd shims on Windows


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(
        cmd, cwd=cwd, shell=SHELL, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def probe() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as res:
            return {"url": HEALTH_URL, "ok": 200 <= res.status < 300, "status": res.status}
    except urllib.error.HTTPError as err:
        return {"url": HEALTH_URL, "ok": False, "status": err.code}
    except OSError as err:
        return {"url": HEALTH_URL, "ok": False, "error": type(err).__name__}


def playwright(suite: Path, args: list[str]) -> dict[str, Any]:
    cmd = ["npx", "playwright", "test", *args, "--retries=0", "--reporter=json"]
    out = subprocess.run(
        cmd,
        cwd=suite,
        shell=SHELL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CI": ""},
    ).stdout
    report: dict[str, Any] = json.loads(out[out.index("{") :])
    # Absolute paths of the machine that built the dataset are noise (and personal); keep them relative.
    text = json.dumps(report)
    for form in (str(suite), suite.as_posix()):
        text = text.replace(json.dumps(form)[1:-1], "<suite>")
    relative: dict[str, Any] = json.loads(text)
    return relative


def truth_from_title(title: str) -> str:
    prefix = title.split(":", 1)[0]
    return {"drift": "test", "product": "product", "env": "environment"}[prefix]


def failed_titles(report: dict[str, Any]) -> list[str]:
    titles: list[str] = []

    def walk(suites: list[dict[str, Any]]) -> None:
        for suite in suites:
            for spec in suite.get("specs", []):
                if any(t["status"] == "unexpected" for t in spec["tests"]):
                    titles.append(spec["title"])
            walk(suite.get("suites", []))

    walk(report["suites"])
    return titles


def save(name: str, report: dict[str, Any], health: dict[str, Any], truth: dict[str, str]) -> None:
    folder = DATASET / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (folder / "health.json").write_text(json.dumps(health, indent=1), encoding="utf-8")
    (folder / "expected.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{name}: {len(truth)} failures labeled, health ok={health['ok']}")


def main(suite: Path) -> None:
    target = suite / "tests" / "e2e" / "dataset"
    shutil.copytree(DATASET / "specs", target, dirs_exist_ok=True)
    shutil.copy(ROOT / "playwright" / "network-errors.ts", target / "network-errors.ts")
    try:
        # 1. App healthy: outdated tests, product bugs and browser-side outages, labeled by title prefix.
        report = playwright(suite, ["tests/e2e/dataset", "--project=chromium"])
        save("app-up", report, probe(), {t: truth_from_title(t) for t in failed_titles(report)})

        # 2. API container stopped: the suite's real tests, without the network recorder.
        run(["docker", "compose", "stop", "api"], suite)
        real = [
            "tests/api/health.spec.ts",
            "tests/api/auth.spec.ts",
            "tests/e2e/home.spec.ts",
            "tests/e2e/comment.spec.ts",
        ]
        report = playwright(suite, [*real, "--project=api", "--project=chromium", "--no-deps"])
        save("api-down", report, probe(), {t: "environment" for t in failed_titles(report)})
        run(["docker", "compose", "start", "api"], suite)

        # 3. Web container stopped: nothing answers on the app port.
        run(["docker", "compose", "stop", "web"], suite)
        report = playwright(
            suite, ["tests/e2e/home.spec.ts", "tests/e2e/session.spec.ts", "--project=chromium", "--no-deps"]
        )
        save("web-down", report, probe(), {t: "environment" for t in failed_titles(report)})
    finally:
        run(["docker", "compose", "start", "api", "web"], suite)
        shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
