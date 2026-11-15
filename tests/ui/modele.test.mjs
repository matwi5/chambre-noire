// Ligne « Modèle » des Réglages (ticket 04), dans la vue du téléphone : montrée seulement quand le Mac a au moins deux
// modèles installés (pas devant un serveur sans liste models) ; Qwen à la première ouverture, puis le dernier choisi,
// retenu par la page (qwen-opt) ; un modèle retenu qui n'est plus installé laisse la place à Qwen ; avec MiniMax H3,
// pas de ligne « Étapes », 6 étapes envoyées, aperçu toutes les 2 étapes ; la grille rappelle le modèle ; la feuille
// Moteur a une ligne par autre modèle installé, la lampe ne change pas.
//   venv/bin/python tests/check.py --quick --ui tests/ui/modele.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const CELLS = `[...$('setGrid').querySelectorAll('[data-set]')].map(c => c.dataset.set)`;

test('Qwen seul, ou serveur sans liste de modèles : pas de ligne Modèle, demande sans champ model', async () => {
  bench.h3(false);
  await page.freshLabo(bench);
  await page.modelsSeen(1);
  assert.equal(await page.eval(`$('modelRow').hidden`), true, 'ligne Modèle avec un seul modèle');
  assert.equal((await page.eval(CELLS)).includes('modele'), false, 'case Modèle avec un seul modèle');
  assert.equal('model' in await page.sentRequest('zmo1 qwen seul'), false, 'champ model envoyé avec un seul modèle');
  bench.h3();
  await bench.idle();
  await page.oldServer();
  assert.equal(await page.eval(`modelList`), null, 'liste lue d\'un serveur qui ne l\'envoie pas');
  assert.equal(await page.eval(`$('modelRow').hidden`), true, 'ligne Modèle devant un ancien serveur');
  assert.equal('model' in await page.sentRequest('zmo1 ancien serveur'), false,
    'champ model envoyé à un ancien serveur');
  await bench.idle();
  page.assertNoErrors();
});

test('Qwen à la première ouverture, puis le dernier choisi ; non installé : Qwen, sans oublier le choix', async () => {
  bench.h3();
  await page.freshLabo(bench);
  await page.modelsSeen(2);
  assert.equal(await page.eval(`$('modelRow').hidden`), false, 'ligne Modèle absente avec deux modèles');
  assert.deepEqual(await page.eval(`[...$('modelOpts').querySelectorAll('[data-k]')].map(b => b.textContent)`),
    ['Qwen', 'MiniMax H3']);
  assert.equal(await page.eval(`modelSel().key`), 'qwen', 'pas Qwen à la première ouverture');
  assert.equal((await page.sentRequest('zmo2 qwen')).model, 'qwen');
  await bench.idle();
  await page.chooseModel('h3');
  await page.goto(bench.url + '/');
  await page.modelsSeen(2);
  assert.equal(await page.eval(`modelSel().key`), 'h3', 'dernier modèle choisi oublié au rechargement');
  // clés de la mémoire de la page inchangées : le modèle s'ajoute à qwen-opt
  const saved = await page.eval(`JSON.parse(localStorage.getItem('qwen-opt'))`);
  assert.equal(saved.model, 'h3');
  assert.equal(saved.v, 2);
  assert.deepEqual(Object.keys(saved).sort(),
    ['campaign', 'count', 'model', 'notify', 'preview', 'ratio', 'res', 'steps', 'v']);
  bench.h3(false);
  await page.modelsSeen(1);
  assert.equal(await page.eval(`$('modelRow').hidden`), true, 'ligne Modèle sans MiniMax H3');
  assert.equal('model' in await page.sentRequest('zmo2 h3 retiré'), false,
    'MiniMax H3 demandé alors qu\'il n\'est plus là');
  await bench.idle();
  bench.h3();
  await page.modelsSeen(2);
  assert.equal(await page.eval(`modelSel().key`), 'h3', 'choix oublié pendant que MiniMax H3 manquait');
  page.assertNoErrors();
});

test('MiniMax H3 : sans Étapes, 6 étapes envoyées, aperçu toutes les 2 étapes, formats de Qwen', async () => {
  bench.h3();
  await page.freshLabo(bench);
  await page.modelsSeen(2);
  const choices = () => page.eval(`['ratioOpts', 'resOpts'].map(id => [...$(id).querySelectorAll('[data-k]')]
    .map(b => b.dataset.k))`);
  const qwen = await choices();
  assert.equal(await page.eval(`$('stepRow').hidden`), false, 'Étapes masquées avec Qwen');
  assert.match(await page.eval(`$('previewChk').parentElement.textContent`), /Aperçu toutes les 5 étapes/);
  await page.chooseModel('h3');
  assert.equal(await page.eval(`$('stepRow').hidden`), true, 'ligne Étapes avec MiniMax H3');
  assert.match(await page.eval(`$('previewChk').parentElement.textContent`), /Aperçu toutes les 2 étapes/);
  assert.deepEqual(await choices(), qwen, 'formats ou résolutions différents de ceux de Qwen');
  const req = await page.sentRequest('zmo3 h3');
  assert.equal(req.model, 'h3');
  assert.equal(req.steps, 6);
  await page.waitFor(`pileItems.some(it => it.prompt === 'zmo3 h3')`, { what: 'image MiniMax H3 dans la pile' });
  page.assertNoErrors();
});

test('la grille rappelle le modèle ; une ligne Moteur par autre modèle, lampe inchangée', async () => {
  bench.h3();
  await page.freshLabo(bench);
  await page.modelsSeen(2);
  const lamp = await page.eval(`$('lamp').title`);
  assert.deepEqual(await page.eval(CELLS), ['modele', 'format', 'taille', 'etapes', 'images']);
  assert.match(await page.eval(`$('setGrid').textContent`), /ModèleQwen/);
  await page.chooseModel('h3');
  assert.deepEqual(await page.eval(CELLS), ['modele', 'format', 'taille', 'images'], 'grille avec MiniMax H3');
  assert.match(await page.eval(`$('setGrid').textContent`), /ModèleMiniMax H3/);
  assert.deepEqual(await page.overflowing(), [], 'la grille dépasse à 367 px');
  assert.match(await page.eval(`$('engineFacts').textContent`), /MiniMax H3H3-Q4/);
  assert.equal(await page.eval(`$('lamp').title`), lamp, 'lampe changée par le choix du modèle');
  page.assertNoErrors();
});
