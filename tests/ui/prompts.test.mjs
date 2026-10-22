// Prompts enregistrés, dans la vue du téléphone : chaque espace (public, privé) ne voit que les siens, et les prompts
// types ; la feuille s'ouvre filtrée sur la catégorie de la saisie (sans image : Créer ; avec images : Éditer ; dessin
// actif : Dessiner), et un nouveau prompt prend cette catégorie.
//   venv/bin/python tests/check.py --quick --ui tests/ui/prompts.test.mjs
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
  await page.typePrompt(text);
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
  const dup = await page.eval(`$('typeList').querySelector('.prow b').textContent`);  // « Dupliquer » un prompt type
  await page.click('#typeList [data-dup]');
  await page.waitFor(`[...$('promptList').querySelectorAll('.prow b')].some(b => b.textContent === ${JSON.stringify(dup)})`,
    { what: 'prompt type dupliqué' });
  await page.eval(`[...$('promptList').querySelectorAll('.prow')].find(r => r.querySelector('b').textContent === 'Privé').querySelector('[data-pick]').click()`);
  assert.equal(await page.eval(`$('prompt').value`), 'un prompt privé');
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

const filter = () => page.eval(`$('promptFilter').querySelector('.on').dataset.k`);
const usages = list => page.eval(`[...$('${list}').querySelectorAll('.prow')]
  .map(r => [...prompts.saved, ...prompts.types].find(p => p.id === r.dataset.id).usage)`);

test('catégories : feuille ouverte sur celle de la saisie, « Tous » à un geste, nouveau prompt dedans', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await openPrompts([]);
  assert.equal(await filter(), 't2i', 'sans image : Créer');
  assert.deepEqual([...new Set(await usages('typeList'))], ['t2i']);
  await page.click('#promptFilter [data-k="all"]');
  assert.equal(await filter(), 'all');
  assert.equal(new Set(await usages('typeList')).size, 3, 'Tous : les trois catégories');
  await page.eval(`closeSheet()`);
  // avec une image : Éditer ; le prompt enregistré prend cette catégorie, et la feuille rouverte garde le filtre
  await page.eval(`(async () => { const c = document.createElement('canvas'); c.width = c.height = 128;
    inputImages.push(await toEntry('a.png', c.toDataURL('image/png'))); renderInputs(); refreshChoices(); })()`);
  await openPrompts([]);
  assert.equal(await filter(), 'edit', 'avec une image : Éditer');
  await saveCurrent('Chapeau', 'mettre un chapeau');
  await page.waitFor(`openedSheet === $('promptSheet') && [...$('promptList').querySelectorAll('.prow b')]
    .some(b => b.textContent === 'Chapeau')`, { what: 'prompt enregistré affiché' });
  assert.equal(await filter(), 'edit', 'réouverture après l\'enregistrement : filtre gardé');
  assert.equal(await page.eval(`prompts.saved.find(p => p.title === 'Chapeau').usage`), 'edit');
  await page.eval(`closeSheet()`);
  // dessin actif : Dessiner ; choisir un prompt d'une autre catégorie ne remplit que le texte
  await page.click('#drawBtn');
  await page.waitFor(`drawOn`, { what: 'dessin actif' });
  await openPrompts([]);
  assert.equal(await filter(), 'mask', 'dessin actif : Dessiner');
  await page.click('#promptFilter [data-k="all"]');
  await page.eval(`[...$('promptList').querySelectorAll('.prow')]
    .find(r => r.querySelector('b').textContent === 'Chapeau').querySelector('[data-pick]').click()`);
  assert.equal(await page.eval(`$('prompt').value`), 'mettre un chapeau');
  assert.equal(await page.eval(`drawOn && inputImages.length === 1`), true, 'images et dessin intacts');
  page.assertNoErrors();
});
