// « Relancer », dans la vue du téléphone : la même demande avec une nouvelle graine, sans toucher la saisie, depuis la
// visionneuse d'une image de la pile (demande gardée par la page : l'image seule, une image de variantes ou la photo
// d'une campagne), la carte d'un échec, ou la visionneuse des Tirages (demande reconstruite de l'image, absente pour
// un masque), dans l'espace affiché, la génération en haut du Labo.
// La demande envoyée est lue au passage (fetch enveloppé).
//   venv/bin/python tests/check.py --quick --ui tests/ui/relance.test.mjs
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
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)})
  .then(r => r.status)`);
// page neuve, générations courtes ; les demandes envoyées à /api/generate sont notées (sentBodies)
async function fresh() {
  await bench.idle();                              // rien en file : la page rechargée ne reprend rien
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.ready();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices();
    window.sentBodies = []; const f = window.fetch; window.fetch = (u, o) => {
      if (String(u).endsWith('/api/generate')) sentBodies.push(JSON.parse(o.body)); return f(u, o); }`);
}
// « Relancer » (sélecteur) : la demande suivante part, la page est sur le Labo ; rend cette demande, images réduites à
// leur nombre (les dimensions seules pour une campagne)
async function again(selector) {
  const [n, jobs] = await page.eval(`[sentBodies.length, pageJobs.length]`);
  await page.click(selector);
  await page.waitFor(`sentBodies.length > ${n} && pageJobs.length > ${jobs} && mode === 'labo'`,
    { what: 'demande relancée, suivie, Labo' });
  return sent(-1);
}
const sent = k => page.eval(`(b => ({ ...b, ref_images: b.ref_images.length,
  campaign: b.campaign && b.campaign.map(c => [c.width, c.height]) }))(sentBodies.at(${k}))`);
const ref = color => `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '${color}'; x.fillRect(0, 0, 256, 256);
  return c.toDataURL('image/png'); })()`;
const addImage = color => page.eval(`(async () => { inputImages.push(await toEntry('i.png', ${ref(color)}));
  renderInputs(); refreshChoices(); })()`);
// génération envoyée hors de l'interface (comme d'un autre appareil), 512×512 en 8 étapes
// les images de la pile gardées par ✓, puis la visionneuse des Tirages sur l'image au prompt donné
async function view(prompt) {
  await page.keepPile();
  await page.tab('tirages');
  const at = `histItems.findIndex(it => it.prompt === ${JSON.stringify(prompt)})`;
  await page.waitFor(`${at} >= 0`, { what: 'image dans la galerie' });
  await page.eval(`openViewer(${at}, histItems)`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
}
const shown = sel => page.eval(`(el => !!el && !el.hidden && el.getClientRects().length > 0)
  (document.querySelector(${JSON.stringify(sel)}))`);

test('pile : la même demande, nouvelle graine, saisie intacte, Labo', async () => {
  await fresh();
  await page.generate('zl1 phare');
  await bench.idle({ page });
  await page.typePrompt('texte suivant');
  await page.viewPile('zl1 phare');
  const b = await again('#vAgain');
  assert.deepEqual(b, { ...await sent(0) }, 'la même demande');
  assert.equal(b.seed, -1, 'nouvelle graine (tirée par le Mac)');
  assert.equal(await page.eval(`pageJobs.length`), 2, 'suivie par la page');
  assert.equal(await page.eval(`$('prompt').value`), 'texte suivant', 'saisie intacte');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('lot de variantes : une image du lot (visionneuse de la pile) relance une seule image', async () => {
  await fresh();
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices()`);
  await page.generate('zl2 variantes');
  await bench.idle({ page });
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);   // le réglage du moment ne compte pas
  await page.viewPile('zl2 variantes');
  const one = await again('#vAgain');
  assert.equal(one.count, undefined, 'une seule image');
  assert.equal(one.prompt, 'zl2 variantes');
  assert.equal(await page.eval(`$('viewer').classList.contains('on')`), false, 'visionneuse fermée');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('campagne : une image du lot relance sa seule photo, à ses dimensions', async () => {
  await fresh();
  await page.tab('labo');
  await addImage('#c02020');
  await addImage('#2060c0');
  await page.eval(`$('campChk').click()`);
  await page.generate('zl3 campagne');
  await page.eval(`$('campChk').click()`);
  await bench.idle({ page });
  await page.waitFor(`pileView().filter(it => it.lot && it.page).length === 2`,
    { what: 'les deux photos dans la pile' });
  await page.eval(`openViewer(pileView().findIndex(it => it.lot && it.lot.rank === 2), pileView())`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  const one = await again('#vAgain');
  assert.equal(one.campaign, undefined, 'une seule photo');
  assert.deepEqual([one.mode, one.ref_images], ['edit', 1]);
  assert.equal(await page.eval(`sentBodies.at(-1).ref_images[0] === sentBodies[0].campaign[1].image
    && sentBodies.at(-1).width === sentBodies[0].campaign[1].width`), true, 'la photo 2, à ses dimensions');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('échec : « Relancer » sur la carte de l\'échec', async () => {
  await fresh();
  await page.generate('zl4 FAIL');
  await bench.idle({ page });
  await page.waitFor(`!!$('pile').querySelector('.pfail [data-again]')`, { what: 'Relancer sur l\'échec' });
  const b = await again('#pile .pfail [data-again]');
  assert.equal(b.prompt, 'zl4 FAIL');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('Tirages : demande reconstruite de l\'image (édition, annotation) ; absent pour un masque', async () => {
  await fresh();
  assert.equal(await page.postGenerate(`{ mode: 'edit', prompt: 'zl5 edition',
    ref_images: [${ref('#c02020')}, ${ref('#2060c0')}] }`), 202);
  assert.equal(await page.postGenerate(`{ mode: 'annot', prompt: 'zl6 annotation',
    ref_images: [${ref('#a040c0')}], seed: 1234 }`),
    202);
  assert.equal(await page.postGenerate(`{ mode: 'mask', prompt: 'zl7 masque', init_image: ${ref('#30a050')},
    mask_image: ${ref('#ffffff')}, ref_images: [${ref('#808080')}] }`), 202);
  await bench.idle({ page });
  await view('zl5 edition');
  const edit = await again('#vAgain');
  assert.deepEqual([edit.mode, edit.prompt, edit.width, edit.height, edit.steps, edit.ref_images, edit.seed],
    ['edit', 'zl5 edition', 512, 512, 8, 2, -1]);
  await bench.idle({ page });
  await view('zl6 annotation');
  const annot = await again('#vAgain');
  assert.deepEqual([annot.mode, annot.ref_images, annot.seed], ['annot', 1, -1], 'graine 1234 de l\'image : nouvelle');
  await bench.idle({ page });
  await view('zl7 masque');
  assert.equal(await shown('#vAgain'), false, 'pas de Relancer pour un masque des Tirages');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});

test('espace du moment : dans l\'espace public, puis dans l\'espace privé', async () => {
  await fresh();
  assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl9 publique' }`), 202);
  await bench.idle({ page });
  await view('zl9 publique');
  const pub = await again('#vAgain');
  assert.deepEqual([pub.private, 'incognito' in pub, 'page' in pub], [undefined, false, false], 'publique');
  await bench.idle({ page });
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl8 privee', private: true }`), 202);
  await bench.idle({ page });
  await view('zl8 privee');
  const priv = await again('#vAgain');
  assert.deepEqual([priv.private, 'incognito' in priv, 'page' in priv, priv.prompt],
    [true, false, false, 'zl8 privee']);
  await bench.idle({ page });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('« Révéler » avec une image : le format choisi reste pour la demande suivante', async () => {
  await fresh();
  await page.tab('labo');
  await addImage('#c02020');
  await page.eval(`opt.ratio = '16:9'; saveOpt(); refreshChoices()`);
  await page.generate('zl10 format');
  assert.equal(await page.eval(`opt.ratio`), '16:9', 'pas remplacé par « Image », puis 1:1');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('double appui sur « Relancer » d\'un échec : une seule relance', async () => {
  await fresh();
  await page.generate('zl11 double FAIL');
  await bench.idle({ page });
  await page.waitFor(`!!$('pile').querySelector('.pfail [data-again]')`, { what: 'Relancer sur l\'échec' });
  await page.eval(`(b => { b.click(); b.click(); })($('pile').querySelector('.pfail [data-again]'))`);
  await page.waitFor(`pageJobs.length === 2`, { what: 'relance suivie' });
  await bench.idle({ page });
  assert.equal(await page.eval(`sentBodies.length`), 2, 'une seule demande en plus');
  page.assertNoErrors();
});

// Modèle de l'image (ticket 07 de MiniMax H3) : « Relancer » renvoie la demande avec son modèle, gardée par la page ou
// reconstruite du champ model de l'image (clé de version) ; MiniMax H3 installé le temps de ces tests seulement
test('modèle d\'une image : absent ou version de Qwen, Qwen ; de MiniMax H3, MiniMax H3 ; sinon null', async () => {
  await fresh();
  const read = item => page.eval(`modelOfImage(${item})`);
  assert.equal(await read(`{}`), 'qwen', 'absent');
  assert.equal(await read(`{ model: null }`), 'qwen', 'absent de la ligne (null de la liste)');
  for (const v of ['q4', 'q8', 'uc-q4', 'uc-q8']) assert.equal(await read(`{ model: '${v}' }`), 'qwen', v);
  for (const v of ['h3-q4', 'h3-q8']) assert.equal(await read(`{ model: '${v}' }`), 'h3', v);
  for (const v of [`'zz-q4'`, `'H3-Q4'`, `'h3'`, `'constructor'`, `42`, `['h3-q4']`, `{}`]) {
    assert.equal(await read(`{ model: ${v} }`), null, `valeur inconnue ou illisible : ${v}`);
  }
  page.assertNoErrors();
});

test('« Relancer » : le modèle de l\'image, demande gardée ou Tirages ; inconnu : celui des Réglages', async () => {
  bench.h3();
  try {
    await fresh();
    await page.modelsSeen(2);
    await page.chooseModel('h3');
    await page.generate('zl12 h3 gardee');
    await bench.idle({ page });
    await page.chooseModel('qwen');
    await page.viewPile('zl12 h3 gardee');
    const kept = await again('#vAgain');
    assert.deepEqual([kept.model, kept.steps], ['h3', 6], 'demande gardée par la page');
    await bench.idle({ page });
    assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl13 h3 tirage', model: 'h3', steps: 6 }`), 202);
    assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl13 qwen tirage' }`), 202);
    await bench.idle({ page });
    await view('zl13 h3 tirage');
    assert.match(await page.eval(`$('vChips').textContent`), /H3-Q4/, 'clé de version en majuscules');
    const fromLog = await again('#vAgain');
    assert.deepEqual([fromLog.model, fromLog.steps], ['h3', 6], 'reconstruite du journal, Réglages sur Qwen');
    await bench.idle({ page });
    await page.eval(`opt.model = 'h3'; saveOpt(); refreshChoices()`);   // (champ replié : la pile reste triable)
    await view('zl13 qwen tirage');
    assert.equal((await again('#vAgain')).model, 'qwen', 'image de Qwen, Réglages sur MiniMax H3');
    await bench.idle({ page });
    const odd = `histItems.find(it => it.prompt === 'zl13 qwen tirage')`;
    await page.eval(`againFrom({ ...${odd}, model: 'zz-q4' })`);
    await page.waitFor(`sentBodies.at(-1).prompt === 'zl13 qwen tirage' && sentBodies.length > 4`,
      { what: 'relance d\'une image au modèle inconnu' });
    assert.deepEqual(await page.eval(`[sentBodies.at(-1).model, sentBodies.at(-1).steps]`), ['h3', 6],
      'modèle inconnu : celui des Réglages, avec ses étapes');
    await bench.idle({ page });
    page.assertNoErrors();
  } finally {
    bench.h3(false);
  }
});

test('« Relancer » une image MiniMax H3 désinstallé depuis : le refus du serveur, tel quel', async () => {
  bench.h3();
  try {
    await fresh();
    await page.modelsSeen(2);
    assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl14 h3', model: 'h3', steps: 6 }`), 202);
    await bench.idle({ page });
    bench.h3(false);
    await page.modelsSeen(1);
    await view('zl14 h3');
    await page.watchToasts();
    const n = await page.eval(`sentBodies.length`);
    await page.click('#vAgain');
    await page.waitFor(`sentBodies.length > ${n}`, { what: 'relance envoyée' });
    await page.waitFor(`seenToasts.some(t => t.startsWith('Erreur : MiniMax H3'))`,
      { what: 'refus du serveur affiché' });
    const error = await page.eval(`seenToasts.find(t => t.startsWith('Erreur'))`);
    assert.equal(error, 'Erreur : MiniMax H3 n\'est pas installé : lancez setup.py --h3 (Mac seulement)');
    page.errors.length = 0;                           // (le 400 du serveur, écrit par Chrome dans la console)
    page.assertNoErrors();
  } finally {
    bench.h3(false);
  }
});

test('« Relancer » une image de Qwen avec MiniMax H3 choisi : aperçus comptés à l\'intervalle de Qwen', async () => {
  bench.h3();
  try {
    await fresh();
    await page.modelsSeen(2);
    await page.eval(`$('previewChk').checked = true; saveOpt(); refreshChoices()`);
    await page.generate('zl15 qwen apercu');
    await bench.idle({ page });
    await page.chooseModel('h3');
    await page.viewPile('zl15 qwen apercu');
    const b = await again('#vAgain');
    assert.deepEqual([b.model, b.preview, b.steps], ['qwen', true, 8]);
    const none = `{ refs: [], init: 0 }`;
    const [est, qwen, h3] = await page.eval(`[pageJobs.at(-1).est, parts(512, 512, 8, ${none}, true, 5).total,
      parts(512, 512, 8, ${none}, true, 2).total]`);
    assert.notEqual(qwen, h3, 'cas qui ne distingue pas les deux intervalles');
    assert.equal(est, qwen, 'estimation de la relance à l\'intervalle du modèle des Réglages');
    await bench.idle({ page });
    page.assertNoErrors();
  } finally {
    bench.h3(false);
  }
});

test('espace privé : « Relancer » une image privée MiniMax H3 garde son modèle', async () => {
  bench.h3();
  try {
    await fresh();
    await page.modelsSeen(2);
    await page.enterPrivate(CODE);
    assert.equal(await page.postGenerate(`{ mode: 't2i', prompt: 'zl16 privee h3', model: 'h3', steps: 6,
      private: true }`), 202);
    await bench.idle({ page });
    await view('zl16 privee h3');
    assert.match(await page.eval(`$('vChips').textContent`), /H3-Q4/);
    const b = await again('#vAgain');
    assert.deepEqual([b.private, b.model, b.steps], [true, 'h3', 6]);
    await bench.idle({ page });
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
    page.assertNoErrors();
  } finally {
    bench.h3(false);
  }
});
