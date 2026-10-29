// Reprises, dans la vue du téléphone. Génération reprise par une page qui ne l'a pas lancée (après un rechargement,
// depuis un autre appareil) : la page en retrouve le prompt complet (la file n'en donne que les 80 premiers
// caractères). Geste « Reprendre » de la visionneuse : texte, images d'entrée et dessin de l'image selon son mode
// (édition, masque, annotation reprise en édition, texte → image), réglages de l'image, confirmation si la saisie n'est
// pas vide ; images lues dans la galerie publique, privée ou la demande gardée par la page ; absent sans images
// d'entrée connues ; saisie visée notée avant la lecture (espace changé pendant l'attente).
//   venv/bin/python tests/check.py --quick --ui tests/ui/reprise.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page, held = null;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // lecture d'une image d'entrée retenue (holdInput) : la première demandée, hors miniatures ; les autres passent
  page.on('Fetch.requestPaused', p => {
    if (held && !held.id && !p.request.url.includes('thumb=1')) { held.id = p.requestId; held.resolve(); }
    else page.send('Fetch.continueRequest', { requestId: p.requestId });
  });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// plus de 80 caractères ; HOLD=<nom> : la génération reste en file jusqu'à bench.release(nom) (voir
// tests/fake_sdcli.py), un nom par test (une libération vaut jusqu'à la fin du banc)
const TEXT = ' zq6 un phare au crépuscule, une mer agitée, des embruns dorés, un ciel violet, '
  + 'des mouettes au loin et une petite maison blanche au pied du phare';
const LONG = 'HOLD=lot' + TEXT, LONG_PRIV = 'HOLD=privee' + TEXT;
const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
const queue = () => page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.queue.map(e => e.prompt))`);

test('rechargement : un lot repris montre le prompt complet et « Reprendre » rend le texte entier', async () => {
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.ready();
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices();`);
  await page.typePrompt(LONG);
  await page.click('#go');
  await page.waitFor(`pageJobs.length === 2`, { what: 'lot de deux images suivi par la page' });

  await page.goto(bench.url + '/');                // rechargement : la page reprend le lot depuis la file
  await page.waitFor(`pageJobs.length === 2`, { what: 'lot repris après le rechargement' });
  const excerpts = await queue();
  assert.ok(excerpts.length > 0 && excerpts.every(p => p.length < LONG.length), 'la file n\'a qu\'un extrait');
  assert.deepEqual(await page.eval(`pageJobs.map(p => p.prompt)`), [LONG, LONG]);
  bench.release('lot');
  await page.waitFor(`pileView().filter(it => it.page && it.page.prompt === ${JSON.stringify(LONG)}).length === 2`,
    { what: 'lot terminé dans la pile', timeout: 30000 });
  assert.equal(await page.topPrompt(), LONG, 'prompt du lot');

  await page.click('#pile [data-k="0"] [data-open]');   // visionneuse depuis la pile, puis « Reprendre »
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  await page.eval(`$('prompt').value = ''`);
  await page.click('#vResume');
  await page.waitFor(`!$('viewer').classList.contains('on')`, { what: 'texte repris, visionneuse fermée' });
  assert.equal(await page.eval(`$('prompt').value`), LONG);
  await page.eval(`opt.count = 1; saveOpt();`);
  page.assertNoErrors();
});

test('espace privé : une génération privée lancée d\'un autre appareil est reprise avec son prompt complet', async () => {
  await page.goto(bench.url + '/');
  await page.ready();
  assert.equal(await post('/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  // demande envoyée hors de l'interface, comme depuis un autre appareil : la page ne la suit pas encore
  assert.equal(await post('/api/generate', { mode: 't2i', prompt: LONG_PRIV, width: 512, height: 512, steps: 4, cfg: 1,
    seed: -1, preview: false, ref_images: [], private: true }), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pageJobs.some(p => p.private && p.adopted)`, { what: 'génération privée reprise de la file' });
  const excerpts = await queue();
  assert.ok(excerpts.length > 0 && excerpts.every(p => p.length < LONG_PRIV.length), 'la file n\'a qu\'un extrait');
  assert.equal(await page.eval(`pageJobs.find(p => p.private).prompt`), LONG_PRIV);
  bench.release('privee');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  await bench.idle();
  page.assertNoErrors();
});

// « Reprendre » ------------------------------------------------------------------------------------------------------
// image de référence (data URL) dessinée dans la page, de la couleur donnée
const ref = color => `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '${color}'; x.fillRect(0, 0, 256, 256);
  return c.toDataURL('image/png'); })()`;
// une génération envoyée hors de l'interface (comme d'un autre appareil), 512×512 en 8 étapes : Carré, 360p, Low
const send = body => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 8, cfg: 1, seed: -1,
  preview: false, ref_images: [], ...${body} }).then(r => r.status)`);
// couleur du centre de chaque image d'entrée de la saisie affichée
const colors = () => page.eval(`inputImages.map(x => { const c = document.createElement('canvas');
  c.width = c.height = 1; const g = c.getContext('2d'); g.drawImage(x.img, x.w / 2, x.h / 2, 1, 1, 0, 0, 1, 1);
  const hex = v => v.toString(16).padStart(2, '0');
  return '#' + [...g.getImageData(0, 0, 1, 1).data.slice(0, 3)].map(hex).join(''); })`);
const saisie = () => page.eval(`({ text: $('prompt').value, n: inputImages.length, drawOn, mask: maskMode(),
  traced: paintedPixels(), kind: inputKind(), ratio: opt.ratio, res: opt.res, steps: opt.steps })`);
const draft = () => page.eval(`localStorage.getItem('qwen-prompt')`);
async function fresh() {
  await bench.idle();                              // rien en file : la page rechargée ne reprend rien
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.ready();
}
async function enterPrivate() {
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
// les images de la pile gardées par ✓, puis la visionneuse des Tirages sur l'image au prompt donné
async function view(prompt) {
  await page.keepPile();
  await page.tab('tirages');
  const at = `histItems.findIndex(it => it.prompt === ${JSON.stringify(prompt)})`;
  await page.waitFor(`${at} >= 0`, { what: 'image dans la galerie' });
  await page.eval(`openViewer(${at}, histItems)`);
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
}
const resumable = () => page.eval(`!$('vResume').hidden`);
// la prochaine lecture d'une image d'entrée de la galerie publique attend releaseInput()
async function holdInput() {
  held = Promise.withResolvers();
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/input?*', requestStage: 'Request' }] });
}
async function releaseInput() {
  await held.promise;
  await page.send('Fetch.continueRequest', { requestId: held.id });
  await page.send('Fetch.disable');
  held = null;
}
const SQUARE_LOW = { ratio: '1:1', res: 'low', steps: 'low' };   // réglages d'une image 512×512 en 8 étapes

test('« Reprendre » une édition : texte, références, réglages, confirmée ; refus : rien ne bouge', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 'edit', prompt: 'zr1 edition',
    ref_images: [${ref('#c02020')}, ${ref('#2060c0')}] }`), 202);
  await bench.idle();
  await page.eval(`opt.ratio = '16:9'; opt.res = 'high'; opt.steps = 'max'; campaignOn = $('campChk').checked = true;
    saveOpt(); refreshChoices()`);
  await page.typePrompt('texte en cours');
  await view('zr1 edition');
  assert.equal(await resumable(), true);
  await page.click('#vResume');
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation : la saisie n\'est pas vide' });
  await page.eval(`answer(false)`);
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length, opt.ratio]`),
    ['texte en cours', 0, '16:9']);

  await view('zr1 edition');
  await page.click('#vResume');
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation' });
  await page.eval(`answer(true)`);
  await page.waitFor(`mode === 'labo' && inputImages.length === 2`, { what: 'image reprise, Labo' });
  assert.deepEqual(await saisie(), { text: 'zr1 edition', n: 2, drawOn: false, mask: 'mask', traced: 0, kind: 'edit',
    ...SQUARE_LOW });
  assert.deepEqual(await colors(), ['#c02020', '#2060c0'], 'les références, dans l\'ordre');
  assert.equal(await page.eval(`inCampaign()`), false, 'une édition à deux références, pas une campagne');
  assert.equal(await draft(), 'zr1 edition', 'brouillon public');
  page.assertNoErrors();
});

test('« Reprendre » un dessin : masque sur l\'image de départ, tracé vide ; annotation en édition', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 'mask', prompt: 'zr2 masque', init_image: ${ref('#30a050')},
    mask_image: ${ref('#ffffff')}, ref_images: [${ref('#808080')}] }`), 202);
  assert.equal(await send(`{ mode: 'annot', prompt: 'zr3 annotation', ref_images: [${ref('#a040c0')}] }`), 202);
  await bench.idle();
  await page.eval(`setMaskMode('annotation')`);
  await view('zr2 masque');
  await page.click('#vResume');                   // saisie vide : sans confirmation
  await page.waitFor(`mode === 'labo' && drawOn`, { what: 'dessin repris' });
  assert.equal(await page.eval(`openedSheet`), null, 'aucune confirmation');
  assert.deepEqual(await saisie(), { text: 'zr2 masque', n: 1, drawOn: true, mask: 'mask', traced: 0, kind: 'mask',
    ...SQUARE_LOW });
  assert.deepEqual(await colors(), ['#30a050'], 'l\'image de départ');

  await view('zr3 annotation');
  await page.click('#vResume');
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation' });
  await page.eval(`answer(true)`);
  await page.waitFor(`mode === 'labo' && $('prompt').value === 'zr3 annotation'`, { what: 'annotation reprise' });
  assert.deepEqual(await saisie(), { text: 'zr3 annotation', n: 1, drawOn: false, mask: 'mask', traced: 0,
    kind: 'edit', ...SQUARE_LOW });
  assert.deepEqual(await colors(), ['#a040c0'], 'la référence annotée');
  page.assertNoErrors();
});

test('« Reprendre » un texte → image : le texte seul, sans images ; absent sans images d\'entrée connues', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 't2i', prompt: 'zr4 texte' }`), 202);
  assert.equal(await send(`{ mode: 'edit', prompt: 'zr4 edition', ref_images: [${ref('#c02020')}] }`), 202);
  await bench.idle();
  await page.eval(`(async () => { inputImages.push(await toEntry('a.png', ${ref('#204080')})); renderInputs(); })()`);
  await page.waitFor(`inputImages.length === 1`, { what: 'une image dans la saisie' });
  await view('zr4 texte');
  await page.click('#vResume');
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation : des images dans la saisie' });
  await page.eval(`answer(true)`);
  await page.waitFor(`mode === 'labo' && $('prompt').value === 'zr4 texte'`, { what: 'texte repris' });
  assert.deepEqual(await saisie(), { text: 'zr4 texte', n: 0, drawOn: false, mask: 'mask', traced: 0, kind: 't2i',
    ...SQUARE_LOW });

  // image ancienne, dont la galerie ne garde pas les images d'entrée : pas de « Reprendre » pour une édition ou un
  // dessin ; un texte → image n'en a pas besoin
  await view('zr4 edition');
  assert.equal(await resumable(), true);
  await page.eval(`(() => { const k = histItems.findIndex(it => it.prompt === 'zr4 edition');
    histItems[k] = { ...histItems[k], inputs: [] }; openViewer(k, histItems); })()`);
  assert.equal(await resumable(), false, 'édition sans images d\'entrée connues');
  await page.eval(`openViewer(histItems.findIndex(it => it.prompt === 'zr4 texte'), histItems)`);
  assert.equal(await resumable(), true, 'texte → image');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});

test('« Reprendre » une image de la pile lancée ici : images de sa demande gardée, brouillon écrit', async () => {
  await fresh();
  await page.eval(`(async () => { inputImages.push(await toEntry('b.png', ${ref('#d08020')})); renderInputs(); })()`);
  await page.waitFor(`inputImages.length === 1`, { what: 'une image dans la saisie' });
  await page.typePrompt('zr5 terminee');
  await page.click('#go');
  // la carte du dessus charge aussi en avance l'image d'entrée de son bouton Avant, une fois son image affichée :
  // attendue avant la visionneuse, qui reprend ce chargement au lieu d'en lancer un second
  await page.waitFor(`pileView()[0]?.prompt === 'zr5 terminee'`,
    { what: 'image arrivée dans la pile', timeout: 30000 });
  await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus');
  await page.viewPile('zr5 terminee');
  assert.equal(await resumable(), true);
  // la visionneuse charge en avance la première image d'entrée (par /api/input) : attendue avant de compter
  await page.waitFor(`ready.get(inputUrl(vList[vIndex], vList[vIndex].inputs[0]))?.im !== undefined`,
    { what: 'image d\'entrée préchargée' });
  await page.eval(`performance.clearResourceTimings()`);
  await page.click('#vResume');
  await page.waitFor(`mode === 'labo' && inputImages.length === 1`, { what: 'image reprise' });
  assert.deepEqual(await page.eval(`performance.getEntriesByType('resource').map(e => e.name)
    .filter(u => u.includes('/api/input') && !u.includes('thumb=1'))`), [], 'lue dans la demande gardée par la page');
  assert.equal(await page.eval(`$('prompt').value`), 'zr5 terminee');
  assert.deepEqual(await colors(), ['#d08020']);
  assert.equal(await draft(), 'zr5 terminee', 'texte repris écrit en brouillon public');
  page.assertNoErrors();
});

test('« Reprendre » une image privée : images lues dans l\'espace privé, rien d\'elle après « Sortir »', async () => {
  await fresh();
  await enterPrivate();
  assert.equal(await send(`{ mode: 'edit', prompt: 'zr6 privee', ref_images: [${ref('#106070')}], private: true }`),
    202);
  await bench.idle();
  await view('zr6 privee');
  await page.click('#vResume');
  await page.waitFor(`mode === 'labo' && inputImages.length === 1`, { what: 'image privée reprise' });
  assert.deepEqual(await colors(), ['#106070']);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length,
    document.documentElement.outerHTML.includes('zr6 privee')]`), ['', 0, false]);
  page.assertNoErrors();
});

test('« Reprendre » : espace changé pendant la lecture, l\'image va dans la saisie de l\'espace du geste', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 'edit', prompt: 'zr7 course', ref_images: [${ref('#c02020')}, ${ref('#2060c0')}] }`),
    202);
  await bench.idle();
  await view('zr7 course');
  await holdInput();
  await page.click('#vResume');                    // saisie publique vide : lecture tout de suite
  await held.promise;                              // première image d'entrée demandée, pas encore reçue
  await enterPrivate();
  await releaseInput();
  await page.waitFor(`asideInput && asideInput.images.length === 2`, { what: 'images dans la saisie publique' });
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length]`), ['', 0], 'saisie privée intacte');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length]`), ['zr7 course', 2]);
  assert.deepEqual(await colors(), ['#c02020', '#2060c0']);
  assert.equal(await draft(), 'zr7 course', 'brouillon public, comme la saisie');
  page.assertNoErrors();
});

test('« Reprendre » : un texte tapé pendant la lecture n\'est pas remplacé sans confirmation', async () => {
  await fresh();
  assert.equal(await send(`{ mode: 'edit', prompt: 'zr8 frappe', ref_images: [${ref('#c02020')}] }`), 202);
  await bench.idle();
  await view('zr8 frappe');
  await holdInput();
  await page.click('#vResume');                    // saisie vide : sans confirmation, lecture en cours
  await held.promise;
  await page.typePrompt('tapé pendant la lecture');
  await releaseInput();
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation demandée' });
  await page.eval(`answer(false)`);
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length]`), ['tapé pendant la lecture', 0]);
  page.assertNoErrors();
});

test('« Éditer » une image de la pile : image ajoutée à la saisie, brouillon public gardé', async () => {
  await fresh();
  await page.typePrompt('zr11 normale');
  await page.click('#go');
  await page.typePrompt('texte public');
  await page.viewPile('zr11 normale');
  await page.click('#viewer .v-acts .act');         // Éditer
  await page.waitFor(`mode === 'labo' && inputImages.length === 1`, { what: 'image ajoutée' });
  // le champ de création, sous la pile, est amené à l'écran
  await page.waitFor(`(r => r.top >= 0 && r.top < innerHeight)($('refs').getBoundingClientRect())`,
    { what: 'images d\'entrée à l\'écran' });
  assert.deepEqual(await page.eval(`[$('toastBox').textContent, $('prompt').value]`),
    ['Ajoutée aux images d\'entrée', 'texte public']);
  assert.equal(await draft(), 'texte public');
  page.assertNoErrors();
});
