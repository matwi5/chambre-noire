// Saisie, dans la vue du téléphone : photos choisies d'un coup en Éditer.
//   node --test tests/ui/saisie.test.mjs   (ou : venv/bin/python tests/check.py --ui)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startBench, launchChrome } from './driver.mjs';

// PNG de 1×1 pixel : chaque photo du test en est une copie, sous son propre nom
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
let bench, chrome, page, dir;

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-photos-'));
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
  if (dir) fs.rmSync(dir, { recursive: true, force: true });
});

// page neuve sur l'onglet Éditer, sans image
async function freshEdit() {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.click('#tabbar [data-pane="edit"]');
  await page.waitFor(`$('pane-edit').classList.contains('active')`);
}

function photos(n) {
  return Array.from({ length: n }, (_, i) => {
    const file = path.join(dir, `photo-${String(i + 1).padStart(2, '0')}.png`);
    fs.writeFileSync(file, PNG);
    return file;
  });
}

test('Éditer : trois photos choisies d\'un coup sont toutes ajoutées, dans l\'ordre', async () => {
  await freshEdit();
  await page.setFiles('#edit_files', photos(3));
  await page.waitFor(`$('edit_thumbs').children.length === 3`, { what: 'trois vignettes', timeout: 5000 });
  assert.deepEqual(await page.eval(`editImages.map(x => x.name)`), ['photo-01.png', 'photo-02.png', 'photo-03.png']);
  page.assertNoErrors();
});

test('Éditer : sur douze photos choisies, dix sont ajoutées et le surplus est annoncé', async () => {
  await freshEdit();
  const files = photos(12);
  await page.setFiles('#edit_files', files);
  await page.waitFor(`$('toast').classList.contains('on') && $('toast').textContent.includes('2 non ajoutées')`,
    { what: 'message du surplus', timeout: 5000 });
  assert.deepEqual(await page.eval(`editImages.map(x => x.name)`), files.slice(0, 10).map(f => path.basename(f)));
  assert.equal(await page.eval(`$('edit_thumbs').children.length`), 10);
  page.assertNoErrors();
});
