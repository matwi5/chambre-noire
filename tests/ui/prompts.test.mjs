// Prompts enregistrés, dans la vue du téléphone : chaque espace (public, privé) ne voit que les siens, et les prompts
// types.
//   node --test tests/ui/prompts.test.mjs   (ou : venv/bin/python tests/check.py --ui)
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

const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
const titles = list => page.eval(`[...$('${list}').querySelectorAll('.prow b')].map(b => b.textContent)`);
async function openPrompts(expected) {             // feuille des prompts, une fois la liste de l'espace reçue
  await page.click('#promptsBtn');
  await page.waitFor(`openedSheet === $('promptSheet') && $('typeList').children.length > 0`, { what: 'prompts types reçus' });
  await page.waitFor(`${JSON.stringify(expected)}.every(t => [...$('promptList').querySelectorAll('.prow b')].some(b => b.textContent === t))`,
    { what: `prompts ${expected.join(', ')} affichés` });
}
// « Enregistrer le texte actuel » avec ce titre, depuis la feuille ouverte
async function saveCurrent(title, text) {
  await page.eval(`(() => { const t = $(mode + '_prompt'); t.value = ${JSON.stringify(text)}; t.dispatchEvent(new Event('input')); })()`);
  await page.click('#promptSheet .pnew');
  await page.waitFor(`openedSheet === $('promptEditSheet')`, { what: 'feuille d\'enregistrement' });
  await page.eval(`$('peTitle').value = ${JSON.stringify(title)}`);
  await page.click('#peSave');
}

test('espaces : les prompts privés ne se voient que dans l\'espace privé, les publics que dehors', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await openPrompts([]);
  await saveCurrent('Public', 'un prompt public');
  await page.waitFor(`openedSheet === $('promptSheet')`, { what: 'retour à la liste' });
  await openPrompts(['Public']);

  // entrée dans l'espace privé, la feuille ouverte : elle se ferme, la liste publique quitte la page
  assert.equal(await post('/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  assert.equal(await page.eval(`openedSheet`), null, 'feuille des prompts fermée');
  assert.deepEqual(await page.eval(`prompts.saved`), []);

  await openPrompts([]);
  await saveCurrent('Privé', 'un prompt privé');
  await openPrompts(['Privé']);
  assert.deepEqual(await titles('promptList'), ['Privé'], 'aucun prompt public dans l\'espace privé');
  const dup = await page.eval(`prompts.types[0].title`);  // « Dupliquer » un prompt type : un prompt privé
  await page.click('#typeList [data-dup]');
  await page.waitFor(`[...$('promptList').querySelectorAll('.prow b')].some(b => b.textContent === ${JSON.stringify(dup)})`,
    { what: 'prompt type dupliqué' });
  await page.eval(`[...$('promptList').querySelectorAll('.prow')].find(r => r.querySelector('b').textContent === 'Privé').querySelector('[data-pick]').click()`);
  assert.equal(await page.eval(`$(mode + '_prompt').value`), 'un prompt privé');
  // utiliser un prompt privé le fait passer en tête
  await page.waitFor(`fetch('/api/private/prompts').then(r => r.json()).then(j => j.saved[0].title === 'Privé')`,
    { what: 'dernière utilisation du prompt privé notée' });

  // fermeture de l'espace par le Mac pendant la confirmation d'une suppression (elle montre le titre du prompt) : elle se
  // ferme sans supprimer, et rien de privé ne reste dans la page
  await openPrompts(['Privé', dup]);
  await page.eval(`[...$('promptList').querySelectorAll('.prow')].find(r => r.querySelector('b').textContent === 'Privé')
    .querySelector('[data-del]').click()`);
  await page.waitFor(`openedSheet === $('askSheet') && $('askText').textContent === 'Privé'`, { what: 'confirmation' });
  assert.equal(await post('/api/private/lock'), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
  assert.equal(await page.eval(`openedSheet`), null, 'confirmation fermée');
  assert.equal(await page.eval(`$('askText').textContent`), '', 'titre du prompt privé effacé');
  assert.deepEqual(await page.eval(`prompts.saved`), []);
  await openPrompts(['Public']);
  assert.deepEqual(await titles('promptList'), ['Public'], 'aucun prompt privé dans l\'espace public');
  page.assertNoErrors();
});
