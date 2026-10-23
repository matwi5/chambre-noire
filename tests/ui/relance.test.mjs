// « Relancer », dans la vue du téléphone : la même demande avec une nouvelle graine, sans toucher la saisie, depuis une
// terminée (demande gardée par la page : une image, ou tout le lot depuis sa carte, variantes ou campagne), un échec ou
// la visionneuse (galerie : demande reconstruite de l'image, absente pour un masque), dans l'espace affiché, la
// génération en haut du Labo.
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
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
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
const send = body => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 8, cfg: 1, seed: -1,
  preview: false, ref_images: [], ...${body} }).then(r => r.status)`);
async function view(prompt) {
  await bench.keepAll(page);                      // piles gardées (privée comprise) : dans la galerie
  await page.tab('tirages');
  const at = `histItems.findIndex(it => it.prompt === ${JSON.stringify(prompt)})`;
  await page.waitFor(`${at} >= 0`, { what: 'image dans la galerie' });
  await page.eval(`openViewer(${at}, histItems)`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
}
const shown = sel => page.eval(`(el => !!el && !el.hidden && el.getClientRects().length > 0)
  (document.querySelector(${JSON.stringify(sel)}))`);

test('terminée : la même demande, nouvelle graine, saisie intacte, Labo', async () => {
  await fresh();
  await page.generate('zl1 phare');
  await bench.idle({ page });
  await page.typePrompt('texte suivant');
  await page.waitFor(`!!$('doneList').querySelector('.dcard [data-again]')`, { what: 'Relancer sur la terminée' });
  const b = await again('#doneList .dcard [data-again]');
  assert.deepEqual(b, { ...await sent(0) }, 'la même demande');
  assert.equal(b.seed, -1, 'nouvelle graine (tirée par le Mac)');
  assert.equal(await page.eval(`pageJobs.length`), 2, 'suivie par la page');
  assert.equal(await page.eval(`$('prompt').value`), 'texte suivant', 'saisie intacte');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('lot de variantes : la carte relance tout le lot, une image du lot (visionneuse) une seule image', async () => {
  await fresh();
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices()`);
  await page.generate('zl2 variantes');
  await bench.idle({ page });
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);   // le réglage du moment ne compte pas
  await page.waitFor(`!!$('doneList').querySelector('.dlot [data-again]')`, { what: 'Relancer sur la carte du lot' });
  const lot = await again('#doneList .dlot [data-again]');
  assert.equal(lot.count, 2, 'tout le lot');
  assert.equal(lot.prompt, 'zl2 variantes');
  await bench.idle({ page });
  await page.click('#doneList .dlot [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  const one = await again('#vAgain');
  assert.equal(one.count, undefined, 'une seule image');
  assert.equal(one.prompt, 'zl2 variantes');
  assert.equal(await page.eval(`$('viewer').classList.contains('on')`), false, 'visionneuse fermée');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('campagne : la carte relance les mêmes photos, une image du lot sa seule photo, à ses dimensions', async () => {
  await fresh();
  await page.tab('labo');
  await addImage('#c02020');
  await addImage('#2060c0');
  await page.eval(`$('campChk').click()`);
  await page.generate('zl3 campagne');
  await page.eval(`$('campChk').click()`);
  await bench.idle({ page });
  await page.waitFor(`!!$('doneList').querySelector('.dlot [data-again]')`, { what: 'Relancer sur la carte du lot' });
  const lot = await again('#doneList .dlot [data-again]');
  assert.deepEqual(lot.campaign, (await sent(0)).campaign, 'les mêmes photos');
  assert.equal(await page.eval(`sentBodies[1].campaign.length === 2
    && sentBodies[1].campaign.every((c, k) => c.image === sentBodies[0].campaign[k].image)`), true);
  await bench.idle({ page });
  await page.eval(`openViewer(doneView.findIndex(it => it.lot && it.lot.rank === 2 && it.page.req === pageJobs[0].req),
    doneView)`);
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
  await page.waitFor(`!!$('doneList').querySelector('.dcard.fail [data-again]')`, { what: 'Relancer sur l\'échec' });
  const b = await again('#doneList .dcard.fail [data-again]');
  assert.equal(b.prompt, 'zl4 FAIL');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('galerie : demande reconstruite de l\'image (édition, annotation) ; absent pour un masque', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 'edit', prompt: 'zl5 edition',
    ref_images: [${ref('#c02020')}, ${ref('#2060c0')}] }`), 202);
  assert.equal(await send(`{ mode: 'annot', prompt: 'zl6 annotation', ref_images: [${ref('#a040c0')}], seed: 1234 }`),
    202);
  assert.equal(await send(`{ mode: 'mask', prompt: 'zl7 masque', init_image: ${ref('#30a050')},
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
  assert.equal(await shown('#vAgain'), false, 'pas de Relancer pour un masque de la galerie');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});

test('espace du moment : dans l\'espace public, puis dans l\'espace privé', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 't2i', prompt: 'zl9 publique' }`), 202);
  await bench.idle({ page });
  await view('zl9 publique');
  const pub = await again('#vAgain');
  assert.deepEqual([pub.private, 'incognito' in pub, 'page' in pub], [undefined, false, false], 'publique');
  await bench.idle({ page });
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  assert.equal(await send(`{ mode: 't2i', prompt: 'zl8 privee', private: true }`), 202);
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

test('« Générer » avec une image : le format choisi reste pour la demande suivante', async () => {
  await fresh();
  await page.tab('labo');
  await addImage('#c02020');
  await page.eval(`opt.ratio = '16:9'; saveOpt(); refreshChoices()`);
  await page.generate('zl10 format');
  assert.equal(await page.eval(`opt.ratio`), '16:9', 'pas remplacé par « Image », puis 1:1');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('double appui sur « Relancer » d\'une terminée : une seule relance', async () => {
  await fresh();
  await page.generate('zl11 double');
  await bench.idle({ page });
  await page.waitFor(`!!$('doneList').querySelector('.dcard [data-again]')`, { what: 'Relancer sur la terminée' });
  await page.eval(`(b => { b.click(); b.click(); })($('doneList').querySelector('.dcard [data-again]'))`);
  await page.waitFor(`pageJobs.length === 2`, { what: 'relance suivie' });
  await bench.idle({ page });
  assert.equal(await page.eval(`sentBodies.length`), 2, 'une seule demande en plus');
  page.assertNoErrors();
});
