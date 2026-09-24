// Tests that are out of date: the app is fine, the test expects UI that no longer exists.
import { test, expect } from './fixtures';

test('drift: clicks a button that was renamed', async ({ page }) => {
  await page.goto('/editor');
  await page.getByRole('button', { name: 'Publish Now' }).click({ timeout: 3_000 });
});

test('drift: fills a field whose placeholder changed', async ({ page }) => {
  await page.goto('/editor');
  await page.getByPlaceholder('Title of the article').fill('x', { timeout: 3_000 });
});

test('drift: follows a nav link that was renamed', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Write Article' }).click({ timeout: 3_000 });
});

test('drift: checks for a heading that was renamed', async ({ page }) => {
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Account Settings' })).toBeVisible({ timeout: 3_000 });
});

test('drift: waits for a sidebar title that was renamed', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Trending Tags')).toBeVisible({ timeout: 3_000 });
});
