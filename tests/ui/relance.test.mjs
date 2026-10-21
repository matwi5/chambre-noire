// « Relancer », dans la vue du téléphone : la même demande avec une nouvelle graine, sans toucher la saisie, depuis une
// terminée (demande gardée par la page : une image, ou tout le lot depuis sa carte, variantes ou campagne), un échec ou
// la visionneuse (galerie : demande reconstruite de l'image, absente pour un masque), dans l'espace affiché et avec
// l'interrupteur incognito du moment, sauf une image incognito, toujours relancée en incognito, puis la page En cours.
// La demande envoyée est lue au passage (fetch enveloppé).
//   node --test tests/ui/relance.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/relance.test.mjs)
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
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices();
    window.sentBodies = []; const f = window.fetch; window.fetch = (u, o) => {
      if (String(u).endsWith('/api/generate')) sentBodies.push(JSON.parse(o.body)); return f(u, o); }`);
}
const type = text => page.eval(`(() => { const t = $('prompt'); t.value = ${JSON.stringify(text)};
  t.dispatchEvent(new Event('input')); })()`);
// texte tapé dans Créer puis « Générer » : la page passe à En cours
async function go(text) {
  if (await page.eval(`mode`) !== 'create') await page.click('#tabbar [data-pane="create"]');
  await type(text);
  const n = await page.eval(`sentBodies.length`);
  await page.click('#go');
  await page.waitFor(`mode === 'run' && sentBodies.length > ${n}`, { what: 'demande acceptée, page En cours' });
}
const settled = () => page.waitFor(`fetch('/api/status').then(r => r.json())
  .then(s => !s.busy && !s.queue.length && !pageJobs.some(isActive))`, { what: 'Mac au repos', timeout: 30000 });
// « Relancer » (sélecteur) : la demande suivante part, la page est sur En cours ; rend cette demande, images réduites à
// leur nombre (les dimensions seules pour une campagne)
async function again(selector) {
  const [n, jobs] = await page.eval(`[sentBodies.length, pageJobs.length]`);
  await page.click(selector);
  await page.waitFor(`sentBodies.length > ${n} && pageJobs.length > ${jobs} && mode === 'run'`,
    { what: 'demande relancée, suivie, page En cours' });
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
  await page.click('#tabbar [data-pane="hist"]');
  const at = `histItems.findIndex(it => it.prompt === ${JSON.stringify(prompt)})`;
  await page.waitFor(`${at} >= 0`, { what: 'image dans la galerie' });
  await page.eval(`openViewer(${at}, histItems)`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
}
const shown = sel => page.eval(`(el => !!el && !el.hidden && el.getClientRects().length > 0)
  (document.querySelector(${JSON.stringify(sel)}))`);

test('terminée : la même demande, nouvelle graine, saisie intacte, page En cours', async () => {
  await fresh();
  await go('zl1 phare');
  await settled();
  await page.click('#tabbar [data-pane="create"]');
  await type('texte suivant');
  await page.click('#tabbar [data-pane="run"]');
  await page.waitFor(`!!$('doneList').querySelector('.dcard [data-again]')`, { what: 'Relancer sur la terminée' });
  const b = await again('#doneList .dcard [data-again]');
  assert.deepEqual(b, { ...await sent(0) }, 'la même demande');
  assert.equal(b.seed, -1, 'nouvelle graine (tirée par le Mac)');
  assert.equal(await page.eval(`pageJobs.length`), 2, 'suivie par la page');
  await page.click('#tabbar [data-pane="create"]');
  assert.equal(await page.eval(`$('prompt').value`), 'texte suivant', 'saisie intacte');
  await settled();
  page.assertNoErrors();
});

test('lot de variantes : la carte relance tout le lot, une image du lot (visionneuse) une seule image', async () => {
  await fresh();
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices()`);
  await go('zl2 variantes');
  await settled();
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);   // le réglage du moment ne compte pas
  await page.waitFor(`!!$('doneList').querySelector('.dlot [data-again]')`, { what: 'Relancer sur la carte du lot' });
  const lot = await again('#doneList .dlot [data-again]');
  assert.equal(lot.count, 2, 'tout le lot');
  assert.equal(lot.prompt, 'zl2 variantes');
  await settled();
  await page.click('#doneList .dlot [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  const one = await again('#vAgain');
  assert.equal(one.count, undefined, 'une seule image');
  assert.equal(one.prompt, 'zl2 variantes');
  assert.equal(await page.eval(`$('viewer').classList.contains('on')`), false, 'visionneuse fermée');
  await settled();
  page.assertNoErrors();
});

test('campagne : la carte relance les mêmes photos, une image du lot sa seule photo, à ses dimensions', async () => {
  await fresh();
  await page.click('#tabbar [data-pane="create"]');
  await addImage('#c02020');
  await addImage('#2060c0');
  await page.eval(`$('campChk').click()`);
  await go('zl3 campagne');
  await page.eval(`$('campChk').click()`);
  await settled();
  await page.waitFor(`!!$('doneList').querySelector('.dlot [data-again]')`, { what: 'Relancer sur la carte du lot' });
  const lot = await again('#doneList .dlot [data-again]');
  assert.deepEqual(lot.campaign, (await sent(0)).campaign, 'les mêmes photos');
  assert.equal(await page.eval(`sentBodies[1].campaign.length === 2
    && sentBodies[1].campaign.every((c, k) => c.image === sentBodies[0].campaign[k].image)`), true);
  await settled();
  await page.eval(`openViewer(doneView.findIndex(it => it.lot && it.lot.rank === 2 && it.page.req === pageJobs[0].req),
    doneView)`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  const one = await again('#vAgain');
  assert.equal(one.campaign, undefined, 'une seule photo');
  assert.deepEqual([one.mode, one.ref_images], ['edit', 1]);
  assert.equal(await page.eval(`sentBodies.at(-1).ref_images[0] === sentBodies[0].campaign[1].image
    && sentBodies.at(-1).width === sentBodies[0].campaign[1].width`), true, 'la photo 2, à ses dimensions');
  await settled();
  page.assertNoErrors();
});

test('échec : « Relancer » sur la carte de l\'échec', async () => {
  await fresh();
  await go('zl4 FAIL');
  await settled();
  await page.waitFor(`!!$('doneList').querySelector('.dcard.fail [data-again]')`, { what: 'Relancer sur l\'échec' });
  const b = await again('#doneList .dcard.fail [data-again]');
  assert.equal(b.prompt, 'zl4 FAIL');
  await settled();
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
  await settled();
  await view('zl5 edition');
  const edit = await again('#vAgain');
  assert.deepEqual([edit.mode, edit.prompt, edit.width, edit.height, edit.steps, edit.ref_images, edit.seed],
    ['edit', 'zl5 edition', 512, 512, 8, 2, -1]);
  await settled();
  await view('zl6 annotation');
  const annot = await again('#vAgain');
  assert.deepEqual([annot.mode, annot.ref_images, annot.seed], ['annot', 1, -1], 'graine 1234 de l\'image : nouvelle');
  await settled();
  await view('zl7 masque');
  assert.equal(await shown('#vAgain'), false, 'pas de Relancer pour un masque de la galerie');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});

test('espace et incognito du moment : incognito activé, puis dans l\'espace privé', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 't2i', prompt: 'zl9 publique' }`), 202);
  await settled();
  await page.click('#tabbar [data-pane="create"]');
  await page.click('#incog');
  await view('zl9 publique');
  const incog = await again('#vAgain');
  assert.deepEqual([incog.incognito, incog.private], [true, undefined], 'incognito');
  await settled();
  await page.eval(`$('incog').click()`);
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  assert.equal(await send(`{ mode: 't2i', prompt: 'zl8 privee', private: true }`), 202);
  await settled();
  await view('zl8 privee');
  const priv = await again('#vAgain');
  assert.deepEqual([priv.private, priv.incognito, priv.prompt], [true, false, 'zl8 privee']);
  await settled();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('« Générer » avec une image : le format choisi reste pour la demande suivante', async () => {
  await fresh();
  await page.click('#tabbar [data-pane="create"]');
  await addImage('#c02020');
  await page.eval(`opt.ratio = '16:9'; saveOpt(); refreshChoices()`);
  await go('zl10 format');
  assert.equal(await page.eval(`opt.ratio`), '16:9', 'pas remplacé par « Image », puis 1:1');
  await settled();
  page.assertNoErrors();
});

test('double appui sur « Relancer » d\'une terminée : une seule relance', async () => {
  await fresh();
  await go('zl11 double');
  await settled();
  await page.waitFor(`!!$('doneList').querySelector('.dcard [data-again]')`, { what: 'Relancer sur la terminée' });
  await page.eval(`(b => { b.click(); b.click(); })($('doneList').querySelector('.dcard [data-again]'))`);
  await page.waitFor(`pageJobs.length === 2`, { what: 'relance suivie' });
  await settled();
  assert.equal(await page.eval(`sentBodies.length`), 2, 'une seule demande en plus');
  page.assertNoErrors();
});

test('image incognito : relancée en incognito, interrupteur éteint (terminée, carte de lot, visionneuse)', async () => {
  await fresh();
  await page.click('#tabbar [data-pane="create"]');
  await page.click('#incog');
  await go('zl12 incognito');
  await settled();
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices()`);
  await go('zl13 lot incognito');
  await settled();
  await page.eval(`opt.count = 1; saveOpt(); $('incog').click()`);   // interrupteur éteint
  assert.equal(await page.eval(`incogOn`), false);
  const one = await again('#doneList .dcard:not(.dlot):not(.fail) [data-again]');
  assert.deepEqual([one.prompt, one.incognito], ['zl12 incognito', true], 'terminée');
  await settled();
  const lot = await again('#doneList .dlot [data-again]');
  assert.deepEqual([lot.prompt, lot.count, lot.incognito], ['zl13 lot incognito', 2, true], 'carte du lot');
  await settled();
  await page.click('#doneList .dlot [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  const viewed = await again('#vAgain');
  assert.deepEqual([viewed.count, viewed.incognito], [undefined, true], 'visionneuse');
  await settled();
  assert.deepEqual(await page.eval(`Object.values({ ...localStorage }).filter(v => v.includes('zl1'))`), [],
    'localStorage fouillé');
  page.assertNoErrors();
});

test('échec incognito : relancé en incognito, interrupteur éteint', async () => {
  await fresh();
  await page.click('#tabbar [data-pane="create"]');
  await page.click('#incog');
  await go('zl14 FAIL incognito');
  await settled();
  await page.eval(`$('incog').click()`);
  const b = await again('#doneList .dcard.fail [data-again]');
  assert.equal(b.incognito, true);
  await settled();
  page.assertNoErrors();
});

test('terminée normale : relancée en incognito quand l\'interrupteur est allumé', async () => {
  await fresh();
  await go('zl15 normale');
  await settled();
  await page.eval(`$('incog').click()`);           // allumé après la génération
  const b = await again('#doneList .dcard [data-again]');
  assert.deepEqual([b.prompt, b.incognito], ['zl15 normale', true]);
  await settled();
  page.assertNoErrors();
});
