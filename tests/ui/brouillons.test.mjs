// Brouillon du navigateur (localStorage, clé unique qwen-prompt), dans la vue du téléphone : une demande incognito ou
// de l'espace privé, même refusée par le Mac, ne laisse aucun texte de prompt dans le navigateur ; activer l'incognito
// retire le brouillon aussitôt ; les brouillons des anciens onglets (qwen-<onglet>_prompt) sont repris une fois.
//   venv/bin/python tests/check.py --quick --ui tests/ui/brouillons.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // demandes de génération interceptées le temps d'un refus : le Mac répond « moteur non prêt »
  page.on('Fetch.requestPaused', p => page.send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 503,
    responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
    body: Buffer.from('{"error":"moteur non prêt"}').toString('base64') }));
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
  await page.eval(`$('toast').textContent = ''`);
  await page.click('#go');
  await page.waitFor(`$('toast').textContent.startsWith('Erreur : moteur non prêt')`, { what: 'refus affiché' });
  await page.send('Fetch.disable');
}

test('incognito : un texte tapé en mode normal ne reste pas en brouillon après une demande refusée', async () => {
  await fresh();
  await page.typePrompt('un phare au crépuscule');
  assert.deepEqual(await drafts(), ['qwen-prompt'], 'brouillon public retenu');
  await page.click('#incog');
  await page.waitFor(`incogOn`, { what: 'incognito activé' });
  assert.deepEqual(await drafts(), [], 'brouillon retiré dès l\'activation, sans attendre la frappe suivante');
  assert.equal(await page.eval(`$('prompt').value`), 'un phare au crépuscule', 'le texte reste dans le champ');
  await page.typePrompt('un phare au crépuscule, la nuit');
  await refusedGenerate();
  assert.deepEqual(await drafts(), []);
  assert.equal(await page.eval(`$('prompt').value`), 'un phare au crépuscule, la nuit',
    'le texte reste après le refus');
  await page.click('#incog');
  await page.waitFor(`!incogOn`, { what: 'incognito désactivé' });
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
