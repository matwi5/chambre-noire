// Grand écran (PC, tablette) : à partir de 1024 px, le Labo en deux colonnes, la pile et la carte en cours à gauche
// (l'image de la carte du dessus à la hauteur de la colonne), le champ de création toujours déplié à droite (après
// « Révéler », pile qui se remplit, toucher de la pile), Dessiner à droite avec la pile visible, dépôt d'images sur
// toute la colonne du champ avec surbrillance ; entre 700 et 1023 px une colonne d'environ 760 px ; rien ne dépasse
// aux quatre tailles ; une fenêtre redimensionnée garde la saisie. Au téléphone, les autres tests (phonePage) gardent
// la disposition d'aujourd'hui.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/grand-ecran.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, PHONE, PC, TABLET, TABLET_WIDE } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.newPage(PC);
});

after(async () => {
  bench?.release('grand');
  await chrome?.close();
  await bench?.stop();
});

// Labo neuf (page.freshLabo) dans la vue view
async function labo(view = PC) {
  await page.setView(view);
  await page.freshLabo(bench);
}

// boîte arrondie d'un élément : { left, right, top, bottom, width, height }
const box = selector => page.eval(`(r => ({ left: Math.round(r.left), right: Math.round(r.right),
  top: Math.round(r.top), bottom: Math.round(r.bottom), width: Math.round(r.width), height: Math.round(r.height) }))
  (document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect())`);
// champ de création déplié : son texte affiché
const unfolded = () => page.visible('#prompt');

test('PC : pile à gauche, champ déplié à droite ; image de la carte à la hauteur de la colonne', async () => {
  await labo();
  assert.equal(await unfolded(), true, 'pile vide : champ replié');
  await page.made('grand pile 1');
  await page.made('grand pile 2');
  await page.waitFor(`(img => img && img.complete && img.naturalWidth > 0)
    ($('pile').querySelector('[data-k="0"] img'))`, { what: 'image de la carte du dessus' });
  assert.equal(await unfolded(), true, 'après « Révéler », pile remplie : champ replié');
  const pile = await box('.pilezone'), field = await box('#composer');
  assert.ok(field.left >= pile.right, `champ pas à droite de la pile : pile ${JSON.stringify(pile)}, champ `
    + JSON.stringify(field));
  assert.ok(pile.width > field.width, `colonne de la pile moins large que le champ : ${pile.width}, ${field.width}`);
  const view = await page.eval(`({ w: innerWidth, h: innerHeight })`);
  assert.ok(field.right <= view.w && field.top < view.h / 2, `champ hors de la vue : ${JSON.stringify(field)}`);
  const img = await box('#pile [data-k="0"] .pimg'), acts = await box('#pileActs');
  assert.ok(img.height >= view.h * 0.5, `image de la carte petite : ${img.height} px pour ${view.h} px`);
  assert.ok(acts.bottom <= view.h, `✓ et ✕ sous le bas de la vue : ${acts.bottom} > ${view.h}`);
  assert.equal(await page.visible('#composerGrab'), false, 'poignée du champ affichée');
  assert.ok(await page.eval(`document.documentElement.scrollHeight <= innerHeight`), 'le Labo défile');
  await page.click('#pile [data-k="0"] .pbody');    // toucher de la pile : le champ reste déplié
  assert.equal(await unfolded(), true, 'toucher de la pile : champ replié');
  assert.deepEqual(await page.overflowing(), [], 'dépasse de la vue');
  page.assertNoErrors();
});

test('PC : le champ reste déplié pendant une génération en cours, affichée à gauche', async () => {
  await labo();
  await page.generate('HOLD=grand en cours');
  try {
    await page.waitFor(`!$('runCard').hidden`, { what: 'carte en cours' });
    assert.equal(await unfolded(), true, 'génération en cours : champ replié');
    const run = await box('#runCard'), field = await box('#composer');
    assert.ok(field.left >= run.right, `carte en cours pas à gauche du champ : ${JSON.stringify([run, field])}`);
  } finally { bench.release('grand'); }               // (un échec ne laisse pas le Mac occupé pour les suivants)
  await bench.idle({ page });
  page.assertNoErrors();
});

test('PC : Dessiner prend la colonne du champ, la pile reste visible à gauche', async () => {
  await labo();
  await page.made('grand dessin');
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
  await page.click('#drawBtn');
  await page.waitFor(`drawOn`, { what: 'dessin actif' });
  assert.equal(await page.visible('.pilezone'), true, 'pile masquée pendant le dessin');
  const pile = await box('.pilezone'), field = await box('#composer');
  assert.ok(field.left >= pile.right, `champ pas à droite de la pile : ${JSON.stringify([pile, field])}`);
  assert.equal(await page.visible('#paintWrap'), true, 'zone de dessin absente');
  assert.deepEqual(await page.overflowing(), [], 'dépasse de la vue');
  page.assertNoErrors();
});

test('PC : une image déposée n\'importe où sur la colonne du champ, avec surbrillance au survol', async () => {
  await labo();
  // un fichier glissé sur un point de la colonne du champ (événement de glisser-déposer à ce point) ; renvoie si le
  // navigateur ouvrirait le fichier à la place de la page (dépôt non pris)
  const drag = (type, x, y) => page.eval(`(async () => { const dt = new DataTransfer(),
    c = document.createElement('canvas'); c.width = c.height = 64; const b = await new Promise(r => c.toBlob(r));
    dt.items.add(new File([b], 'deposee.png', { type: 'image/png' }));
    const el = document.elementFromPoint(${x}, ${y});
    const ev = new DragEvent(${JSON.stringify(type)}, { dataTransfer: dt, bubbles: true, cancelable: true,
      clientX: ${x}, clientY: ${y}, relatedTarget: null });
    el.dispatchEvent(ev); return ev.defaultPrevented; })()`);
  const lit = () => page.eval(`getComputedStyle($('composer')).outlineStyle !== 'none'`);
  const field = await box('#composer');
  const x = Math.round((field.left + field.right) / 2), y = field.bottom - 8;   // bas de la colonne, hors de la tuile
  assert.equal(await lit(), false, 'surbrillance avant le survol');
  assert.equal(await drag('dragenter', x, y), true, 'entrée : non prise');
  assert.equal(await drag('dragover', x, y), true, 'survol : le navigateur ouvrirait le fichier');
  assert.equal(await lit(), true, 'survol : pas de surbrillance');
  assert.equal(await drag('drop', x, y), true, 'dépôt : le navigateur ouvrirait le fichier');
  await page.waitFor(`inputImages.length === 1`, { what: 'image déposée' });
  assert.equal(await lit(), false, 'surbrillance restée après le dépôt');
  await drag('dragenter', x, y);
  assert.equal(await lit(), true, 'second survol : pas de surbrillance');
  await page.eval(`$('composer').dispatchEvent(new DragEvent('dragleave', { bubbles: true, relatedTarget: null }))`);
  assert.equal(await lit(), false, 'surbrillance restée après la sortie');
  page.assertNoErrors();
});

test('tablette en hauteur : une seule colonne d\'environ 760 px, champ sous la pile', async () => {
  await labo(TABLET);
  await page.made('grand tablette');
  const main = await box('main'), pile = await box('.pilezone'), field = await box('#composer');
  assert.ok(main.width >= 740 && main.width <= 780, `colonne de ${main.width} px`);
  assert.ok(field.top >= pile.bottom, `champ pas sous la pile : ${JSON.stringify([pile, field])}`);
  page.assertNoErrors();
});

test('aucun débordement du Labo aux quatre tailles, pile vide ou remplie', async () => {
  for (const view of [PHONE, TABLET, TABLET_WIDE, PC]) {
    await labo(view);
    assert.deepEqual(await page.overflowing(), [], `${view.width}×${view.height}, pile vide`);
    await page.made(`grand débord ${view.width}×${view.height}`);
    assert.deepEqual(await page.overflowing(), [], `${view.width}×${view.height}, pile remplie`);
  }
  page.assertNoErrors();
});

test('fenêtre redimensionnée PC → téléphone → PC : saisie gardée, champ toujours déplié au PC', async () => {
  await labo();
  await page.made('grand redim');
  await page.typePrompt('grand texte gardé');
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
  await page.click('#go');                           // « Révéler » au PC : la règle du téléphone replierait le champ
  await page.waitFor(`pageJobs.length >= 2 && !inputImages.length`, { what: 'demande acceptée, saisie vidée' });
  await page.typePrompt('grand texte gardé');
  // (la page voit la nouvelle largeur, puis le changement de disposition : l'effet attendu, pas la largeur seule)
  await page.setView(PHONE);
  await page.waitFor(`innerWidth === ${PHONE.width} && !$('prompt').getClientRects().length`,
    { what: 'téléphone : champ replié, comme le veut la règle du téléphone après « Révéler »' });
  assert.equal(await page.eval(`$('prompt').value`), 'grand texte gardé', 'saisie perdue au téléphone');
  await page.setView(PC);
  await page.waitFor(`innerWidth === ${PC.width} && $('prompt').getClientRects().length > 0`,
    { what: 'PC : champ déplié' });
  assert.equal(await page.eval(`$('prompt').value`), 'grand texte gardé', 'saisie perdue au PC');
  await bench.idle({ page });
  page.assertNoErrors();
});
