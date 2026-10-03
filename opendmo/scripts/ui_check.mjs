// Browser gate: visits every page, fails on console errors, page errors or any non-local request.
// usage: node scripts/ui_check.mjs http://127.0.0.1:8000
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require(`${process.env.NODE_PATH || ''}/playwright`); }
const base = (process.argv[2] || 'http://127.0.0.1:8000').replace(/\/$/, '');
const pages = ['/', '/observatory/', '/observatory/#capacity', '/observatory/#site', '/observatory/#sentiment', '/observatory/#heritage',
  '/climate-risk/', '/climate-risk/#hazards', '/climate-risk/#ecosystem', '/climate-risk/#resilience',
  '/future-economy/', '/future-economy/#leakage', '/future-economy/#forecast', '/future-economy/#scenarios', '/future-economy/#infrastructure',
  '/research-lab/', '/research-lab/#methodology', '/research-lab/#models', '/research-lab/#runs', '/research-lab/#briefs',
  '/research-lab/#publications', '/research-lab/#glossary', '/research-lab/#vrar', '/import/',
  ...['overview', 'data', 'destinations', 'backup', 'registry', 'runs', 'audit', 'settings', 'diagnostics'].map((t) => `/system/control-board/#${t}`)];
const browser = await pw.chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const ctx = await browser.newContext({ viewport: { width: Number(process.env.VW || 1280), height: 900 } });
const problems = [];
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') problems.push(`[console] ${page.url()} ${m.text()}`); });
page.on('pageerror', (e) => problems.push(`[pageerror] ${page.url()} ${e.message}`));
page.on('request', (r) => { const u = new URL(r.url()); if (!['127.0.0.1', 'localhost'].includes(u.hostname) && u.protocol !== 'data:' && u.protocol !== 'blob:') problems.push(`[remote] ${r.url()}`); });
for (const p of pages) {
  await page.goto(base + p, { waitUntil: 'networkidle' });
  await page.waitForTimeout(400);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  if (overflow) problems.push(`[h-scroll] ${p}`);
  if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/${p.replace(/[/#]+/g, '_') || 'home'}.png`, fullPage: false });
}
if (!process.env.NO_FLOWS) {
  // --- interaction flows (exercise the real backend) ---
  const fs = await import('fs');
  const os = await import('os');
  const path = await import('path');
  const step = async (name, fn) => { try { await fn(); } catch (e) { problems.push(`[flow] ${name}: ${e.message.split('\n')[0]}`); } };
  await step('first calculation', async () => {
    await page.goto(base + '/observatory/#capacity', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Run calculation' }).first().click();
    await page.getByText('PROVENANCE').first().waitFor({ timeout: 10000 });
  });
  await step('forecast compare', async () => {
    await page.goto(base + '/future-economy/#forecast', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'ALL', exact: true }).click();
    await page.getByRole('button', { name: 'Compare all three methods' }).click();
    await page.getByText('Back-test accuracy (hold-out)').waitFor({ timeout: 20000 });
  });
  await step('import wizard', async () => {
    const f = path.join(os.tmpdir(), 'opendmo-ui-check.csv');
    fs.writeFileSync(f, 'Month;Visitors;Occupancy\n2024-01;1000;55\n2024-02;1100;60\n2024-03;oops;61\n');
    await page.goto(base + '/import/', { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: '+ Create a new dataset' }).click();
    await page.locator('#w-name').fill(`UI check ${Date.now()}`);
    await page.getByRole('button', { name: 'Create dataset' }).click();
    await page.locator('input[type=file]').setInputFiles(f);
    await page.getByText('Layout guess').waitFor();
    await page.getByRole('button', { name: 'Next: map columns' }).click();
    await page.getByRole('button', { name: 'Run dry-run validation' }).click();
    await page.getByText('Row-level issues').waitFor();
    await page.getByLabel(/Skip invalid cells/).check();
    await page.getByRole('button', { name: 'Commit import' }).click();
    await page.getByText('Import complete').waitFor();
  });
  await step('policy brief', async () => {
    await page.goto(base + '/research-lab/#briefs', { waitUntil: 'networkidle' });
    await page.locator('input[aria-label^="Include RUN"]').first().check();
    await page.getByRole('button', { name: /Generate brief/ }).click();
    await page.locator('iframe[title="Brief preview"]').waitFor();
  });
  await step('command palette', async () => {
    await page.goto(base + '/', { waitUntil: 'networkidle' });
    await page.keyboard.press('Control+k');
    await page.getByLabel('Command', { exact: true }).fill('holt');
    await page.keyboard.press('Enter');
    await page.waitForURL(/future-economy/);
  });
  await step('theme toggle', async () => {
    await page.getByRole('button', { name: 'Toggle theme' }).click();
    const t = await page.evaluate(() => document.documentElement.dataset.theme);
    if (t !== 'light') throw new Error(`theme is ${t}`);
    if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/light.png` });
  });
}
await browser.close();
if (problems.length) { console.error(problems.join('\n')); process.exit(1); }
console.log(`UI check OK: ${pages.length} views, no console errors, no remote requests, no horizontal page scroll`);
