// Garder et Jeter visent une image par son nom, jamais par l'objet affiché (règle née de la régression « Garder
// celle-ci », corrigée en 8ce12d4) : la pile rechargée pendant que la visionneuse est ouverte (une autre image qui
// arrive, un tri sur un autre appareil) donne de nouveaux objets, et c'est toujours l'image vue qui est gardée ou
// jetée, les autres restant dans la pile.
//   venv/bin/python tests/check.py --quick --ui tests/ui/keep.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

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

// noms des images du lot, par rang, dans la pile ou dans les Tirages
const lotNames = async (path, id) => (await bench.api(path)).filter(it => it.lot && it.lot.id === id)
  .sort((a, b) => a.lot.rank - b.lot.rank).map(it => it.name);
// lot de 3 variantes lancé hors de l'interface, terminé, dans la pile affichée ; visionneuse ouverte sur l'image 2,
// puis la pile relue (nouveaux objets) ; renvoie l'identifiant du lot et les noms
async function viewSecond(prompt) {
  const reply = await page.eval(`postJson('/api/generate', { mode: 't2i', prompt: ${JSON.stringify(prompt)}, width: 512,
    height: 512, steps: 2, cfg: 1, seed: -1, preview: false, ref_images: [], count: 3 }).then(r => r.json())`);
  const lot = reply.lot.id;
  await bench.idle();
  const names = await lotNames('/api/pile', lot);
  assert.equal(names.length, 3);
  await page.waitFor(`pileItems.filter(it => it.lot && it.lot.id === ${JSON.stringify(lot)}).length === 3`,
    { what: 'lot dans la pile' });
  await page.eval(`openViewer(pileView().findIndex(it => it.name === ${JSON.stringify(names[1])}), pileView())`);
  await page.waitFor(`$('viewer').classList.contains('on') && !$('vSort').hidden`,
    { what: 'visionneuse sur l\'image 2' });
  assert.equal(await page.eval(`(async () => { const before = pileItems; await loadPile();
    return pileItems !== before; })()`), true, 'pile relue (nouveaux objets)');
  return { lot, names };
}

test('Garder depuis la visionneuse, la pile relue : seule l\'image vue part dans les Tirages', async () => {
  const { lot, names } = await viewSecond('variantes à départager');
  await page.click('#vSort .btn:not(.secondary)');            // Garder
  await waitUntil(async () => (await lotNames('/api/history', lot)).length === 1, { what: 'image gardée' });
  assert.deepEqual(await lotNames('/api/history', lot), [names[1]], 'l\'image vue, et elle seule, gardée');
  assert.deepEqual(await lotNames('/api/pile', lot), [names[0], names[2]], 'les autres restent dans la pile');
  await page.eval(`closeViewer()`);
  await page.keepPile();
  page.assertNoErrors();
});

test('Jeter depuis la visionneuse après une relecture de la pile : seule l\'image vue est effacée', async () => {
  const { lot, names } = await viewSecond('variantes à jeter');
  await page.click('#vSort .btn.secondary');                  // Jeter
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau Annuler' });
  await waitUntil(async () => (await lotNames('/api/pile', lot)).length === 2, { what: 'image jetée', timeout: 10000 });
  assert.deepEqual(await lotNames('/api/pile', lot), [names[0], names[2]], 'les autres restent dans la pile');
  assert.deepEqual(await lotNames('/api/history', lot), [], 'rien dans les Tirages');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});
