// Champ de création du Labo, dans la vue du téléphone : déplié quand la pile et la carte en cours sont vides, replié
// sinon en une ligne « Décrire une image… » (avec le nombre d'images d'entrée) qu'un toucher déplie ; replié par sa
// poignée (glissement vers le bas), par un toucher sur la pile (image comprise ; pas la fin d'un balayage à la souris,
// et dès le premier toucher après un balayage au doigt) et après « Révéler », sans rien perdre de la saisie ; déplié
// d'office sans y toucher, il se replie quand le Labo a de nouveau quelque chose ; image glissée sur la ligne ; ✓ et ✕
// jamais sous la ligne ;
// dessin en pleine hauteur ; réglages en grille de quatre cases qui ouvrent la feuille des réglages (Images masquée
// en campagne) ; bouton « Révéler » et son estimation ; rien ne dépasse de la vue à 367 px.
//   venv/bin/python tests/check.py --quick --ui tests/ui/champ.test.mjs
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
  bench?.release('champ');
  await chrome?.close();
  await bench?.stop();
});

const DRAFT = 'qwen-prompt';
const FOLDED = `$('composer').classList.contains('folded')`;
const folded = () => page.eval(FOLDED);
// page neuve (brouillons effacés), Labo affiché, pile lue et vidée ; générations courtes
async function fresh() {
  await bench.idle();
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && pileRead`, { what: 'moteur prêt, pile lue' });
  await page.keepPile();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);
}

test('champ : déplié pile vide, replié après « Révéler », replié au chargement quand la pile a une image', async () => {
  await fresh();
  assert.equal(await page.eval(`pileSize()`), 0, 'pile du banc pas vide');
  assert.equal(await folded(), false, 'pile vide : champ replié');
  assert.equal(await page.visible('#composerLine'), false, 'ligne repliée affichée');
  assert.equal(await page.visible('#prompt'), true, 'texte masqué');
  await page.made('zqC1 une tasse');
  assert.equal(await folded(), true, 'pas replié après « Révéler »');
  assert.equal(await page.eval(`$('prompt').value`), '', 'saisie gardée après « Révéler »');
  assert.equal(await page.visible('#prompt'), false, 'replié : texte encore affiché');
  assert.match(await page.eval(`$('composerLine').textContent`), /Décrire une image…/);
  await page.goto(bench.url + '/');
  await page.waitFor(`pileRead && pileSize() === 1`, { what: 'pile relue' });
  assert.equal(await folded(), true, 'pile non vide au chargement : champ déplié');
  page.assertNoErrors();
});

test('champ : la ligne le déplie ; replié par la poignée et par un toucher sur la pile, saisie intacte', async () => {
  assert.equal(await folded(), true);
  await page.click('#composerLine');
  assert.equal(await folded(), false, 'toucher sur la ligne : champ replié');
  await page.typePrompt('zqC2 un phare');
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
  await page.swipe('#composerGrab', 0, 140);        // glissement vers le bas sur la poignée
  await page.waitFor(FOLDED, { what: 'replié par la poignée' });
  assert.match(await page.eval(`$('composerLine').textContent`), /1 image/, 'nombre d\'images absent de la ligne');
  assert.deepEqual(await page.eval(`[$('prompt').value, inputImages.length, localStorage.getItem('${DRAFT}')]`),
    ['zqC2 un phare', 1, 'zqC2 un phare'], 'saisie perdue en repliant');
  await page.click('#composerLine');
  assert.equal(await page.visible('#inThumbs .thumb'), true, 'image d\'entrée absente une fois déplié');
  await page.click('.pilezone');                    // toucher sur la pile (hors de ses cartes)
  assert.equal(await folded(), true, 'toucher sur la pile : champ déplié');
  assert.equal(await page.eval(`vIndex`), -1, 'visionneuse ouverte');
  assert.equal(await page.eval(`$('prompt').value`), 'zqC2 un phare');
  page.assertNoErrors();
});

test('champ : déplié d\'office quand la pile se vide', async () => {
  assert.equal(await folded(), true);
  await page.keepPile();
  await page.waitFor(`!${FOLDED}`, { what: 'déplié, pile vide' });
  assert.equal(await page.eval(`$('prompt').value`), 'zqC2 un phare', 'saisie perdue');
  page.assertNoErrors();
});

test('champ : déplié d\'office sans y toucher, replié quand la carte revient ; touché, il reste déplié', async () => {
  await fresh();
  await page.made('zqC3 un pont');
  await page.click('#pileNo');                     // la dernière carte part, bandeau Annuler : rien à trier
  await page.waitFor(`!${FOLDED}`, { what: 'déplié d\'office' });
  await page.click('#undoBtn');
  await page.waitFor(FOLDED, { what: 'replié quand la carte revient' });
  await page.click('#composerLine');               // touché : une image qui arrive ne le replie pas
  await page.launch('zqC3 d\'un autre appareil');
  await page.waitFor(`pileItems.some(it => it.prompt === 'zqC3 d\\'un autre appareil')`,
    { what: 'image de l\'autre appareil dans la pile' });
  assert.equal(await folded(), false, 'replié sous les doigts');
  page.assertNoErrors();
});

test('champ : un toucher sur l\'image de la pile le replie et ouvre la visionneuse ; un balayage à la souris non',
  async () => {
    assert.equal(await folded(), false);
    await page.click('#pile .pcard[data-k="0"] .pimg');
    assert.equal(await folded(), true, 'image touchée : champ déplié');
    assert.ok(await page.eval(`vIndex`) >= 0, 'visionneuse fermée');
    await page.eval(`closeViewer()`);
    await page.waitFor(`getComputedStyle($('viewer')).visibility === 'hidden'`, { what: 'visionneuse fermée' });
    await page.click('#composerLine');
    const size = await page.eval(`pileSize()`);
    await page.eval(`scrollTo({ top: 0, behavior: 'instant' })`);   // (le défilement vers le champ déplié arrêté)
    await page.swipe('#pile .pcard[data-k="0"] .pimg', 200, 0, { mouse: true });   // gardée d'un balayage à droite
    await page.waitFor(`pileSize() === ${size - 1}`, { what: 'carte balayée' });
    assert.equal(await folded(), false, 'fin du balayage prise pour un toucher sur la pile');
    page.assertNoErrors();
  });

// toucher du doigt au centre d'un élément (geste de Chrome : pointerdown, pointerup puis click)
async function tap(selector) {
  const c = await page.eval(`(r => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 }))
    (document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect())`);
  await page.send('Input.synthesizeTapGesture', { x: c.x, y: c.y, gestureSourceType: 'touch' });
}

test('champ : après un balayage au doigt, le premier toucher sur la pile le replie', async () => {
  await page.made('zqC3 encore');                  // (replié après « Révéler »)
  await page.click('#composerLine');
  await page.eval(`scrollTo({ top: 0, behavior: 'instant' })`);
  const size = await page.eval(`pileSize()`);
  await page.swipe('#pile .pcard[data-k="0"] .pimg', 200);   // au doigt : aucun clic ne suit le geste
  await page.waitFor(`pileSize() === ${size - 1} && !flying`, { what: 'carte balayée' });
  assert.equal(await folded(), false);
  await tap('#pileCount');
  await page.waitFor(FOLDED, { what: 'replié au premier toucher', timeout: 3000 });
  page.assertNoErrors();
});

// ✓ et ✕ touchables partout (haut, milieu, bas) : rien, ligne repliée comprise, ne les recouvre
const reachable = () => page.eval(`['pileYes', 'pileNo'].filter(id => { const r = $(id).getBoundingClientRect(),
  x = r.left + r.width / 2; return [r.top + 2, r.top + r.height / 2, r.bottom - 2]
    .some(y => !document.elementFromPoint(x, y)?.closest('#' + id)); })`);

test('pile : ✓ et ✕ jamais sous la ligne repliée, carte en cours derrière la pile et pastille de la file', async () => {
  await page.generate('HOLD=champ zqC4 en cours');
  await page.waitFor(`${FOLDED} && !$('runCard').hidden && $('runCard').classList.contains('behind')`,
    { what: 'carte en cours derrière la pile, champ replié' });
  await page.eval(`scrollTo({ top: 0, behavior: 'instant' })`);
  assert.deepEqual(await reachable(), [], 'carte derrière : bouton recouvert');
  await page.generate('zqC5 en file');
  await page.waitFor(`${FOLDED} && !$('queueChip').hidden`, { what: 'pastille de la file' });
  await page.eval(`scrollTo({ top: 0, behavior: 'instant' })`);
  assert.deepEqual(await reachable(), [], 'pastille : bouton recouvert');
  bench.release('champ');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('champ : une image glissée sur la ligne repliée le déplie et rejoint les images d\'entrée', async () => {
  assert.equal(await folded(), true);
  const drag = type => page.eval(`(async () => { const dt = new DataTransfer(), c = document.createElement('canvas');
    c.width = c.height = 64; const b = await new Promise(r => c.toBlob(r, 'image/png'));
    dt.items.add(new File([b], 'glissee.png', { type: 'image/png' }));
    const el = ${JSON.stringify(type)} === 'dragover' ? $('composerLine') : $('prompt');
    const ev = new DragEvent(${JSON.stringify(type)}, { dataTransfer: dt, bubbles: true, cancelable: true });
    // annulé par le champ lui-même : vu sur document, avant l'écouteur de la fenêtre qui annule tout fichier
    let taken = false; document.addEventListener(ev.type, e => { taken = e.defaultPrevented; }, { once: true });
    el.dispatchEvent(ev); return taken; })()`);
  const before = await page.eval(`inputImages.length`);
  assert.equal(await drag('dragover'), true, 'survol : le navigateur ouvrirait le fichier');
  assert.equal(await folded(), false, 'survol : champ replié');
  assert.equal(await drag('drop'), true, 'dépôt : le navigateur ouvrirait le fichier');
  await page.waitFor(`inputImages.length === ${before + 1}`, { what: 'image déposée' });
  page.assertNoErrors();
});

test('Dessiner : le champ prend toute la hauteur du Labo, la pile revient ensuite', async () => {
  await fresh();
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn`, { what: 'dessin actif' });
  assert.equal(await page.visible('.pilezone'), false, 'pile affichée pendant le dessin');
  const room = await page.eval(`(() => { const top = document.querySelector('.topbar').getBoundingClientRect().bottom,
    bar = $('tabbar').getBoundingClientRect().top; return [Math.round($('composer').getBoundingClientRect().height),
    Math.round(bar - top)]; })()`);
  assert.ok(room[0] >= room[1] - 24, `champ moins haut que le Labo : ${room}`);
  await page.click('#drawBtn');
  await page.waitFor(`!drawOn`, { what: 'dessin éteint' });
  assert.equal(await page.visible('.pilezone'), true, 'pile absente après le dessin');
  page.assertNoErrors();
});

const CELLS = `[...$('setGrid').querySelectorAll('[data-set]')]`;
const cells = () => page.eval(`${CELLS}.filter(c => c.getClientRects().length).map(c => c.dataset.set)`);

test('réglages : grille de quatre cases qui ouvrent la feuille ; Images masquée en campagne', async () => {
  await fresh();
  assert.deepEqual(await cells(), ['format', 'taille', 'etapes', 'images']);
  for (const k of await cells()) {
    await page.click(`#setGrid [data-set="${k}"]`);
    assert.equal(await page.eval(`openedSheet === $('setSheet')`), true, `case ${k} : feuille fermée`);
    await page.eval(`closeSheet()`);
  }
  await page.eval(`$('stepOpts').querySelector('[data-k="max"]').click();
    $('countOpts').querySelector('[data-k="3"]').click()`);
  assert.match(await page.eval(`$('setGrid').textContent`), /Étapes40Images3/, 'grille pas à jour');
  await page.pasteImage(); await page.pasteImage();
  await page.waitFor(`inputImages.length === 2 && campaignShown()`, { what: 'campagne proposée' });
  await page.eval(`$('campChk').click()`);
  await page.waitFor(`inCampaign()`, { what: 'campagne active' });
  assert.deepEqual(await cells(), ['format', 'taille', 'etapes'], 'Images affichée en campagne');
  assert.match(await page.eval(`document.querySelector('#setGrid [data-set="format"]').textContent`), /2 photos/);
  page.assertNoErrors();
});

test('« Révéler » et son estimation ; rien ne dépasse à 367 px, champ déplié ou replié', async () => {
  await fresh();
  assert.equal(await page.eval(`$('goLabel').textContent`), 'Révéler');
  assert.match(await page.eval(`$('goEta').textContent`), /^≈ \d+ (s|min)$/);
  // réglages les plus longs à écrire : 1440p, 40 étapes, 4 images, deux images d'entrée
  await page.eval(`opt.res = 'max'; opt.steps = 'max'; opt.count = 4; saveOpt(); refreshChoices()`);
  await page.pasteImage(); await page.pasteImage();
  await page.waitFor(`inputImages.length === 2`, { what: 'images collées' });
  const clipped = `${CELLS}.filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.dataset.set)
    .concat($('go').scrollWidth > $('go').clientWidth + 1 ? ['go'] : [])`;
  assert.deepEqual(await page.overflowing(), [], 'déplié : dépasse de la vue');
  assert.deepEqual(await page.eval(clipped), [], 'texte rogné');
  await page.click('#composerGrab');                // un toucher sur la poignée replie aussi
  assert.equal(await folded(), true, 'toucher sur la poignée : champ déplié');
  assert.deepEqual(await page.overflowing(), [], 'replié : dépasse de la vue');
  page.assertNoErrors();
});
