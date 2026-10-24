// Test de fumée de l'interface, dans la vue du téléphone : chaque écran principal s'ouvre sans erreur de console
// (Labo, avec la génération en cours, et Tirages), et le panneau Moteur dit quelle version du code est servie.
//   venv/bin/python tests/check.py --ui   (tous les fichiers ; --quick --ui tests/ui/smoke.test.mjs pour celui-ci)
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

test('onglets Labo et Tirages', async () => {
  for (const pane of ['tirages', 'labo']) {
    await page.tab(pane);
    assert.equal(await page.eval(`document.body.className`), `m-${pane}`);
    if (pane === 'tirages') await page.waitFor(`$('histGrid').children.length > 0`, { what: 'Tirages affichés' });
  }
  // feuille de la file, rangée « #1 #2… » et annulation du compositeur d'avant : remplacées par le haut du Labo
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

// (titre attendu tel quel par tests/test_check.py, UiNameTest)
test('« Révéler » suit la génération sur le Labo, puis annulation depuis la carte en cours', async () => {
  // une génération lente lancée depuis l'interface (le faux moteur ralentit sur SLOW=…)
  await page.typePrompt('SLOW=0.3 essai de la file');
  await page.click('#go');
  await page.waitFor(`pageJobs.some(isActive) && mode === 'labo'`, { what: 'génération suivie, Labo' });
  await page.waitFor(`shown && shown.j.status === 'running' && !$('runCard').hidden`,
    { what: 'génération sur la carte en cours' });
  await page.cancelRun();
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
