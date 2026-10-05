// NODE_PATH may point to the bundled Playwright installation.
// Uses a separate Chrome profile and reads the board without changing tasks.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { mkdtempSync, rmSync } = require('node:fs');
const { join } = require('node:path');
const { tmpdir } = require('node:os');
(async () => {
  const profile = mkdtempSync(join(tmpdir(), 'task-matrix-pwa-'));
  let context;
  try {
    context = await chromium.launchPersistentContext(profile, {
      headless: true,
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    });
    const base = process.env.TASK_MATRIX_TEST_URL || 'http://127.0.0.1:8765';
    const page = await context.newPage();
    await page.goto(base);
    await page.evaluate(() => navigator.serviceWorker.ready);
    await page.reload();
    assert(await page.evaluate(() => !!navigator.serviceWorker.controller));
    const manifest = await (await page.request.get(`${base}/manifest.webmanifest`)).json();
    assert.equal(manifest.display, 'standalone');
    for (const icon of manifest.icons) {
      assert.equal(await page.evaluate(async src => {
        const image = new Image(); image.src = src; await image.decode();
        return `${image.naturalWidth}x${image.naturalHeight}`;
      }, icon.src), icon.sizes);
    }
    const cdp = await context.newCDPSession(page);
    await cdp.send('Page.enable');
    assert.deepEqual((await cdp.send('Page.getInstallabilityErrors')).installabilityErrors, []);
    assert.equal((await page.request.get(`${base}/assets/../server.py`)).status(), 404);
    await context.setOffline(true);
    await page.reload();
    await page.getByRole('heading', { name: 'Task Matrix is unavailable' }).waitFor();
    await context.setOffline(false);
    await page.getByRole('button', { name: 'Try again' }).click();
    await page.waitForFunction(() => document.title === 'Task Matrix' && !!navigator.serviceWorker.controller);
    console.log('Passed: PWA installability, icons, service worker, static route boundaries, offline fallback and recovery.');
  } finally {
    if (context) await context.close();
    rmSync(profile, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exit(1); });
