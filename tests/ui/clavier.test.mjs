// Raccourcis clavier du PC (spec du 27/10/2026, section 3), dans la vue PC : sur la pile du Labo, → garde et ← jette
// l'image du dessus (bandeau Annuler, un Jeter suivant valide le précédent, comme au doigt), Z ou Ctrl/⌘ + Z annule
// tant que le bandeau est là. Règle à ne jamais enfreindre : « Aucune touche ne supprime un tirage ; au clavier, Jeter
// passe toujours par le bandeau Annuler, comme au doigt ; une touche maintenue ou répétée ne jette jamais plus d'une
// image avant que la suivante soit affichée. » Boutons de tri marqués data-sort : Entrée répétée n'en active aucun.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/clavier.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, PC, TOP, SORT_IDLE, VIEWER_SEEN, ARROWS } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.newPage(PC);
  await page.goto(bench.url + '/');
  await page.ready();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);   // générations courtes
  await page.watchSorts();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// focus rendu à la page (aucun bouton ni champ ne le tient)
const unfocus = () => page.eval(`document.activeElement?.blur()`);
// bandeau Annuler affiché pour le Jeter en attente
const banner = what => page.waitFor(`!$('undoBar').hidden && !!discarding`, { what });
// pile vidée : un Jeter en attente annulé, puis tout gardé
async function clearPile() {
  if (await page.eval(`!!discarding`)) await page.click('#undoBtn');
  await bench.idle({ page });
  await page.keepPile();
}

test('→ garde l\'image du dessus ; ← la jette avec le bandeau ; Z et Ctrl/⌘ + Z annulent', async () => {
  await page.made('zk1 dessous');
  await page.made('zk1 dessus');
  await unfocus();
  await page.topShown();
  await page.watchSorts();
  await page.sort('keep', { by: 'key', ready: false });
  await waitUntil(() => bench.kept('zk1 dessus'), { what: '→ : gardée' });
  await page.waitFor(`${TOP} === 'zk1 dessous'`, { what: 'la suivante dessus' });
  await page.topShown();
  await page.sort('discard', { by: 'key', ready: false });
  await banner('← : bandeau');
  assert.equal(await page.topPrompt(), undefined, 'carte partie');
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé avant la fin du bandeau');
  await page.press('z');
  await page.waitFor(`$('undoBar').hidden && ${TOP} === 'zk1 dessous'`, { what: 'Z : carte remise' });
  await page.topShown();
  for (const modifiers of [['ctrl'], ['meta']]) {
    await page.sort('discard', { by: 'key', ready: false });
    await banner('← : bandeau');
    await page.press('z', { modifiers });
    await page.waitFor(`$('undoBar').hidden && ${TOP} === 'zk1 dessous'`, { what: `${modifiers} + Z : carte remise` });
    await page.topShown();
  }
  await page.press('z');                            // sans bandeau : rien
  assert.equal(await page.topPrompt(), 'zk1 dessous');
  assert.deepEqual([await page.sortsSent('discard'), await page.sortsSent('delete'), await bench.inPile('zk1 dessous')],
    [0, 0, true]);
  await clearPile();
  page.assertNoErrors();
});

test('← maintenue (répétition du système) : une seule image jetée, même la suivante affichée', async () => {
  for (const p of ['zk2 a', 'zk2 b', 'zk2 c']) await page.made(p);
  await unfocus();
  await page.topShown();
  await page.watchSorts();
  await page.keyDown(ARROWS.discard);
  for (let k = 0; k < 8; k++) await page.keyDown(ARROWS.discard, { repeat: true });
  await banner('bandeau du premier Jeter');
  await page.waitFor(`${TOP} === 'zk2 b'`, { what: 'zk2 b dessus' });
  await page.topShown();
  for (let k = 0; k < 8; k++) await page.keyDown(ARROWS.discard, { repeat: true });   // touche toujours tenue
  await page.keyUp(ARROWS.discard);
  await page.topShown();
  assert.equal(await page.topPrompt(), 'zk2 b', 'la touche tenue a jeté la suivante');
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé avant la fin du bandeau');
  assert.equal(await page.eval(`pileView().length`), 2);
  await clearPile();
  page.assertNoErrors();
});

test('← ← rapides : la seconde attend la carte suivante affichée ; ← ← : le premier Jeter part, un seul bandeau',
  async () => {
    for (const p of ['zk3 a', 'zk3 b', 'zk3 c']) await page.made(p);
    await unfocus();
    await page.topShown();
    await page.watchSorts();
    await page.sort('discard', { by: 'key', ready: false });   // ← ← : la seconde pendant l'envol de la première
    await page.sort('discard', { by: 'key', ready: false });
    await banner('bandeau');
    await page.topShown();
    assert.deepEqual([await page.topPrompt(), await page.sortsSent('discard')], ['zk3 b', 0], 'second ← ignoré');
    await page.sort('discard', { by: 'key', ready: false });   // zk3 b : le Jeter de zk3 c part, comme au doigt
    await waitUntil(async () => await page.sortsSent('discard') === 1, { what: 'premier Jeter envoyé' });
    await waitUntil(async () => !(await bench.inPile('zk3 c')), { what: 'zk3 c effacée' });
    assert.equal(await page.eval(`document.querySelectorAll('.undo:not([hidden])').length`), 1, 'un seul bandeau');
    await page.press('z');
    await page.waitFor(`${TOP} === 'zk3 b'`, { what: 'zk3 b remise' });
    assert.equal(await bench.inPile('zk3 b'), true);
    await clearPile();
    page.assertNoErrors();
  });

test('carte d\'échec en tête : → et ← ne font rien', async () => {
  await page.made('zk4 reussie');
  await page.generate('FAIL zk4 échec');
  await page.waitFor(`topEntry()?.fail?.prompt === 'FAIL zk4 échec'`, { what: 'carte de l\'échec en tête' });
  await unfocus();
  await page.watchSorts();
  await page.sort('discard', { by: 'key', ready: false });
  await page.sort('keep', { by: 'key', ready: false });
  assert.equal(await page.eval(`!!$('pile').querySelector('[data-k="0"] .pfail') && !flying && $('undoBar').hidden`),
    true, 'la carte d\'échec reste');
  await page.waitFor(`${SORT_IDLE}`, { what: 'carte d\'échec vue 0,3 s' });   // (verrou court d'une carte arrivée)
  await page.sort('discard', { ready: false });                      // ✕ la retire, comme avant
  await page.waitFor(`${TOP} === 'zk4 reussie'`, { what: 'échec retiré' });
  assert.equal(await page.sortsSent('discard'), 0);
  await clearPile();
  page.assertNoErrors();
});

test('Entrée maintenue sur ✕ ou sur Jeter de la visionneuse : une seule image jetée', async () => {
  for (const p of ['zk5 a', 'zk5 b', 'zk5 c']) await page.made(p);
  await page.topShown();
  await page.watchSorts();
  await page.eval(`$('pileNo').focus()`);
  await page.keyDown('Enter');                      // un appui voulu : jetée
  await banner('bandeau');
  await page.topShown();
  for (let k = 0; k < 6; k++) await page.keyDown('Enter', { repeat: true });
  await page.keyUp('Enter');
  await page.topShown();
  assert.equal(await page.topPrompt(), 'zk5 b', 'Entrée répétée a jeté la suivante');
  await page.press('z');
  await page.waitFor(`${TOP} === 'zk5 c'`, { what: 'zk5 c remise' });
  await page.viewPile('zk5 c');
  await page.eval(`$('vSort').querySelector('.btn').focus()`);   // Jeter de la visionneuse
  await page.keyDown('Enter');
  await page.waitFor(`!!discarding && vList[vIndex]?.prompt === 'zk5 b' && ${VIEWER_SEEN}`,
    { what: 'suivante affichée' });
  for (let k = 0; k < 6; k++) await page.keyDown('Enter', { repeat: true });
  await page.keyUp('Enter');
  await page.waitFor(`${VIEWER_SEEN}`, { what: 'rien de plus en route' });
  assert.deepEqual(await page.eval(`[vList.length, vList[vIndex].prompt]`), [2, 'zk5 b'], 'seconde image jetée');
  assert.equal(await page.sortsSent('discard'), 0);
  await page.closeViewer();
  await page.press('z');
  await clearPile();
  page.assertNoErrors();
});

test('aucun raccourci pendant la saisie dans le prompt, avec une feuille ouverte, ni avec ⌘ ou Alt', async () => {
  await page.made('zk6 a');
  await page.made('zk6 b');
  await page.topShown();
  await page.watchSorts();
  await page.eval(`$('prompt').focus()`);
  for (const key of [ARROWS.discard, ARROWS.keep, 'z']) await page.press(key);
  await unfocus();
  await page.eval(`openQueue()`);
  await page.waitFor(`openedSheet === $('fileSheet')`, { what: 'feuille de la file' });
  for (const key of [ARROWS.discard, ARROWS.keep]) await page.press(key);
  await page.closeSheet();
  for (const modifiers of [['meta'], ['alt'], ['ctrl'], ['shift']]) {
    await page.sort('discard', { by: 'key', ready: false, modifiers });
    await page.sort('keep', { by: 'key', ready: false, modifiers });
  }
  assert.equal(await page.eval(`!flying && $('undoBar').hidden && pileView().length`), 2, 'une image triée');
  assert.equal(await page.eval(`sorts.length`), 0);
  await clearPile();
  page.assertNoErrors();
});

test('visionneuse de la pile : ← → parcourent, rien n\'est trié ; Échap la ferme', async () => {
  for (const p of ['zk7 a', 'zk7 b', 'zk7 c']) await page.made(p);
  await page.viewPile('zk7 c');
  await unfocus();
  await page.watchSorts();
  await page.stepViewer(1);
  await page.waitFor(`vList[vIndex]?.prompt === 'zk7 b'`, { what: '→ : image suivante' });
  await page.stepViewer(-1);
  await page.waitFor(`vList[vIndex]?.prompt === 'zk7 c'`, { what: '← : image précédente' });
  await page.press('Escape');
  await page.waitFor(`vIndex < 0`, { what: 'Échap : fermée' });
  assert.deepEqual(await page.eval(`[sorts.length, pileView().length, !discarding]`), [0, 3, true]);
  await clearPile();
  page.assertNoErrors();
});

test('aucune touche ne supprime un tirage : Tirages et visionneuse des Tirages', async () => {
  await page.made('zk8 tirage');
  await page.keepPile();
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zk8 tirage')`, { what: 'tirage affiché' });
  await unfocus();
  await page.watchSorts();
  const keys = [[ARROWS.discard], [ARROWS.keep], ['Delete'], ['Backspace'], ['Backspace', { modifiers: ['meta'] }],
    ['z'], ['Enter']];
  for (const k of keys) await page.press(...k);
  await page.viewTirage(0);
  for (const k of keys) await page.press(...k);
  assert.equal(await page.sortsSent('delete'), 0, '/api/delete envoyé');
  assert.equal(await page.eval(`openedSheet === $('askSheet')`), false, 'confirmation de suppression ouverte');
  assert.equal(await bench.kept('zk8 tirage'), true);
  await page.closeViewer();
  await page.tab('labo');
  page.assertNoErrors();
});

test('Ctrl/⌘ + Entrée dans le prompt : « Révéler », une demande par appui', async () => {
  await page.freshLabo(bench);
  for (const modifiers of [['ctrl'], ['meta']]) {
    await page.typePrompt(`zk9 ${modifiers}`);
    await page.eval(`$('prompt').focus()`);
    const before = await page.eval(`pageJobs.length`);
    await page.keyDown(modifiers[0] === 'ctrl' ? 'Control' : 'Meta', { modifiers });
    await page.keyDown('Enter', { modifiers });
    for (let k = 0; k < 4; k++) await page.keyDown('Enter', { modifiers, repeat: true });
    await page.keyUp('Enter', { modifiers });
    await page.keyUp(modifiers[0] === 'ctrl' ? 'Control' : 'Meta');
    await page.waitFor(`pageJobs.length > ${before}`, { what: `${modifiers} + Entrée : demande envoyée` });
    await bench.idle({ page });
    assert.equal(await page.eval(`pageJobs.length - ${before}`), 1, 'une demande par appui');
    assert.equal(await page.eval(`pageJobs.at(-1).prompt`), `zk9 ${modifiers}`);
  }
  await page.typePrompt('zk9 entrée seule');
  await page.eval(`$('prompt').focus()`);
  const before = await page.eval(`pageJobs.length`);
  await page.press('Enter');                        // sans Ctrl ni ⌘ : un retour à la ligne, rien d'envoyé
  assert.equal(await page.eval(`pageJobs.length`), before);
  // une feuille ouverte par-dessus le champ, qui garde le focus (confirmation de « Révéler ») : rien d'envoyé
  await page.eval(`(() => { window.asked = 0; const f = window.fetch;
    window.fetch = (u, o) => { if (String(u) === '/api/generate') asked++; return f(u, o); }; })()`);
  await page.eval(`openSheet('setSheet'); $('prompt').focus()`);
  await page.press('Enter', { modifiers: ['meta'] });
  await page.closeSheet();
  assert.equal(await page.eval(`asked`), 0, 'demande envoyée sous une feuille ouverte');
  await unfocus();
  await page.typePrompt('');
  await clearPile();
  page.assertNoErrors();
});

test('boutons de tri marqués data-sort : Entrée répétée n\'en active aucun, même un bouton ajouté plus tard',
  async () => {
    assert.deepEqual(await page.eval(`[...document.querySelectorAll('[data-sort]')]
      .map(b => b.id || 'visionneuse ' + b.textContent.trim())`),
    ['pileNo', 'pileYes', 'visionneuse Jeter', 'visionneuse Garder']);
    // un futur bouton de tri, marqué comme les autres : un appui l'active, la répétition du système non
    await page.eval(`(() => { const b = document.createElement('button'); b.id = 'futureSort'; b.dataset.sort = '';
      b.textContent = 'Trier'; window.futureHits = 0; b.onclick = () => futureHits++; document.body.append(b);
      b.focus(); })()`);
    await page.keyDown('Enter');
    for (let k = 0; k < 4; k++) await page.keyDown('Enter', { repeat: true });
    await page.keyUp('Enter');
    assert.equal(await page.eval(`futureHits`), 1, 'Entrée répétée sur un bouton marqué data-sort');
    await page.eval(`$('futureSort').remove()`);
    page.assertNoErrors();
  });
