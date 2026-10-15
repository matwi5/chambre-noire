// Test de fumée de l'interface, dans la vue du téléphone : chaque écran principal s'ouvre sans erreur de console.
//   node --test "tests/ui/*.test.mjs"   (ou : venv/bin/python tests/check.py --ui)
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

test('vue du téléphone : mode allégé', async () => {
  assert.equal(await page.eval(`document.documentElement.classList.contains('lite')`), true);
});

test('onglets Créer, Éditer, Dessiner et Galerie', async () => {
  for (const pane of ['edit', 'mask', 'hist', 't2i']) {
    await page.click(`#tabbar [data-pane="${pane}"]`);
    await page.waitFor(`$('pane-${pane}').classList.contains('active') && document.body.className === 'm-${pane}'`);
    if (pane === 'hist') await page.waitFor(`$('histGrid').children.length > 0`, { what: 'galerie affichée' });
  }
  page.assertNoErrors();
});

test('feuille des prompts', async () => {
  await page.click('#promptsBtn');
  await page.waitFor(`$('promptSheet').classList.contains('on') && $('typeList').children.length > 0`,
    { what: 'feuille des prompts ouverte, prompts types listés' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('feuille de la file, puis annulation depuis la file', async () => {
  // une génération lente lancée depuis l'interface (le faux moteur ralentit sur SLOW=…)
  await page.eval(`(() => { const t = $('t2i_prompt'); t.value = 'SLOW=0.3 essai de la file'; t.dispatchEvent(new Event('input')); })()`);
  await page.click('#go');
  await page.waitFor(`pageJobs.some(isActive)`, { what: 'génération suivie par la page' });
  await page.click('#island');
  await page.waitFor(`$('queueSheet').classList.contains('on') && !!$('queueList').querySelector('.qrow.own [data-cancel]')`,
    { what: 'feuille de la file avec la génération de cet appareil' });
  await page.click('#queueList .qrow.own [data-cancel]');
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération annulée' });
  const status = await (await fetch(bench.url + '/api/status')).json();
  assert.equal(status.queue.length, 0);
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});
