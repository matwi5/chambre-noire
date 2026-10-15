// Brouillons du navigateur (localStorage), dans la vue du téléphone : une demande incognito ou de l'espace privé,
// même refusée par le Mac, ne laisse aucun texte de prompt (clé qwen-<onglet>_prompt) dans le navigateur.
//   node --test tests/ui/brouillons.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/brouillons.test.mjs)
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
const type = (tab, text) => page.eval(`(() => { const t = $('${tab}_prompt'); t.value = ${JSON.stringify(text)};
  t.dispatchEvent(new Event('input')); })()`);
// Chrome note dans sa console la réponse 503 du refus simulé : seule erreur attendue
const assertNoOtherErrors = () => assert.deepEqual(page.errors.filter(e => !/status of 503/.test(e)), []);
const drafts = () => page.eval(`Object.keys(localStorage).filter(k => /^qwen-.*_prompt$/.test(k))`);

async function fresh() {
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
  await type('t2i', 'un phare au crépuscule');
  assert.deepEqual(await drafts(), ['qwen-t2i_prompt'], 'brouillon public retenu');
  await page.click('#incog');
  await page.waitFor(`incogOn`, { what: 'incognito activé' });
  await refusedGenerate();
  assert.deepEqual(await drafts(), []);
  assert.equal(await page.eval(`$('t2i_prompt').value`), 'un phare au crépuscule', 'le texte reste dans le champ');
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
  await type('t2i', 'une forêt sous la neige');
  assert.deepEqual(await drafts(), [], 'rien écrit pendant la saisie');
  await refusedGenerate();
  assert.deepEqual(await drafts(), []);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await drafts(), []);
  assertNoOtherErrors();
});
