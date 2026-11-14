// Headless-Chrome smoke test of the deployed UI: runs a transcript, checks every tab renders, no JS errors.
// Setup: npm i puppeteer-core ; Usage: UI_URL=https://nexus-ops-coordinator.vercel.app CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" node tests/ui_smoke.mjs
import puppeteer from 'puppeteer-core';
const URL_ = process.env.UI_URL || 'https://nexus-ops-coordinator.vercel.app';
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const b = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
const p = await b.newPage(); await p.setViewport({ width: 1440, height: 900 });
const errs = []; p.on('pageerror', e => errs.push(e.message));
await p.goto(URL_, { waitUntil: 'networkidle2' });
await p.$eval('#inp-tr', e => e.value = "Dana: We decided to move the portal launch to May 20. Omar owns the data import, due May 5. We cannot store card numbers. Nobody has said who writes the user docs.");
await p.$eval('#inp-ru', e => e.value = "Security review required before any launch.");
await p.click('#run-btn');
await p.waitForFunction(() => document.getElementById('run-btn').textContent.trim() !== 'Running…', { timeout: 420000 });
const r = await p.evaluate(() => ({ tasks: S.final?.tasks?.length || 0, board: document.querySelectorAll('#board-cols [class*=card]').length,
  timeline: (document.getElementById('tl-content') || { innerHTML: '' }).innerHTML.length, facts: document.querySelectorAll('#edit-facts > *').length }));
console.log(r, 'jsErrors:', errs);
const ok = r.tasks > 0 && r.board > 0 && r.timeline > 0 && r.facts > 0 && errs.length === 0;
console.log(ok ? 'PASS' : 'FAIL'); await b.close(); process.exit(ok ? 0 : 1);
