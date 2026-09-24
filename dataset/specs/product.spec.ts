// Product bugs: the app is up and answers, but with the wrong data. Simulated by rewriting API responses.
import { test, expect } from './fixtures';
import { newArticle } from '../../../src/data/factory';

test('product: popular tags come back empty', async ({ page, myApi }) => {
  await myApi.createArticleOk(newArticle({ tagList: ['dataset'] }));
  await page.route('**/api/tags', (route) => route.fulfill({ json: { tags: [] } }));

  await page.goto('/');

  await expect(page.locator('.sidebar .tag-pill').first()).toBeVisible({ timeout: 3_000 });
});

test('product: article title is saved with the wrong text', async ({ page, myApi }) => {
  const article = await myApi.createArticleOk(newArticle());
  await page.route(`**/api/articles/${article.slug}`, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.article.title = body.article.title.toUpperCase();
    await route.fulfill({ response: res, json: body });
  });

  await page.goto(`/article/${article.slug}`);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(article.title, { timeout: 3_000 });
});

test('product: article shows the wrong author', async ({ page, api, otherUser }) => {
  const article = await api.as(otherUser.token).createArticleOk(newArticle());
  await page.route(`**/api/articles/${article.slug}`, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.article.author.username = 'someone-else';
    await route.fulfill({ response: res, json: body });
  });

  await page.goto(`/article/${article.slug}`);

  await expect(page.locator('.banner .author')).toHaveText(otherUser.username, { timeout: 3_000 });
});

test('product: new comment disappears after posting', async ({ page, api, otherUser }) => {
  const article = await api.as(otherUser.token).createArticleOk(newArticle());
  await page.route('**/comments', (route) =>
    route.request().method() === 'GET' ? route.fulfill({ json: { comments: [] } }) : route.continue(),
  );

  await page.goto(`/article/${article.slug}`);
  await page.getByPlaceholder('Write a comment...').fill('dataset comment');
  await page.getByRole('button', { name: 'Post Comment' }).click();
  await page.reload();

  await expect(page.locator('app-article-comment .card-text')).toHaveText(['dataset comment'], { timeout: 3_000 });
});
