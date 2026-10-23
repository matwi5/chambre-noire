// Brouillon du navigateur (localStorage, clé unique qwen-prompt), dans la vue du téléphone : une demande de l'espace
// privé, même refusée par le Mac, ne laisse aucun texte de prompt dans le navigateur ; l'incognito retiré n'a plus ni
// bouton ni thème, son ancien réglage est signalé une seule fois puis oublié, et une demande ne le porte plus ; les
// brouillons des anciens onglets (qwen-<onglet>_prompt) sont repris une fois.
//   venv/bin/python tests/check.py --quick --ui tests/ui/brouillons.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page, sentBody;               // sentBody : la dernière demande interceptée

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // demandes de génération interceptées le temps d'un refus : le Mac répond « moteur non prêt »
  page.on('Fetch.requestPaused', p => {
    sentBody = JSON.parse(p.request.postData || 'null');
    page.send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 503,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
      body: Buffer.from('{"error":"moteur non prêt"}').toString('base64') });
  });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
// Chrome note dans sa console la réponse 503 du refus simulé : seule erreur attendue
const assertNoOtherErrors = () => assert.deepEqual(page.errors.filter(e => !/status of 503/.test(e)), []);
// brouillons de texte (clé actuelle et anciennes clés par onglet)
const drafts = () => page.eval(`Object.keys(localStorage).filter(k => /^qwen-(\\w+_)?prompt$/.test(k)).sort()`);

async function fresh() {
  await bench.idle();                              // rien en file : la page rechargée ne reprend rien
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
}
// « Générer », refusé par le Mac
async function refusedGenerate() {
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Request' }] });
  await page.eval(`$('toastBox').textContent = ''`);
  await page.click('#go');
  await page.waitFor(`$('toastBox').textContent.startsWith('Erreur : moteur non prêt')`, { what: 'refus affiché' });
  await page.send('Fetch.disable');
}

const INCOG_GONE = 'L\'incognito n\'existe plus : vos images sont enregistrées. Pour la confidentialité, passez par '
  + 'l\'espace privé.';

test('incognito retiré : ancien réglage signalé une fois, brouillon retenu, demande sans incognito', async () => {
  await fresh();
  await page.eval(`localStorage.setItem('qwen-opt', JSON.stringify({ v: 2, ratio: '16:9', incognito: true }))`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.waitFor(`$('toastBox').textContent === ${JSON.stringify(INCOG_GONE)}`, { what: 'ancien réglage signalé' });
  await page.waitFor(`!('incognito' in JSON.parse(localStorage.getItem('qwen-opt')))`,
    { what: 'ancien réglage oublié une fois le message affiché jusqu\'au bout' });
  assert.equal(await page.eval(`JSON.parse(localStorage.getItem('qwen-opt')).ratio`), '16:9', 'autres réglages gardés');
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  assert.notEqual(await page.eval(`$('toastBox').textContent`), INCOG_GONE, 'signalé une seule fois');
  assert.deepEqual(await page.eval(`[!!document.getElementById('incog'),
    document.documentElement.classList.contains('incog')]`), [false, false], 'ni bouton ni thème incognito');
  await page.typePrompt('un phare au crépuscule');
  assert.deepEqual(await drafts(), ['qwen-prompt'], 'brouillon public retenu');
  sentBody = null;
  await refusedGenerate();
  assert.equal(sentBody.prompt, 'un phare au crépuscule');
  assert.deepEqual(['incognito', 'page'].filter(k => k in sentBody), [], 'ni incognito ni jeton de page envoyés');
  assert.deepEqual(await drafts(), ['qwen-prompt'], 'brouillon gardé après le refus');
  assertNoOtherErrors();
});

test('incognito retiré : message remplacé avant la fin, réglage gardé pour le chargement suivant', async () => {
  await fresh();
  await page.eval(`localStorage.setItem('qwen-opt', JSON.stringify({ v: 2, incognito: true }))`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('toastBox').textContent === ${JSON.stringify(INCOG_GONE)}`, { what: 'ancien réglage signalé' });
  await page.eval(`toast('Image prête')`);           // un autre message le remplace avant la fin
  await new Promise(r => setTimeout(r, 7000));       // au-delà de LONG_TOAST
  assert.equal(await page.eval(`JSON.parse(localStorage.getItem('qwen-opt')).incognito`), true, 'réglage gardé');
  assertNoOtherErrors();
});

test('espace privé : un texte tapé puis une demande refusée ne laissent aucun brouillon', async () => {
  await fresh();
  const create = `postJson('/api/private/create', { code: ${JSON.stringify(CODE)} }).then(r => r.status)`;
  assert.equal(await page.eval(create), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  await page.typePrompt('une forêt sous la neige');
  assert.deepEqual(await drafts(), [], 'rien écrit pendant la saisie');
  await refusedGenerate();
  assert.deepEqual(await drafts(), []);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await drafts(), []);
  assertNoOtherErrors();
});

// page chargée avec les brouillons d'avant la page Créer unique (un par onglet)
async function withOldDrafts(old) {
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear();
    Object.entries(${JSON.stringify(old)}).forEach(([k, v]) => localStorage.setItem(k, v))`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
}

test('brouillons d\'avant : celui de Créer, sinon le premier non vide d\'Éditer puis de Dessiner', async () => {
  const edit = 'texte d\'Éditer', mask = 'texte de Dessiner';
  const cases = [
    [{ 'qwen-t2i_prompt': 'texte de Créer', 'qwen-edit_prompt': edit, 'qwen-mask_prompt': mask }, 'texte de Créer'],
    [{ 'qwen-t2i_prompt': '', 'qwen-edit_prompt': edit, 'qwen-mask_prompt': mask }, edit],
    [{ 'qwen-mask_prompt': mask }, mask]];
  for (const [old, kept] of cases) {
    await withOldDrafts(old);
    assert.equal(await page.eval(`$('prompt').value`), kept);
    assert.deepEqual(await drafts(), ['qwen-prompt'], 'les anciennes clés sont retirées');
    assert.equal(await page.eval(`localStorage.getItem('qwen-prompt')`), kept);
  }
  // une fois la clé unique écrite, une ancienne clé ne la remplace plus
  await page.eval(`localStorage.setItem('qwen-t2i_prompt', "revenu d'un vieil onglet")`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  assert.equal(await page.eval(`$('prompt').value`), 'texte de Dessiner');
  assertNoOtherErrors();
});
