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
  // l'image prend la hauteur de la colonne : ✓ et ✕ tiennent au bas de la vue, sans place perdue dessous (la marge
  // du bas de la page, 16 px, et 24 px d'air au plus)
  assert.ok(acts.bottom <= view.h, `✓ et ✕ sous le bas de la vue : ${acts.bottom} > ${view.h}`);
  assert.ok(view.h - acts.bottom <= 40, `place perdue sous ✓ et ✕ : ${view.h - acts.bottom} px`);
  assert.ok(img.height >= view.h * 0.6, `image de la carte petite : ${img.height} px pour ${view.h} px`);
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

test('PC : une image glissée sur le champ après « Révéler » le déplie aussi pour la règle du téléphone', async () => {
  await labo();
  await page.made('grand glissée');                 // « Révéler » : la règle du téléphone replie le champ
  await page.eval(`(async () => { const dt = new DataTransfer(), c = document.createElement('canvas');
    c.width = c.height = 64; const b = await new Promise(r => c.toBlob(r));
    dt.items.add(new File([b], 'g.png', { type: 'image/png' }));
    $('prompt').dispatchEvent(new DragEvent('dragover', { dataTransfer: dt, bubbles: true, cancelable: true })); })()`);
  await page.setView(PHONE);                         // au téléphone, une image glissée dessus l'aurait déplié
  await page.waitFor(`innerWidth === ${PHONE.width}`, { what: 'vue du téléphone' });
  // (le changement de disposition suit la nouvelle largeur à l'image d'affichage suivante : deux images attendues)
  await page.eval(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  assert.equal(await page.visible('#prompt'), true, 'téléphone : champ replié malgré l\'image glissée');
  await page.setView(PC);
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

// barre d'onglets, visionneuse et Tirages en grand écran

// Tirages affichés dans la vue view, avec au moins une image gardée
async function tirages(view = PC) {
  await labo(view);
  await page.made('grand tirage');
  await page.keepPile();
  await page.tab('tirages');
  await page.waitFor(`histItems.length > 0`, { what: 'Tirages' });
}

test('PC : onglets dans la barre du haut, centrés, avec l\'anneau et le nombre de la pile ; plus de marge du bas',
  async () => {
    await labo();
    await page.generate('HOLD=grand anneau');
    try {
      await page.waitFor(`!$('runCard').hidden`, { what: 'carte en cours' });
      const bar = await box('#tabbar'), top = await box('.topbar');
      assert.ok(bar.top >= top.top && bar.bottom <= top.bottom, `onglets hors de la barre du haut : ${
        JSON.stringify([bar, top])}`);
      const center = await page.eval(`innerWidth / 2`);
      assert.ok(Math.abs((bar.left + bar.right) / 2 - center) <= 2, `onglets pas centrés : ${JSON.stringify(bar)}`);
      assert.equal(await page.visible('#runRing'), true, 'anneau de progression absent');
      assert.equal(await page.visible('#lens'), true, 'indicateur de l\'onglet absent');
    } finally { bench.release('grand'); }
    await page.waitFor(`pileItems.length > 0 && !$('runCount').hidden`, { what: 'image dans la pile' });
    assert.equal(await page.visible('#runCount'), true, 'nombre de la pile absent');
    await page.tab('tirages');                       // l'onglet marche du haut
    await page.tab('labo');
    // plus de marge du bas pour une barre flottante : le Labo descend jusqu'au bas de la vue, à 24 px près
    const pane = await box('#pane-labo'), view = await page.eval(`innerHeight`);
    assert.ok(view - pane.bottom <= 24, `marge du bas de ${view - pane.bottom} px`);
    await bench.idle({ page });
    page.assertNoErrors();
  });

test('tablette en hauteur : les onglets restent en bas ; au doigt, le glissement d\'onglet marche en largeur',
  async () => {
    await labo(TABLET);
    const bar = await box('#tabbar'), view = await page.eval(`innerHeight`);
    assert.ok(bar.bottom >= view - 40, `onglets pas en bas : ${JSON.stringify(bar)}`);
    await labo(TABLET_WIDE);
    await page.swipe('#pileEmpty', -160);
    await page.waitFor(`mode === 'tirages'`, { what: 'Tirages après un glissement vers la gauche' });
    await page.swipe('#pane-tirages', 160);
    await page.waitFor(`mode === 'labo'`, { what: 'Labo après un glissement vers la droite' });
    page.assertNoErrors();
  });

test('PC : visionneuse en largeur, image à gauche sur toute la hauteur, panneau à droite ; immersif le masque',
  async () => {
    await tirages();
    await page.viewTirage();
    const stage = await box('#vStage'), panel = await box('#viewer .v-panel');
    const view = await page.eval(`({ w: innerWidth, h: innerHeight })`);
    assert.ok(panel.left >= stage.right, `panneau pas à droite de l'image : ${JSON.stringify([stage, panel])}`);
    assert.ok(panel.right <= view.w && panel.bottom <= view.h, `panneau hors de la vue : ${JSON.stringify(panel)}`);
    assert.ok(stage.height >= view.h * 0.8, `image pas sur la hauteur : ${stage.height} px pour ${view.h}`);
    assert.ok(panel.width >= 320 && panel.width <= 440, `panneau de ${panel.width} px`);
    await page.swipe('#vImg', 0, 0, { mouse: true });   // un appui sur l'image : mode immersif
    await page.waitFor(`getComputedStyle(document.querySelector('#viewer .v-panel')).opacity === '0'`,
      { what: 'panneau masqué en mode immersif' });
    await page.eval(`closeViewer()`);
    page.assertNoErrors();
  });

test('PC : un panneau plus long que la fenêtre défile dans sa colonne', async () => {
  await tirages();
  await page.setView({ ...PC, height: 150 });   // (le panneau d'un tirage fait environ 150 px)
  await page.viewTirage();
  const panel = await box('#viewer .v-panel'), view = await page.eval(`innerHeight`);
  assert.ok(panel.bottom <= view, `panneau coupé en bas : ${JSON.stringify(panel)}`);
  assert.ok(await page.eval(`(p => p.scrollHeight > p.clientHeight && getComputedStyle(p).overflowY === 'auto')
    (document.querySelector('#viewer .v-panel'))`), 'panneau long qui ne défile pas');
  await page.eval(`closeViewer()`);
  await page.setView(PC);
  page.assertNoErrors();
});

test('Tirages : vignettes d\'au moins 200 px à partir de 1024 px, celles d\'aujourd\'hui en dessous', async () => {
  const width = () => page.eval(`Math.round($('histGrid').firstElementChild.getBoundingClientRect().width)`);
  await tirages();
  assert.ok(await width() >= 200, `vignette de ${await width()} px au PC`);
  await page.setView(TABLET);
  await page.waitFor(`innerWidth === ${TABLET.width}`, { what: 'vue de la tablette' });
  assert.ok(await width() < 200, `vignette de ${await width()} px à la tablette en hauteur`);
  await page.setView(PC);
  page.assertNoErrors();
});

test('aucun débordement des Tirages et de la visionneuse aux quatre tailles', async () => {
  for (const view of [PHONE, TABLET, TABLET_WIDE, PC]) {
    await tirages(view);
    assert.deepEqual(await page.overflowing(), [], `${view.width}×${view.height}, Tirages`);
    await page.viewTirage();
    // (overflowing ne regarde pas la visionneuse) : ses parties tiennent dans la vue
    const out = await page.eval(`[...document.querySelectorAll('#viewer > :not(.v-bg), #viewer .act')]
      .filter(el => { const r = el.getBoundingClientRect(); return r.left < -.5 || r.right > innerWidth + .5; })
      .map(el => el.className)`);
    assert.deepEqual(out, [], `${view.width}×${view.height}, visionneuse`);
    await page.eval(`closeViewer()`);
  }
  page.assertNoErrors();
});
