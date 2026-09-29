// Run with Node and playwright available (NODE_PATH may point to its installation).
// Uses a temporary task store; never writes to the installed board's data.
const assert = require('node:assert/strict');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

(async () => {
  const directory = mkdtempSync(join(tmpdir(), 'task-matrix-test-'));
  const port = 18765;
  const base = `http://127.0.0.1:${port}`;
  const server = spawn('python3', [resolve(__dirname, '../plugin/server.py'), 'web'], {
    env: { ...process.env, TASK_MATRIX_DATA: join(directory, 'tasks.json'), TASK_MATRIX_PORT: String(port) },
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  let serverError = '';
  const serverClosed = new Promise(resolve => server.once('close', resolve));
  server.stderr.on('data', chunk => { serverError += chunk; });
  let browser;
  try {
    for (let i = 0; ; i++) {
      if (server.exitCode !== null) throw new Error(serverError);
      try { if ((await fetch(`${base}/health`)).ok) break; } catch {}
      if (i === 50) throw new Error('Test server did not start');
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    const upsert = ['a', 'b', 'c', 'd'].map((id, i) => ({
      id, name: `${id.toUpperCase()}: Test task`, importance: 'high', urgency: 'high',
      doing: id !== 'b', today: id === 'c', description: 'First line\nSecond line',
      createdAt: `2026-01-0${i + 1}T00:00:00Z`, dueDate: `2026-10-0${i + 1}`,
    }));
    assert.equal((await fetch(`${base}/api/tasks`, { method: 'POST', body: JSON.stringify({ upsert }) })).status, 200);
    browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    page.setDefaultTimeout(10000);
    // The service allows the installed board's fixed Origin; tests use another port.
    const allowTestOrigin = async route => route.fulfill({ response: await route.fetch({ headers: { ...route.request().headers(), origin: 'http://127.0.0.1:8765' } }) });
    await page.route('**/api/tasks', allowTestOrigin);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    const cell = '#cell-high-high';
    const card = id => `${cell} .task-card[data-id="${id}"]`;
    const ids = async (selector = cell) => page.locator(`${selector} .task-card`).evaluateAll(els => els.map(el => el.dataset.id));
    const check = async (expected, selector = cell) => {
      console.log('Checking', selector, expected.join(','));
      await page.waitForFunction(({ selector, expected }) => JSON.stringify([...document.querySelectorAll(`${selector} .task-card`)].map(el => el.dataset.id)) === JSON.stringify(expected), { selector, expected });
      assert.deepEqual(await ids(selector), expected);
    };
    const drag = async (source, target, after = false) => {
      const bounds = await page.locator(target).boundingBox();
      const saved = page.waitForResponse(response => response.url().endsWith('/api/tasks') && response.request().method() === 'POST');
      await page.locator(source).dragTo(page.locator(target), { targetPosition: { x: 35, y: after ? bounds.height - 4 : 4 } });
      const response = await saved;
      assert.equal(response.status(), failingSave ? 500 : 200);
    };
    let failingSave = false;
    await check(['a', 'b', 'c', 'd']);
    await drag(card('d'), card('a'));
    await check(['d', 'a', 'b', 'c']);
    await page.reload();
    await check(['d', 'a', 'b', 'c']);
    await drag(card('d'), card('c'), true);
    await check(['a', 'b', 'c', 'd']);
    await page.locator('.filter[data-filter="doing"]').click();
    await check(['a', 'c', 'd']);
    await drag(card('d'), card('a'));
    await check(['d', 'a', 'c']);
    await page.locator('.filter[data-filter="all"]').click();
    await check(['d', 'a', 'b', 'c']);
    await page.locator(`${card('d')} .edit-task`).click();
    await page.locator('#task-name').fill('D: Renamed');
    const edited = page.waitForResponse(response => response.url().endsWith('/api/tasks') && response.request().method() === 'POST');
    await page.locator('#task-form button[type="submit"]').click();
    await edited;
    await check(['d', 'a', 'b', 'c']);
    await drag(card('d'), '#cell-medium-medium');
    await check(['d'], '#cell-medium-medium');
    await check(['a', 'b', 'c']);
    await drag('#cell-medium-medium .task-card[data-id="d"]', card('b'));
    await check(['a', 'd', 'b', 'c']);
    await drag(card('a'), '#today-panel');
    await check(['a', 'c'], '#today-panel');
    await check(['a', 'd', 'b', 'c']);
    await drag('#today-panel .task-card[data-id="a"]', card('c'), true);
    await check(['d', 'b', 'c', 'a']);
    await check(['c'], '#today-panel');
    await page.locator(`${card('c')} .description-toggle`).click();
    assert.equal(await page.locator('#today-panel .description-toggle').getAttribute('aria-expanded'), 'true');
    failingSave = true;
    await page.route('**/api/tasks', route => route.request().method() === 'POST'
      ? route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"Test save failure"}' })
      : route.fallback());
    await drag(card('a'), card('d'));
    await check(['d', 'b', 'c', 'a']);
    await page.unroute('**/api/tasks');
    await page.reload();
    await check(['d', 'b', 'c', 'a']);
    assert.deepEqual(errors, []);
    console.log('PASS: real drag/drop, reload persistence, both directions, filters, edits, cross-box and empty-box moves, Today, descriptions, failed-save rollback; no browser errors.');
  } finally {
    if (browser) await browser.close();
    server.kill();
    await serverClosed;
    rmSync(directory, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
