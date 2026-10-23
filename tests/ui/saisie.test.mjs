// Saisie, dans la vue du téléphone : page Créer unique (un champ de texte, une liste d'images d'entrée : sans image la
// demande part en texte → image, avec des images en édition, dessin actif en masque ou annotation ; exemple du champ
// selon la saisie ; Campagne proposée à partir de 2 images), bouton Dessiner (selon le nombre d'images, ajout refusé
// pendant le dessin, tracé gardé en désactivant et effacé avec son image), geste « Dessiner », collage d'une image,
// images choisies d'un coup, champs vidés après « Générer », saisie propre à chaque espace (public, privé), variantes
// avec ou sans images et en dessin, hors campagne.
//   venv/bin/python tests/check.py --quick --ui tests/ui/saisie.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { startBench, launchChrome } from './driver.mjs';

// PNG gris de w×h pixels (assez grand pour qu'on puisse peindre dessus), du niveau de gris donné
function png(w, h, gray = 128) {
  const chunk = (type, data) => { const len = Buffer.alloc(4), crc = Buffer.alloc(4), td = Buffer.concat([Buffer.from(type), data]);
    len.writeUInt32BE(data.length); crc.writeUInt32BE(zlib.crc32(td)); return Buffer.concat([len, td, crc]); };
  const head = Buffer.alloc(13); head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 0;   // 8 bits, gris
  const rows = Buffer.alloc((w + 1) * h, gray); for (let y = 0; y < h; y++) rows[y * (w + 1)] = 0;   // filtre 0
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', head), chunk('IDAT', zlib.deflateSync(rows)), chunk('IEND', Buffer.alloc(0))]);
}
let bench, chrome, page, dir, refusal = null, held = null;

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-photos-'));
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // demandes de génération interceptées (Fetch.enable, voir generate) : le Mac répond par une erreur, ou est injoignable ;
  // 'hold' : la demande attend que le test la laisse partir (held)
  page.on('Fetch.requestPaused', p => refusal === 'hold' ? held.resolve(p.requestId)
    : refusal === 'unreachable' ? page.send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'ConnectionRefused' })
    : page.send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 503,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }], body: Buffer.from('{"error":"moteur non prêt"}').toString('base64') }));
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
  if (dir) fs.rmSync(dir, { recursive: true, force: true });
});

// page neuve (brouillons effacés) sur un onglet
async function fresh(pane = 'create') {
  await bench.idle();                              // rien en file : la page rechargée ne reprend rien
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  if (pane !== 'create') await page.click(`#tabbar [data-pane="${pane}"]`);
  await page.waitFor(`$('pane-${pane}').classList.contains('active')`);
}

// une photo de ce gris (gris moyen par défaut) ; un autre gris : une adresse data: que la page n'a jamais affichée
function photo(name, gray = 128) {
  const file = path.join(dir, name);
  fs.writeFileSync(file, png(320, 320, gray));
  return file;
}

function photos(n) {
  return Array.from({ length: n }, (_, i) => photo(`photo-${String(i + 1).padStart(2, '0')}.png`));
}

test('Créer : trois photos choisies d\'un coup sont toutes ajoutées, dans l\'ordre', async () => {
  await fresh();
  await page.setFiles('#inFiles', photos(3));
  await page.waitFor(`$('inThumbs').children.length === 3`, { what: 'trois vignettes', timeout: 5000 });
  assert.deepEqual(await page.eval(`inputImages.map(x => x.name)`), ['photo-01.png', 'photo-02.png', 'photo-03.png']);
  page.assertNoErrors();
});

test('Créer : sur douze photos choisies, dix sont ajoutées et le surplus est annoncé', async () => {
  await fresh();
  const files = photos(12);
  await page.setFiles('#inFiles', files);
  await page.waitFor(`$('toastBox').classList.contains('on') && $('toastBox').textContent.includes('2 non ajoutées')`,
    { what: 'message du surplus', timeout: 5000 });
  assert.deepEqual(await page.eval(`inputImages.map(x => x.name)`), files.slice(0, 10).map(f => path.basename(f)));
  assert.equal(await page.eval(`$('inThumbs').children.length`), 10);
  page.assertNoErrors();
});

test('Créer : un fichier illisible est annoncé et n\'arrête pas les images suivantes', async () => {
  await fresh();
  const bad = path.join(dir, 'abime.png');
  fs.writeFileSync(bad, 'pas une image');
  const [a, b] = photos(2);
  await page.setFiles('#inFiles', [a, bad, b]);
  await page.waitFor(`$('toastBox').classList.contains('on') && $('toastBox').textContent.includes('illisible')`,
    { what: 'message du fichier illisible', timeout: 5000 });
  assert.deepEqual(await page.eval(`inputImages.map(x => x.name)`), ['photo-01.png', 'photo-02.png']);
  assert.equal(await page.eval(`$('inThumbs').children.length`), 2, 'chaque image ajoutée est visible');
  page.assertNoErrors();
});

test('« Éditer » depuis la galerie : l\'image rejoint les images d\'entrée, page Créer, 10 au plus', async () => {
  await fresh();
  await page.typePrompt('un phare à éditer');
  await generate();
  await page.waitFor(`pageJobs.at(-1).result`, { what: 'image finie', timeout: 30000 });
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length > 0`, { what: 'galerie' });
  await page.eval(`openViewer(0, histItems); viewerAction('edit')`);
  await page.waitFor(`mode === 'create' && inputImages.length === 1 && $('inThumbs').children.length === 1`,
    { what: 'image ajoutée, page Créer' });
  assert.equal(await page.eval(`$('inThumbs').querySelector('span').textContent`), '1', 'numérotée');
  await page.setFiles('#inFiles', photos(9));
  await page.waitFor(`inputImages.length === 10`, { what: 'dix images' });
  await page.click('#tabbar [data-pane="hist"]');
  await page.eval(`openViewer(0, histItems); viewerAction('edit')`);
  await page.waitFor(`$('toastBox').textContent === '10 images d\\'entrée au maximum'`, { what: 'plafond annoncé' });
  assert.equal(await page.eval(`inputImages.length`), 10);
  page.assertNoErrors();
});

const draft = () => page.eval(`localStorage.getItem('qwen-prompt')`);
const settings = () => page.eval(`JSON.stringify({ opt, campaignOn, preview: $('previewChk').checked })`);

// un trait de pinceau dans le quart haut gauche de l'image du dessin ; souris : événements pointeur réels
async function paint() {
  await page.waitFor(`$('paintCanvas').getBoundingClientRect().width > 0`, { what: 'zone de dessin à sa taille' });
  const box = await page.eval(`(() => { const c = $('paintCanvas'); c.scrollIntoView({ block: 'center' });
    const r = c.getBoundingClientRect(); return { x: r.left + r.width / 4, y: r.top + r.height / 4 }; })()`);
  for (const [kind, dx] of [['mousePressed', 0], ['mouseMoved', 4], ['mouseReleased', 4]])
    await page.send('Input.dispatchMouseEvent', { type: kind, x: box.x + dx, y: box.y, button: 'left', buttons: kind === 'mouseReleased' ? 0 : 1, clickCount: 1 });
  await page.waitFor(`paintedPixels() > 0`, { what: 'zone peinte' });
}

// « Générer » ; refuse : 'error' (le Mac répond par une erreur) ou 'unreachable' (Mac injoignable), simulés au niveau
// du réseau de Chrome. Demande acceptée : la page passe à En cours, puis le test revient à l'onglet de saisie ;
// refusée : elle reste sur l'onglet
async function generate({ refuse = null } = {}) {
  refusal = refuse;
  if (refuse) await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Request' }] });
  const jobsBefore = await page.eval(`pageJobs.length`), tab = await page.eval(`mode`);
  await page.click('#go');
  if (refuse) {
    const shown = refuse === 'unreachable' ? 'Serveur injoignable' : 'Erreur : moteur non prêt';
    await page.waitFor(`$('toastBox').textContent.startsWith(${JSON.stringify(shown)})`, { what: 'refus affiché' });
    await page.send('Fetch.disable');
    assert.equal(await page.eval(`mode`), tab, 'demande refusée : la page reste sur l\'onglet');
  } else {
    await page.waitFor(`pageJobs.length > ${jobsBefore} && mode === 'run'`,
      { what: 'génération suivie, page En cours' });
    await page.click(`#tabbar [data-pane="${tab}"]`);
  }
}

// dernière génération lancée par la page : son mode (vu par le Mac) et son lot (taille, marqueur de campagne)
const lastJob = () => page.eval(`(p => ({ mode: p.j.mode,
  lot: p.lot && { size: p.lot.size, campaign: p.lot.campaign } }))(pageJobs.at(-1))`);
const tabs = () => page.eval(`[...document.querySelectorAll('#tabbar button')].map(b => b.dataset.pane)`);
const SHOWN = `!!$('paintCanvas').getClientRects().length`;   // zone de dessin affichée
// une image d'entrée, puis Dessiner activé dessus
async function drawOne() {
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 1`, { what: 'une image d\'entrée' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn && ${SHOWN}`, { what: 'dessin actif' });
}
const toastSays = text => page.waitFor(`$('toastBox').classList.contains('on')
  && $('toastBox').textContent === ${JSON.stringify(text)}`, { what: `message « ${text} »` });
const REFUSED = 'Désactivez Dessiner pour ajouter d\'autres images';

test('Dessiner : sans image, choix d\'une image puis dessin ; à plusieurs images, grisé et expliqué', async () => {
  await fresh();
  await page.eval(`$('drawFile').addEventListener('click', e => { window.chooser = true; e.preventDefault(); },
    { once: true })`);
  await page.click('#drawBtn');
  assert.equal(await page.eval(`!!window.chooser && !drawOn`), true, 'choix d\'une image ouvert');
  await page.setFiles('#drawFile', photos(1));
  await page.waitFor(`inputImages.length === 1 && drawOn && ${SHOWN}`, { what: 'image choisie, dessin actif' });
  assert.match(await page.eval(`$('prompt').placeholder`), /^Que mettre dans la zone peinte/);
  // Masque et Annotation : chaque texte au milieu de son bouton, à la hauteur de la lentille qui le surligne
  assert.deepEqual(await page.eval(`[...$('mask_mode').children].map(l => {
    const a = l.getBoundingClientRect(), s = l.parentElement.getBoundingClientRect();
    return Math.round(Math.abs((a.top + a.bottom) - (s.top + s.bottom)) / 2); })`), [0, 0], 'texte décentré');
  await page.click('#drawBtn');                    // une image : le bouton éteint le dessin
  await page.waitFor(`!drawOn && !${SHOWN}`, { what: 'dessin éteint' });
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  assert.equal(await page.eval(`$('drawBtn').disabled`), true, 'grisé à deux images');
  assert.equal(await page.eval(`$('drawHint').textContent`), 'Dessiner se fait sur une seule image');
  assert.equal(await page.eval(`!!$('drawHint').getClientRects().length`), true, 'explication visible');
  page.assertNoErrors();
});

test('Dessiner : ajout refusé pendant le dessin ; tracé gardé en désactivant, effacé avec son image', async () => {
  await fresh();
  await drawOne();
  await paint();
  await page.setFiles('#inFiles', photos(1));      // choix de fichiers, puis appui sur la tuile d'ajout
  await toastSays(REFUSED);
  await page.eval(`$('toastBox').classList.remove('on')`);
  await page.click('#inDrop');
  await toastSays(REFUSED);
  assert.equal(await page.eval(`inputImages.length`), 1);
  assert.equal(await page.eval(`campaignShown()`), false);
  await page.click('#drawBtn');                    // éteint : tracé gardé, la demande serait une édition
  await page.waitFor(`!drawOn && inputKind() === 'edit'`, { what: 'dessin éteint' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn && paintedPixels() > 0`, { what: 'tracé retrouvé' });
  await page.click('#drawBtn');
  await page.click('#inThumbs .thumb button');     // l'image retirée emporte son tracé
  await page.waitFor(`!inputImages.length && !drawOn`, { what: 'image retirée' });
  assert.equal(await page.eval(`paintedPixels()`), 0);
  await drawOne();
  assert.equal(await page.eval(`paintedPixels()`), 0, 'nouvelle image : tracé vierge');
  page.assertNoErrors();
});

test('Dessiner : la demande part en masque, ou en annotation ; sans zone peinte, refusée', async () => {
  await fresh();
  await drawOne();
  await page.typePrompt('une fenêtre ouverte');
  await page.click('#go');
  await toastSays('Peignez une zone.');
  await paint();
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'mask', lot: null });
  await drawOne();
  await page.eval(`$('mask_mode').querySelector('[value=annotation]').click()`);
  await paint();
  await page.typePrompt('une fenêtre ouverte');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'annot', lot: null });
  page.assertNoErrors();
});

// image collée (Cmd+V, « Coller ») dans le champ : événement paste avec un fichier image, ou du texte seul
const paste = kind => page.eval(`(async () => { const dt = new DataTransfer();
  if (${JSON.stringify(kind)} !== 'text') { const c = document.createElement('canvas'); c.width = c.height = 64;
    const b = await new Promise(r => c.toBlob(r, 'image/png'));
    dt.items.add(new File([b], 'image.png', { type: 'image/png' })); }
  if (${JSON.stringify(kind)} !== 'image') dt.setData('text/plain', 'texte collé');
  const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
  $('prompt').dispatchEvent(ev); return ev.defaultPrevented; })()`);

test('Collage : une image collée s\'ajoute ; un texte reste un texte ; refusé pendant le dessin', async () => {
  await fresh();
  assert.equal(await paste('text'), false, 'collage de texte laissé au champ');
  assert.equal(await paste('both'), false, 'texte accompagné d\'une image (Word, Keynote) : laissé au champ');
  assert.equal(await page.eval(`inputImages.length`), 0);
  assert.equal(await paste('image'), true);
  await page.waitFor(`inputImages.length === 1 && $('inThumbs').children.length === 1`,
    { what: 'image collée ajoutée' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn`, { what: 'dessin actif' });
  await paste('image');
  await toastSays(REFUSED);
  assert.equal(await page.eval(`inputImages.length`), 1);
  page.assertNoErrors();
});

test('geste « Dessiner » : l\'image seule, dessin actif ; confirmation s\'il y avait des images', async () => {
  await fresh();
  await page.typePrompt('un phare à dessiner');
  await generate();
  await page.waitFor(`pageJobs.at(-1).result`, { what: 'image finie', timeout: 30000 });
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length > 0`, { what: 'galerie' });
  const name = await page.eval(`histItems[0].name`);
  await page.eval(`openViewer(0, histItems); void viewerAction('mask')`);   // saisie sans image : pas de confirmation
  await page.waitFor(`mode === 'create' && drawOn && inputImages.length === 1`, { what: 'dessin sur l\'image' });
  assert.equal(await page.eval(`inputImages[0].name`), name);
  await page.click('#drawBtn');
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  await page.click('#tabbar [data-pane="hist"]');
  await page.eval(`openViewer(0, histItems); void viewerAction('mask')`);
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation' });
  assert.equal(await page.eval(`$('askText').textContent`), 'Remplacer les 2 images de la saisie par celle-ci ?');
  await page.eval(`answer(false)`);                 // refusée : rien ne change
  assert.equal(await page.eval(`inputImages.length`), 2);
  await page.eval(`openViewer(0, histItems); void viewerAction('mask')`);
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation' });
  await page.eval(`answer(true)`);
  await page.waitFor(`mode === 'create' && drawOn && inputImages.length === 1
    && inputImages[0].name === ${JSON.stringify(name)}`,
    { what: 'images remplacées, dessin actif' });
  assert.equal(await page.eval(`paintedPixels()`), 0, 'tracé vierge');
  // saisie mise de côté (espace changé pendant que le sélecteur était ouvert) qui a une image : ni question posée dans
  // l'espace affiché, ni image remplacée
  const aside = await page.eval(`(async () => { const keep = inputImages[0], n = ${JSON.stringify(name)};
    asideInput = { text: '', images: [keep], imageRatio: false,
      drawing: { on: false, mask: 'mask', image: null, pixels: null } };
    await drawFrom(n, () => dataUrlOf(n), { list: asideInput.images, priv: false });
    const r = { asked: !!openedSheet, kept: asideInput.images.length === 1 && asideInput.images[0] === keep,
      drawing: asideInput.drawing.on };
    asideInput = null; return r; })()`);
  assert.deepEqual(aside, { asked: false, kept: true, drawing: false });
  page.assertNoErrors();
});

test('Créer : sans image d\'entrée la demande part du texte, avec des images c\'est une édition', async () => {
  await fresh();
  assert.deepEqual(await tabs(), ['run', 'create', 'hist'], 'plus d\'onglet Éditer ni Dessiner');
  assert.equal(await page.eval(`$('pane-create').classList.contains('active')
    && !!$('inDrop').getClientRects().length`), true, 'ajout d\'images offert sur Créer');
  assert.match(await page.eval(`$('prompt').placeholder`), /^Décrivez l'image/);
  await page.typePrompt('un phare au crépuscule');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 't2i', lot: null });
  await page.setFiles('#inFiles', photos(2));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  assert.match(await page.eval(`$('prompt').placeholder`), /^Que faut-il changer/);
  await page.typePrompt('mettre un chapeau');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'edit', lot: null });
  assert.match(await page.eval(`$('prompt').placeholder`), /^Décrivez l'image/,
    'images parties : l\'exemple redevient celui du texte');
  page.assertNoErrors();
});

test('Créer : texte et brouillon vidés quand la demande est acceptée, Réglages inchangés', async () => {
  await fresh();
  await page.typePrompt('un phare au crépuscule');
  assert.equal(await draft(), 'un phare au crépuscule');
  const opts = await settings();
  await generate();
  assert.equal(await page.eval(`$('prompt').value`), '');
  assert.equal(await draft(), null);
  assert.equal(await settings(), opts);
  assert.equal(await page.eval(`pageJobs.at(-1).prompt`), 'un phare au crépuscule', 'la génération garde son prompt');
  page.assertNoErrors();
});

test('Créer avec des images : texte et images vidés quand la demande est acceptée', async () => {
  await fresh();
  await page.setFiles('#inFiles', photos(2));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  await page.typePrompt('mettre un chapeau');
  const opts = await settings();
  await generate();
  assert.equal(await settings(), opts);
  assert.equal(await page.eval(`$('prompt').value`), '');
  assert.equal(await page.eval(`inputImages.length + $('inThumbs').children.length`), 0);
  assert.equal(await draft(), null);
  assert.equal(await page.eval(`!!pageJobs.at(-1).thumb`), true, 'la génération garde sa vignette d\'entrée');
  page.assertNoErrors();
});

test('Dessiner : texte, image et tracé vidés quand la demande est acceptée', async () => {
  await fresh();
  await drawOne();
  await paint();
  assert.match(await page.eval(`$('prompt').placeholder`), /^Que mettre dans la zone peinte/);
  await page.typePrompt('une fenêtre ouverte');
  const opts = JSON.parse(await settings());
  await generate();
  // le format « Image » suit l'image à retoucher : il part avec elle, comme quand on la retire à la main ; le reste des
  // Réglages ne bouge pas
  assert.equal(opts.opt.ratio, 'image');
  assert.deepEqual(JSON.parse(await settings()), { ...opts, opt: { ...opts.opt, ratio: '1:1' } });
  assert.equal(await page.eval(`$('prompt').value`), '');
  assert.equal(await page.eval(`!drawOn && !inputImages.length && !${SHOWN}`), true, 'image partie, dessin éteint');
  assert.equal(await page.eval(`paintedPixels()`), 0, 'masque effacé');
  page.assertNoErrors();
});

test('Campagne : proposée dès 2 images, ignorée sinon ; photos vidées, interrupteur gardé', async () => {
  const shown = () => page.eval(`!!$('campSwitch').getClientRects().length`);
  await fresh();
  assert.equal(await shown(), false, 'sans image');
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 1`, { what: 'une image' });
  assert.equal(await shown(), false, 'une seule image : édition simple');
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  assert.equal(await shown(), true, 'à partir de 2 images');
  await page.click('#campChk');
  await page.waitFor(`campaignOn`, { what: 'campagne activée' });
  assert.match(await page.eval(`$('pills').textContent`), /Campagne · 2 photos/);
  // une image retirée : l'interrupteur disparaît, son réglage reste mais la demande part en édition simple
  await page.click('#inThumbs .thumb:last-child button');
  await page.waitFor(`inputImages.length === 1`, { what: 'image retirée' });
  assert.equal(await shown(), false);
  assert.doesNotMatch(await page.eval(`$('pills').textContent`), /Campagne/);
  await page.typePrompt('voiture bleue');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'edit', lot: null });
  assert.equal(await page.eval(`campaignOn`), true, 'réglage gardé');
  await page.setFiles('#inFiles', photos(2));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux photos' });
  assert.equal(await page.eval(`$('campChk').checked && !!$('campSwitch').getClientRects().length`), true,
    'de nouveau proposée, active');
  await page.typePrompt('voiture bleue');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'edit', lot: { size: 2, campaign: true } });
  assert.equal(await page.eval(`inputImages.length + $('inThumbs').children.length`), 0);
  assert.equal(await page.eval(`campaignOn && $('campChk').checked`), true);
  page.assertNoErrors();
});

test('Variantes : proposées avec des images et en Dessiner hors campagne, la demande part en lot', async () => {
  const countShown = () => page.eval(`getComputedStyle($('countRow')).display !== 'none'`);
  const pick = k => page.eval(`$('countOpts').querySelector('[data-k="${k}"]').click()`);
  // générations des tests précédents finies d'abord : sinon la page neuve les reprend (lancées par ce navigateur),
  // ce qui ajoute des générations et des messages de fin à ceux comptés plus bas (banc chargé : --ui complet)
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queued)`,
    { what: 'file du banc vide', timeout: 60000 });
  await fresh();
  await watchToasts();
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 1`, { what: 'une image' });
  assert.equal(await countShown(), true, 'rangée des images avec une image d\'entrée');
  await pick(2);
  // HOLD : chaque lot ne finit qu'une fois la page revenue sur Créer (fini sur En cours, il n'aurait pas de message)
  await page.typePrompt('HOLD=chapeau deux essais d\'un chapeau');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'edit', lot: { size: 2, campaign: false } });
  // campagne : la rangée disparaît et le nombre choisi est ignoré (une image par photo)
  await page.setFiles('#inFiles', photos(3));
  await page.waitFor(`inputImages.length === 3`, { what: 'trois photos' });
  await page.click('#campChk');
  await page.waitFor(`campaignOn`, { what: 'campagne activée' });
  assert.equal(await countShown(), false, 'pas de variantes en campagne');
  await page.typePrompt('HOLD=voiture voiture bleue');
  await generate();
  bench.release('chapeau');                        // les deux lots, une fois revenu sur Créer
  bench.release('voiture');
  assert.deepEqual(await lastJob(), { mode: 'edit', lot: { size: 3, campaign: true } });
  // fin de chaque lot, vue depuis Créer : un message par lot, une fois toutes ses images finies ; derrière les
  // générations des tests précédents, toutes les pages d'interface et le banc tournant en même temps
  await page.waitFor(`pageJobs.length === 5 && pageJobs.every(p => p.result)`,
    { what: 'deux lots terminés', timeout: 60000 });
  const ends = await page.eval(`seenToasts.filter(t => t.startsWith('Lot prêt'))`);
  assert.deepEqual(ends, ['Lot prêt · 2 images', 'Lot prêt · 3 images']);
  await fresh();
  await drawOne();
  assert.equal(await countShown(), true, 'rangée des images en dessin');
  await pick(3);
  await paint();
  await page.typePrompt('une fenêtre ouverte');
  await generate();
  assert.deepEqual(await lastJob(), { mode: 'mask', lot: { size: 3, campaign: false } });
  assert.equal(await page.eval(`pageJobs.slice(-3).every(p => p.j.mode === 'mask' && p.lot.size === 3)`), true);
  page.assertNoErrors();
});

test('Créer : rien n\'est vidé quand le Mac refuse la demande ou est injoignable', async () => {
  await fresh();
  await page.setFiles('#inFiles', photos(2));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images' });
  await page.typePrompt('mettre un chapeau');
  for (const refuse of ['error', 'unreachable']) {
    await generate({ refuse });
    assert.equal(await page.eval(`$('prompt').value`), 'mettre un chapeau', refuse);
    assert.equal(await page.eval(`inputImages.length`), 2, refuse);
    assert.equal(await draft(), 'mettre un chapeau', refuse);
  }
  // Chrome note dans sa console la réponse 503 et la connexion refusée : seules erreurs attendues ici
  assert.deepEqual(page.errors.filter(e => !/503|ERR_CONNECTION_REFUSED/.test(e)), []);
  page.errors.length = 0;
});

// ------------------------------------------------------------ saisie propre à chaque espace
const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
// entrée dans l'espace privé (créé la première fois) ; la page le voit à son interrogation suivante de /api/status
async function enterPrivate() {
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
// fermeture de l'espace par le Mac (15 minutes sans requête privée) : la session est fermée sans passer par « Sortir »
async function closedByMac() {
  assert.equal(await post('/api/private/lock'), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
}
const goTab = pane => page.click(`#tabbar [data-pane="${pane}"]`);
const value = () => page.eval(`$('prompt').value`);
// onglets marqués (supprimés) : une pastille dessinée sur le bouton (pseudo-élément ::after) ou une infobulle
const marked = () => page.eval(`[...document.querySelectorAll('#tabbar button')]
  .filter(b => getComputedStyle(b, '::after').content !== 'none' || b.title).length`);

test('espaces : la saisie privée disparaît à « Sortir », la saisie publique revient intacte', async () => {
  await fresh();
  await drawOne();
  await paint();
  await page.eval(`$('mask_mode').querySelector('[value=annotation]').click()`);
  await page.typePrompt('chapeau public');

  await enterPrivate();                            // première entrée : saisie privée vide
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length, drawOn, ${SHOWN}]`), ['', 0, false, false]);
  assert.equal(await page.eval(`paintedPixels()`), 0, 'aucun tracé public sur le canevas');
  await page.setFiles('#inFiles', photos(2));
  await page.waitFor(`inputImages.length === 2`, { what: 'deux images privées' });
  await page.typePrompt('chapeau secret');
  await generate();                                // génération privée : la saisie privée est vidée
  assert.equal(await page.eval(`pageJobs.at(-1).private`), true);
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length]`), ['', 0]);
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 1`, { what: 'une image privée' });
  await page.typePrompt('texte secret');
  assert.equal(await draft(), 'chapeau public',
    'la saisie privée n\'est jamais écrite dans le navigateur, le brouillon public reste');

  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.equal(await value(), 'chapeau public');
  assert.equal(await page.eval(`inputImages.length === 1 && drawOn && ${SHOWN} && paintedPixels() > 0`), true,
    'image, dessin et tracé publics');
  assert.equal(await page.eval(`maskMode()`), 'annotation', 'mode du dessin public');
  assert.equal(await marked(), 0, 'aucun onglet marqué');

  await enterPrivate();                            // « Sortir » a effacé la saisie privée
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length, drawOn]`), ['', 0, false]);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('espaces : un dessin privé ne laisse ni image, ni tracé, ni taille d\'image après « Sortir »', async () => {
  await fresh();
  await enterPrivate();
  await drawOne();
  await paint();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.eval(`[inputImages.length, drawOn, $('paintImg').hasAttribute('src'), paintedPixels(),
    $('paintCanvas').width, $('paintCanvas').height]`), [0, false, false, 0, 1, 1]);
  page.assertNoErrors();
});

// image réellement peinte sous le canevas du dessin (currentSrc : l'image d'avant tant que la nouvelle charge), notée
// à chaque changement de l'image et à chaque image de l'écran, avec l'espace où l'on est. Garde de régression : Chrome
// sans écran montre aussitôt une adresse data: déjà décodée (toEntry le fait pour chaque image d'entrée), même après
// une alerte mémoire, donc l'image d'avant n'y reste pas même sans showImage ; c'est tests/check.py (IMAGE_IDS) qui
// refuse l'adresse donnée à la main
const watchPaint = () => page.eval(`(() => { window.paintSeen = []; const i = $('paintImg');
  const note = () => paintSeen.push({ priv: inPrivate(), cur: i.currentSrc });
  window.paintWatch?.disconnect(); window.paintWatch = new MutationObserver(note);
  paintWatch.observe(i, { attributes: true });
  (function frame(){ if (window.paintSeen) { note(); requestAnimationFrame(frame); } })(); })()`);
const paintLoaded = `$('paintImg').complete && $('paintImg').naturalWidth > 0
  && $('paintImg').currentSrc === inputImages[0]?.dataUrl`;

test('espaces : dessin actif des deux côtés, l\'image du dessin n\'est jamais celle de l\'autre espace', async () => {
  await fresh();
  await page.setFiles('#inFiles', [photo('publique.png', 60)]);
  await page.waitFor(`inputImages.length === 1`, { what: 'une image publique' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn && ${paintLoaded}`, { what: 'dessin public affiché' });
  const pub = await page.eval(`inputImages[0].dataUrl`);
  // dans l'espace privé, Dessiner ouvre le choix d'une image ; le Mac ferme l'espace pendant que le sélecteur est
  // ouvert, puis l'image choisie arrive : elle va dans la saisie privée mise de côté, jamais encore affichée
  await enterPrivate();
  await page.eval(`$('drawFile').addEventListener('click', e => e.preventDefault(), { once: true })`);
  await page.click('#drawBtn');
  await closedByMac();
  await page.setFiles('#drawFile', [photo('privee.png', 200)]);
  await page.waitFor(`asideInput && asideInput.drawing.on && asideInput.images.length === 1`,
    { what: 'image privée mise de côté, dessin actif' });
  await page.waitFor(paintLoaded, { what: 'dessin public de nouveau affiché' });

  await watchPaint();
  await enterPrivate();                            // public → privé : l'image privée remplace la publique
  await page.waitFor(`drawOn && ${paintLoaded}`, { what: 'dessin privé affiché' });
  const priv = await page.eval(`inputImages[0].dataUrl`);
  assert.notEqual(priv, pub);
  await page.click('#privExit');                   // privé → public
  await page.waitFor(`!inPrivate() && drawOn && ${paintLoaded}`, { what: 'dessin public de retour' });
  const seen = await page.eval(`(() => { const s = paintSeen; window.paintSeen = null; paintWatch.disconnect();
    return s; })()`);
  assert.ok(seen.some(x => x.priv) && seen.some(x => !x.priv), 'image du dessin notée dans les deux espaces');
  const other = seen.filter(x => x.cur === (x.priv ? pub : priv)).map(x => (x.priv ? 'privé' : 'public'));
  assert.deepEqual(other, [], 'image de l\'autre espace à l\'écran');
  // après « Sortir », l'image privée n'est plus nulle part dans la page, ni dans les images prêtes
  const p = JSON.stringify(priv);
  assert.deepEqual(await page.eval(`[document.documentElement.outerHTML.includes(${p}),
    [...ready.keys()].includes(${p}), $('paintImg').currentSrc === ${p}]`), [false, false, false]);
  page.assertNoErrors();
});

test('espaces : un trait commencé dans l\'espace privé ne continue pas sur le tracé public', async () => {
  await fresh();
  await drawOne();                                 // dessin public, tracé vide
  await enterPrivate();
  await drawOne();
  const box = await page.eval(`(() => { const c = $('paintCanvas'); c.scrollIntoView({ block: 'center' });
    const r = c.getBoundingClientRect();
    return { x: r.left + r.width / 4, y: r.top + r.height / 4, w: r.width }; })()`);
  const mouse = (type, dx, buttons = 1) => page.send('Input.dispatchMouseEvent',
    { type, x: box.x + dx, y: box.y, button: 'left', buttons, clickCount: 1 });
  await mouse('mousePressed', 0);
  await mouse('mouseMoved', 4);
  await page.waitFor(`paintedPixels() > 0`, { what: 'trait privé commencé' });
  await closedByMac();                             // le doigt encore posé
  await mouse('mouseMoved', box.w / 2);
  await mouse('mouseReleased', box.w / 2, 0);
  assert.equal(await page.eval(`drawOn && paintedPixels()`), 0, 'rien du trait privé sur le tracé public');
  page.assertNoErrors();
});

test('espaces : fermée par le Mac, la saisie privée attend le retour dans la page ; supprimée avec l\'espace', async () => {
  await fresh();
  await page.typePrompt('texte public');
  await enterPrivate();
  await page.typePrompt('un long texte privé');
  await page.setFiles('#inFiles', photos(1));
  await page.waitFor(`inputImages.length === 1`, { what: 'une image privée' });
  await closedByMac();
  assert.equal(await value(), 'texte public');
  assert.equal(await page.eval(`inputImages.length`), 0);
  assert.equal(await marked(), 0, 'aucun onglet marqué');
  await enterPrivate();
  assert.equal(await value(), 'un long texte privé', 'retrouvé au retour');
  assert.equal(await page.eval(`inputImages.length`), 1, 'son image aussi');
  await closedByMac();

  assert.equal(await post('/api/private/reset', { confirm: 'SUPPRIMER' }), 200);   // espace supprimé (sur le Mac)
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!privState.exists`, { what: 'espace supprimé vu par la page' });
  await enterPrivate();                            // recréé : rien de l'ancien espace
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length]`), ['', 0]);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.equal(await value(), 'texte public');
  page.assertNoErrors();
});

// messages affichés depuis l'appel (chaque texte posé dans #toastBox, même remplacé aussitôt par un autre)
const watchToasts = () => page.eval(`(() => { window.seenToasts = []; window.toastWatch?.disconnect();
  window.toastWatch = new MutationObserver(() => seenToasts.push($('toastBox').textContent));
  toastWatch.observe($('toastBox'), { childList: true, characterData: true, subtree: true }); })()`);
const CLOSED = 'Espace privé fermé : retour dans l\'espace public';

test('espaces : fermé sans « Sortir », le champ perd le curseur et un message dit le retour dans l\'espace public', async () => {
  await fresh();
  await enterPrivate();
  await page.eval(`$('prompt').focus()`);
  assert.equal(await page.eval(`document.activeElement === $('prompt')`), true);
  await watchToasts();
  await closedByMac();                             // 15 minutes sans requête privée
  assert.equal(await page.eval(`document.activeElement === $('prompt')`), false, 'le champ a perdu le curseur');
  assert.deepEqual(await page.eval(`seenToasts`), [CLOSED]);
  assert.equal(await page.eval(`$('toastBox').classList.contains('on')`), true);

  await enterPrivate();                            // espace supprimé depuis le Mac pendant qu'on tape
  await page.eval(`$('prompt').focus()`);
  await watchToasts();
  assert.equal(await post('/api/private/reset', { confirm: 'SUPPRIMER' }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
  assert.equal(await page.eval(`document.activeElement === $('prompt')`), false, 'le champ a perdu le curseur');
  assert.deepEqual(await page.eval(`seenToasts`), [CLOSED]);

  await enterPrivate();                            // « Sortir » : la sortie est demandée, pas de message de fermeture
  await page.eval(`$('prompt').focus()`);
  await watchToasts();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate() && seenToasts.length > 0`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.eval(`seenToasts`), ['Sorti de l\'espace privé']);
  page.assertNoErrors();
});

test('espaces : une demande privée acceptée après la fermeture par le Mac ne vide pas la saisie publique', async () => {
  await fresh();
  await page.typePrompt('texte public');
  await enterPrivate();
  await page.typePrompt('demande privée');
  refusal = 'hold'; held = Promise.withResolvers();
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Response' }] });
  await page.click('#go');
  const requestId = await held.promise;            // le Mac a accepté la demande privée, la page n'a pas encore sa réponse
  await closedByMac();                             // pendant l'attente : la saisie publique revient à l'écran
  await page.send('Fetch.continueRequest', { requestId });
  await page.send('Fetch.disable');
  refusal = null;
  // demande acceptée : sa saisie privée, mise de côté par la fermeture, est vidée de ce qui est parti (le journal n'en
  // dit rien : une ligne privée finie hors de l'espace n'y entre pas)
  await page.waitFor(`asideInput && asideInput.text === ''`, { what: 'demande acceptée' });
  assert.equal(await page.eval(`pageJobs.some(p => p.private)`), false, 'hors de l\'espace, la page ne suit pas la génération privée');
  assert.equal(await value(), 'texte public', 'la saisie publique reste');
  assert.equal(await draft(), 'texte public', 'son brouillon aussi');
  await enterPrivate();
  assert.equal(await value(), '', 'c\'est la saisie privée de la demande qui est vidée');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('Créer : un texte tapé pendant l\'envoi reste quand la demande est acceptée', async () => {
  await fresh();
  await page.typePrompt('premier texte');
  refusal = 'hold'; held = Promise.withResolvers();
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Response' }] });
  const jobsBefore = await page.eval(`pageJobs.length`);
  await page.click('#go');
  const requestId = await held.promise;            // le Mac a accepté, la page n'a pas encore sa réponse
  await page.typePrompt('texte suivant');
  await page.send('Fetch.continueRequest', { requestId });
  await page.send('Fetch.disable');
  refusal = null;
  await page.waitFor(`pageJobs.length > ${jobsBefore}`, { what: 'demande acceptée' });
  assert.equal(await value(), 'texte suivant');
  assert.equal(await draft(), 'texte suivant');
  page.assertNoErrors();
});
