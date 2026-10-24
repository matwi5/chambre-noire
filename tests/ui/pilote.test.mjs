// Aides du pilote (driver.mjs) et délais des tests d'interface : page.leaks trouve un marqueur laissé dans une variable
// globale, un texte caché, un attribut ou un élément détaché ; bench.disk voit un fichier écrit ; page.eval et
// bench.idle échouent dans leur délai ; un test bloqué lancé par check.py échoue dans le délai par test, sans laisser
// Chrome ni le serveur du banc.
//   venv/bin/python tests/check.py --quick --ui tests/ui/pilote.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok')`, { what: 'moteur prêt affiché' });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const MARKS = ['zpLet', 'zpVar', 'zpCache', 'zpHidden', 'zpAttr', 'zpDetached'];

test('page.leaks : un marqueur laissé dans l\'état global ou caché dans la page est trouvé', async () => {
  assert.deepEqual(await page.leaks(MARKS), [], 'page neuve : rien');
  // fuites volontaires : let de premier niveau (Map dans un objet), var globale (Set), texte caché, attribut, élément
  // détaché gardé en mémoire
  await page.eval(`(() => {
    const s = document.createElement('script');
    s.textContent = "let zpPlanted = { cache: new Map([['k', { deep: ['zpLet'] }], ['zpCache', 1]]) };";
    document.head.append(s);
    window.zpGlobal = new Set(['x', 'zpVar']);
    const h = document.createElement('div'); h.hidden = true; h.textContent = 'zpHidden'; document.body.append(h);
    document.body.dataset.trace = 'zpAttr';
    window.zpKept = document.createElement('p'); zpKept.textContent = 'zpDetached';
  })()`);
  const found = await page.leaks(MARKS);
  for (const m of MARKS) assert.ok(found.some(f => f.endsWith(' : ' + m)), `${m} non trouvé : ${found.join(' ; ')}`);
  assert.ok(found.includes('mémoire zpPlanted.cache.get(k).deep[0] : zpLet'), found.join(' ; '));
  const skipped = await page.leaks(['zpLet', 'zpVar'], { skip: ['zpPlanted'] });
  assert.deepEqual(skipped, ['mémoire zpGlobal[1] : zpVar']);
  await page.goto(bench.url + '/');
  assert.deepEqual(await page.leaks(MARKS), [], 'page rechargée : plus rien');
  page.assertNoErrors();
});

test('bench.disk : une image enregistrée est vue, rien quand rien n\'est écrit', async () => {
  await page.waitFor(`$('lamp').classList.contains('ok')`, { what: 'moteur prêt affiché' });
  const disk = bench.disk();
  assert.deepEqual(disk.written(), []);
  await page.generate('zp1 disque');
  await bench.idle();
  const written = disk.written();
  assert.ok(written.length > 0 && written.some(f => f.startsWith('outputs')), written.join(', '));
  page.assertNoErrors();
});

test('délais : page.eval et bench.idle échouent au lieu d\'attendre sans fin', async () => {
  await assert.rejects(page.eval('new Promise(() => {})', { timeout: 300 }), /pas de réponse après 0.3 s/);
  assert.equal(await page.eval(`postJson('/api/generate', { prompt: 'HOLD=pilote zp2', width: 512, height: 512,
    steps: 2, cfg: 1, seed: -1, ref_images: [] }).then(r => r.status)`), 202);
  await assert.rejects(bench.idle({ timeout: 300 }), /Mac au repos/);
  bench.release('pilote');
  await bench.idle();
  page.assertNoErrors();
});

test('check.py : un test bloqué échoue dans le délai par test, sans Chrome ni banc restants', () => {
  const journal = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-pilote-')), 'check.log');
  const start = Date.now();
  const r = spawnSync(process.env.PYTHON || 'python3', ['tests/check.py', '--no-bench', '--ui',
    'tests/ui/fixtures/bloque.mjs'], { encoding: 'utf8', timeout: 120000,
    env: { ...process.env, QWEN_UI_TEST_TIMEOUT: '5000', QWEN_CHECK_JOURNAL: journal } });
  const out = r.stdout + r.stderr;
  fs.rmSync(path.dirname(journal), { recursive: true, force: true });
  assert.equal(r.status, 1, out);
  assert.match(out, /test timed out after 5000ms/);
  assert.ok(Date.now() - start < 60000, `trop long : ${(Date.now() - start) / 1000} s`);
  const pids = JSON.parse(out.match(/PIDS (\[[\d, ]+\])/)[1]);
  assert.equal(pids.length, 2);
  const alive = pids.filter(pid => { try { process.kill(pid, 0); return true; } catch { return false; } });
  assert.deepEqual(alive, [], 'Chrome ou le serveur du banc encore là');
});
