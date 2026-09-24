// Environment problems seen from the browser: the API is unreachable or answers 5xx.
import { test, expect } from './fixtures';

test('env: API refuses connections while loading the feed', async ({ page }) => {
  await page.route('**/api/articles?**', (route) => route.abort('connectionrefused'));

  await page.goto('/');

  await expect(page.locator('app-article-preview').first()).toBeVisible({ timeout: 3_000 });
});

test('env: API times out while loading tags', async ({ page }) => {
  await page.route('**/api/tags', (route) => route.abort('timedout'));

  await page.goto('/');

  await expect(page.locator('.sidebar .tag-pill').first()).toBeVisible({ timeout: 3_000 });
});

test('env: API answers 503 on the article page', async ({ page, myApi }) => {
  const article = await myApi.createArticleOk({ title: `env ${Date.now()}`, description: 'd', body: 'b' });
  await page.route(`**/api/articles/${article.slug}`, (route) => route.fulfill({ status: 503, body: 'Service Unavailable' }));

  await page.goto(`/article/${article.slug}`);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(article.title, { timeout: 3_000 });
});
