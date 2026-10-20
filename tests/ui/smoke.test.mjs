// Test de fumée de l'interface, dans la vue du téléphone : chaque écran principal s'ouvre sans erreur de console
// (page En cours comprise, avec la file), et le panneau Moteur dit quelle version du code est servie.
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

test('onglets En cours, Créer, Éditer, Dessiner et Galerie', async () => {
  for (const pane of ['run', 'edit', 'mask', 'hist', 't2i']) {
    await page.click(`#tabbar [data-pane="${pane}"]`);
    await page.waitFor(`$('pane-${pane}').classList.contains('active') && document.body.className === 'm-${pane}'`);
    if (pane === 'hist') await page.waitFor(`$('histGrid').children.length > 0`, { what: 'galerie affichée' });
  }
  // feuille de la file, rangée « #1 #2… » et annulation du compositeur : remplacées par la page En cours
  assert.deepEqual(await page.eval(`['queueSheet', 'strip', 'cancel'].filter(id => $(id))`), []);
  page.assertNoErrors();
});

test('feuille des prompts', async () => {
  await page.click('#promptsBtn');
  await page.waitFor(`$('promptSheet').classList.contains('on') && $('typeList').children.length > 0`,
    { what: 'feuille des prompts ouverte, prompts types listés' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('« Générer » mène à la page En cours, puis annulation depuis sa file', async () => {
  // une génération lente lancée depuis l'interface (le faux moteur ralentit sur SLOW=…)
  await page.eval(`(() => { const t = $('t2i_prompt'); t.value = 'SLOW=0.3 essai de la file'; t.dispatchEvent(new Event('input')); })()`);
  await page.click('#go');
  await page.waitFor(`pageJobs.some(isActive) && mode === 'run'`, { what: 'génération suivie, page En cours' });
  await page.waitFor(`!!$('queueList').querySelector('.qrow.own [data-cancel]')`,
    { what: 'file de la page avec la génération de cet appareil' });
  await page.click('#queueList .qrow.own [data-cancel]');
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération annulée' });
  const status = await (await fetch(bench.url + '/api/status')).json();
  assert.equal(status.queue.length, 0);
  page.assertNoErrors();
});

test('panneau Moteur : version du code servi, et serveur à relancer quand launch.py a changé', async () => {
  const shown = await page.eval(`({ v: fmtVersion({ commit: 'abc1234', branch: 'main', date: '2026-10-16' }),
    none: fmtVersion(undefined),
    same: staleServer({ version: { commit: 'b2', server: 'f1' }, server_version: { commit: 'a1', server: 'f1' } }),
    stale: staleServer({ version: { commit: 'abc1234', server: 'f2' },
      server_version: { commit: 'def5678', server: 'f1' } }) })`);
  assert.deepEqual(shown, { v: 'abc1234 · main · 16/10/2026', none: '', same: '',
    stale: 'à relancer : son code a changé depuis son lancement' });
  page.assertNoErrors();
});
