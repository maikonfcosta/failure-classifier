# Spec

## Goal

When a test pipeline goes red, tell whether the product is broken, the environment is down, or the test itself is out of date. Only the first one should block a merge.

This is the open version of a classifier I wrote at work, rebuilt from scratch against public data.

## Why a naive version does not work

Before writing this spec I broke [playwright-reference-suite](https://github.com/maikonfcosta/playwright-reference-suite) on purpose, three ways, and looked at what Playwright reports:

| What I broke | Error Playwright reported |
|---|---|
| Stopped the API container | `Expected: 200 Received: 502` (looks like a product assertion) |
| Stopped the web container | `page.goto: net::ERR_CONNECTION_REFUSED` |
| Renamed a button the test clicks | `locator.click: Timeout 3000ms exceeded ... waiting for getByRole(...)` |
| API returned empty data (product bug) | `expect(locator).toBeVisible() failed ... element(s) not found` |

Two lessons:

1. **The error message alone is ambiguous.** An environment outage showed up as a failed assertion (502), and a product bug and a renamed selector both end in "element not found".
2. **The classifier needs context the report does not have**: was the app healthy when the test failed, and did the page get 5xx responses during the test.

So the tool reads the Playwright JSON report plus two optional signals, and it is allowed to answer "I don't know".

## Inputs

| Input | Required | Where it comes from |
|---|---|---|
| Playwright JSON report | yes | `json` reporter |
| Health probe result | no | a CI step that hits the app's health URL right after the tests, saved as JSON |
| Network errors per test | no | a small Playwright fixture shipped in this repo that attaches `network-errors.json` (responses ≥ 500 and failed requests) to each test |

## Output

For every failed or flaky test: `category`, `confidence` (`high` / `low`), `reason` (the rule that fired, in plain words) and the first error line.

Categories:

| Category | Meaning | Blocks merge |
|---|---|---|
| `environment` | app or dependency was down or returning 5xx | no, retry the pipeline |
| `test` | the test is out of date (selector, flow changed) while the app was healthy | no, fix the test |
| `product` | the app was healthy and a business assertion failed | yes |
| `unknown` | signals disagree or are missing | yes (safe default) |

Written as a table to the GitHub job summary and as JSON to a file. Exit code: 1 if any `product` or `unknown`, 0 otherwise. Configurable.

## Rules (first version, deterministic, no LLM)

Evaluated in order, first match wins:

1. Connection refused / DNS / `ERR_CONNECTION_*` in the error → `environment`, high.
2. Health probe says unhealthy → `environment`, high.
3. Network errors attachment has 5xx or failed requests → `environment`, high.
4. Error is an action timeout waiting for a locator (`locator.click`, `fill`, ...) and the app was healthy → `test`, low. Low because a product bug that hides the element looks the same.
5. Error is an `expect(...)` assertion and the app was healthy with no 5xx → `product`, high.
6. Anything else → `unknown`.

Rule 4 is the honest limit of this tool. The README will say so.

## Delivery

- Python 3.12+, standard library only at runtime, pytest for tests.
- CLI: `failure-classifier report.json [--health health.json] [--summary] [--fail-on product,unknown]`.
- GitHub composite action wrapping the CLI.
- The Playwright fixture for network errors, as a copy-paste TypeScript file with its own test.

## Out of scope (for now)

- LLM-based diagnosis (that is the next project, `ai-ci-triage`).
- Reading trace.zip files.
- Frameworks other than Playwright.

## Done when

- A labeled set of at least 20 real failures, produced by breaking playwright-reference-suite in controlled ways, is classified with no wrong `high` answer. Every miss is `low` or `unknown`, and the README reports the numbers.
- Classifier code has at least 90% test coverage.
- The action runs in playwright-reference-suite's CI and its table shows up in the job summary.
