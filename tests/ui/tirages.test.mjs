// Page Tirages, dans la vue du téléphone : état vide en pixels (le logo, « Aucun tirage pour l'instant », « Aller au
// Labo »), plus de bouton Rafraîchir : la page se met à jour seule, sans recharger, quand une image est gardée ou un
// tirage supprimé, ici ou sur un autre appareil, et ne redessine pas sa grille quand seule la pile a changé ;
// « Supprimer » confirmé dans la visionneuse, qui n'a pas « Garder celle-ci ».
//   venv/bin/python tests/check.py --quick --ui tests/ui/tirages.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page, other;                    // other : une deuxième page, comme un autre appareil

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  other = await chrome.phonePage();
  for (const p of [page, other]) {
    await p.goto(bench.url + '/');
    await p.ready();
  }
  await page.eval(`window.zqSansRecharger = true`);   // disparaît si la page est rechargée
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const names = p => p.eval(`[...$('histGrid').querySelectorAll('button[data-name]')].map(b => b.dataset.name)`);

test('Tirages vides : le logo, « Aucun tirage pour l\'instant » et « Aller au Labo » ; pas de Rafraîchir', async () => {
  await page.tab('tirages');
  await page.waitFor(`!!$('histGrid').querySelector('.hempty')`, { what: 'état vide des Tirages' });
  assert.equal(await page.eval(`$('histGrid').querySelector('.hempty p').textContent`), 'Aucun tirage pour l\'instant');
  assert.equal(await page.eval(`$('histGrid').querySelector('.hempty img').getAttribute('src')`), '/logo.svg');
  assert.equal(await page.eval(`!!document.querySelector('.hist-head button')`), false, 'plus de bouton dans le titre');
  assert.equal(await page.eval(`!!$('vKeep')`), false, 'pas de « Garder celle-ci »');
  assert.deepEqual(await page.overflowing(), []);
  await page.click('#histGrid .hempty button');
  await page.waitFor(`mode === 'labo'`, { what: 'Labo après « Aller au Labo »' });
  page.assertNoErrors();
});

test('une image gardée par un autre appareil arrive dans les Tirages affichés, sans recharger', async () => {
  await page.tab('tirages');
  await other.made('zqT gardée ailleurs');
  assert.equal(await other.keepPile(), 1);
  await page.waitFor(`$('histGrid').querySelectorAll('button[data-name]').length === 1`,
    { what: 'tirage arrivé sans Rafraîchir' });
  assert.equal(await page.eval(`$('histCount').textContent`), '1 image');
  assert.equal(await page.eval(`window.zqSansRecharger`), true, 'page non rechargée');
  page.assertNoErrors();
  other.assertNoErrors();
});

test('une image qui arrive seulement dans la pile ne redessine pas les Tirages', async () => {
  await page.eval(`window.zqVignette = $('histGrid').querySelector('button[data-name]')`);
  // lectures des Tirages demandées par la page (requêtes envoyées, mesurées par le navigateur)
  const reads = `performance.getEntriesByType('resource').filter(e => e.name.endsWith('/api/history')).length`;
  const before = await page.eval(`window.zqListe = histItems, ${reads}`);
  await other.made('zqT dans la pile');
  // la page a relu les Tirages après l'arrivée dans la pile (nouvelle liste appliquée) : eux n'ont pas changé
  await page.waitFor(`${reads} > ${before} && histItems !== window.zqListe`,
    { what: 'Tirages relus après l\'arrivée dans la pile' });
  assert.equal(await page.eval(`window.zqVignette.isConnected`), true, 'même vignette, grille non redessinée');
  page.assertNoErrors();
});

test('un tirage supprimé ailleurs quitte les Tirages ; « Supprimer » ici, confirmé, aussi', async () => {
  await other.keepPile();                          // la deuxième image : deux tirages
  await page.waitFor(`$('histGrid').querySelectorAll('button[data-name]').length === 2`, { what: 'deux tirages' });
  const [first, second] = await names(page);
  assert.equal(await other.eval(`postJson('/api/delete', { name: ${JSON.stringify(first)} }).then(r => r.status)`),
    200);
  await page.waitFor(`$('histGrid').querySelectorAll('button[data-name]').length === 1`,
    { what: 'tirage supprimé ailleurs retiré' });
  assert.deepEqual(await names(page), [second]);
  await page.click('#histGrid button[data-name]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  await page.click('#vDelete');
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de la suppression' });
  await page.eval(`answer(true)`);
  await page.waitFor(`!!$('histGrid').querySelector('.hempty')`, { what: 'Tirages vides après Supprimer' });
  assert.deepEqual(await bench.api('/api/history'), []);
  assert.equal(await page.eval(`window.zqSansRecharger`), true, 'page non rechargée');
  page.assertNoErrors();
  other.assertNoErrors();
});
