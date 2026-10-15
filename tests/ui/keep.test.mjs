// Régression « Garder celle-ci » (corrigée en 8ce12d4) : la galerie rechargée pendant que la visionneuse est ouverte
// (une génération de la page qui se termine) ne doit pas faire supprimer l'image gardée avec les autres du lot.
// La comparaison se fait par nom ; par identité d'objet, l'image gardée ne correspondait plus et partait aussi.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const lotNames = async id => (await (await fetch(bench.url + '/api/history')).json())
  .filter(it => it.lot && it.lot.id === id).sort((a, b) => a.lot.rank - b.lot.rank).map(it => it.name);

test('garder l\'image 2 d\'un lot de variantes après un rechargement de la galerie', async () => {
  const body = { mode: 't2i', prompt: 'variantes à départager', width: 512, height: 512, steps: 2, cfg: 1, seed: -1,
    preview: false, preview_interval: 5, ref_images: [], init_image: null, mask_image: null, strength: 1, count: 3 };
  const reply = await page.eval(`fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: ${JSON.stringify(JSON.stringify(body))} }).then(r => r.json())`);
  const lot = reply.lot.id;
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`, { what: 'lot terminé' });
  const names = await lotNames(lot);
  assert.equal(names.length, 3);

  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`!!$('histGrid').querySelector('button[data-name="${names[1]}"]')`, { what: 'image 2 dans la galerie' });
  await page.click(`#histGrid button[data-name="${names[1]}"]`);
  await page.waitFor(`$('viewer').classList.contains('on') && !$('vKeep').hidden`, { what: 'visionneuse ouverte, « Garder celle-ci » visible' });

  await page.eval(`(async () => { const before = histItems; await loadHistory(); return histItems !== before; })()`)
    .then(reloaded => assert.equal(reloaded, true, 'la galerie a été rechargée (nouveaux objets)'));

  await page.click('#vKeep');
  await page.waitFor(`$('askSheet').classList.contains('on')`, { what: 'confirmation demandée' });
  await page.click('#askYes');
  await page.waitFor(`$('toast').textContent.startsWith('Image gardée') || $('toast').textContent.startsWith('Suppression')`,
    { what: 'suppression terminée' });

  assert.deepEqual(await lotNames(lot), [names[1]], 'seule l\'image gardée reste');
  page.assertNoErrors();
});
