// Copy this file into a Playwright project and build your `test` on top of it:
//
//   import { withNetworkErrors } from './network-errors';
//   export const test = withNetworkErrors(base);
//
// Every test then attaches `network-errors` (JSON) when the page saw a 5xx response or a failed request.
// failure-classifier reads that attachment to tell an environment problem from a product bug.

import type { Page, TestType } from '@playwright/test';

type NetworkError = { method: string; url: string; status?: number; failure?: string };

export function withNetworkErrors<T extends { page: Page }, W extends object>(base: TestType<T, W>) {
  return base.extend<{ recordNetworkErrors: void }>({
    recordNetworkErrors: [
      async ({ page }, use, testInfo) => {
        const errors: NetworkError[] = [];
        page.on('response', (res) => {
          if (res.status() >= 500) errors.push({ method: res.request().method(), url: res.url(), status: res.status() });
        });
        page.on('requestfailed', (req) => {
          errors.push({ method: req.method(), url: req.url(), failure: req.failure()?.errorText });
        });

        await use();

        if (errors.length > 0) {
          await testInfo.attach('network-errors', { body: JSON.stringify(errors), contentType: 'application/json' });
        }
      },
      { auto: true },
    ],
  });
}
