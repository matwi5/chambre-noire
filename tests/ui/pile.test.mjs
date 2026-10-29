// Pile du Labo, dans la vue du téléphone : pile et tri. Les images terminées de l'espace, lues du Mac (partagées
// entre appareils, gardées au rechargement), la dernière sur le dessus et deux devinées dessous, une carte par image
// d'un lot (« 2/3 ») ; ✓ garde (l'image passe dans les Tirages), ✕ jette après un bandeau « Annuler » de 5 s (rien
// n'est envoyé avant, ni à la fermeture de la page ; un seul bandeau à la fois) ; « Déjà triée » quand une autre page
// a trié l'image ; la visionneuse de la pile (Garder, Jeter, image suivante ; vrai mode et images d'entrée) ; carte
// d'échec en tête (message, Relancer, ✕) ; un second ✓ pendant le départ d'une carte ne trie rien de plus ; état
// vide ; message « Image prête » sur les Tirages, qui mène au Labo ; balayage de la carte du dessus au doigt et à la
// souris (seuil, geste vif, tampons, échec qui ne part qu'à gauche, pile redessinée sous le doigt, clic qui ouvre la
// visionneuse). La pile privée et « Sortir » : pile-prive.test.mjs ; le verrou court et la page cachée :
// pile-verrou.test.mjs.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/pile.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse,
  TOP, PRESS, VIEWER_PRESS, SORT_IDLE, VIEWER_SEEN } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.ready();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);   // générations courtes
  await page.watchSorts();
});

after(async () => {
  bench?.release('pret');
  await chrome?.close();
  await bench?.stop();
});

test('pile vide : état vide en pixels, ni ✕ ni ✓', async () => {
  await page.tab('labo');
  assert.equal(await page.visible('#pileEmpty'), true);
  assert.match(await page.eval(`$('pileEmpty').textContent`), /Rien à trier/);
  assert.equal(await page.visible('#pileActs'), false);
  assert.equal(await page.eval(`$('runCount').hidden`), true, 'pastille de l\'onglet cachée à zéro');
  page.assertNoErrors();
});

test('la dernière sur le dessus, la suivante devinée dessous ; ✓ la garde dans les Tirages', async () => {
  await page.made('zp1 premier');
  await page.made('zp1 second');
  assert.deepEqual(await page.pileCards(), ['zp1 second', 'zp1 premier']);
  assert.equal(await page.visible('#pileEmpty'), false);
  assert.equal(await page.eval(`$('pileCount').textContent`), '2 à trier');
  assert.equal(await page.eval(`$('runCount').textContent`), '2', 'pastille de l\'onglet : le nombre de la pile');
  assert.match(await page.eval(`$('pile').querySelector('[data-k="0"] .pset').textContent`), /^512×512 · 8 étapes/);
  await page.waitFor(`(i => i.complete && i.naturalWidth > 0)($('pile').querySelector('[data-k="0"] img'))`,
    { what: 'image de la carte du dessus' });
  assert.deepEqual(await page.overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/pile.png');
  await page.sort('keep', { ready: false });
  await page.waitFor(`!pileItems.some(it => it.prompt === 'zp1 second') && $('runCount').textContent === '1'`,
    { what: 'carte gardée' });
  assert.equal(await page.topPrompt(), 'zp1 premier');
  assert.equal(await bench.kept('zp1 second'), true, 'dans les Tirages');
  assert.equal(await bench.inPile('zp1 second'), false, 'plus dans la pile');
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zp1 second')`, { what: 'image gardée dans les Tirages' });
  await page.tab('labo');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('✕ : bandeau « Annuler » de 5 s, rien envoyé avant ; « Annuler » remet la carte', async () => {
  await page.made('zp2 a jeter');
  await page.eval(`sorts.length = 0`);
  await page.sort('discard', { ready: false });
  await page.waitFor(`!$('undoBar').hidden && !$('pile').querySelector('.pcard')`, { what: 'bandeau, carte partie' });
  assert.equal(await page.eval(`$('undoBar').textContent`), 'Image jetéeAnnuler');
  assert.equal(await page.eval(`$('runCount').hidden`), true, 'l\'image jetée ne compte plus');
  await elapse(2500);                               // au milieu du délai : rien n'est parti
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé avant la fin du bandeau');
  await page.click('#undoBtn');
  await page.waitFor(`$('undoBar').hidden && ${TOP} === 'zp2 a jeter'`,
    { what: 'carte remise sur le dessus' });
  await elapse(3500);                               // au-delà des 5 s du premier geste : toujours rien
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé malgré « Annuler »');
  assert.equal(await bench.inPile('zp2 a jeter'), true);
  // ✕ jusqu'au bout : la demande part à la fin du bandeau, pas avant
  const at = Date.now();
  await page.sort('discard', { ready: false });
  await page.waitFor(`sorts.some(s => s.url.endsWith('/discard'))`, { what: 'Jeter envoyé', timeout: 10000 });
  const sent = await page.eval(`sorts.find(s => s.url.endsWith('/discard')).at`);
  assert.ok(sent - at >= 4900, `Jeter envoyé après ${sent - at} ms`);
  await waitUntil(async () => !(await bench.inPile('zp2 a jeter')), { what: 'image effacée de la pile' });
  assert.equal(await bench.kept('zp2 a jeter'), false, 'pas dans les Tirages');
  await page.waitFor(`$('undoBar').hidden && !pileItems.length`, { what: 'bandeau parti, pile vide' });
  page.assertNoErrors();
});

test('double appui sur ✕ : une seule image part, rien avant 5 s ; Annuler, visionneuse ouverte', async () => {
  await page.made('zp2b dessous');
  await page.made('zp2b double');
  await page.eval(`sorts.length = 0; ${PRESS.discard}; ${PRESS.discard}`);   // deux appuis pendant l'envol
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp2b dessous'`, { what: 'bandeau, la suivante dessus' });
  await page.topShown();                            // les deux appuis joués : envol fini, la suivante vue 0,3 s
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé par le second appui');
  assert.equal(await page.eval(`pileView().some(it => it.prompt === 'zp2b dessous')`), true, 'la suivante reste');
  await page.click('#undoBtn');
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  // jetée depuis la visionneuse, qui passe à la suivante : le bandeau reste à portée du doigt, au-dessus d'elle
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && ${VIEWER_SEEN}`,
    { what: 'visionneuse, image vue 0,3 s' });
  await page.eval(`${VIEWER_PRESS.discard}`);
  await page.waitFor(`!$('undoBar').hidden && $('viewer').classList.contains('on')`,
    { what: 'bandeau, visionneuse ouverte' });
  assert.equal(await page.eval(`(r => document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2))
    ($('undoBtn').getBoundingClientRect()) === $('undoBtn')`), true, 'Annuler caché par la visionneuse');
  await page.click('#undoBtn');
  await page.eval(`closeViewer()`);
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  assert.equal(await page.sortsSent('discard'), 0);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

// la carte du dessus, à balayer
const CARD = '#pile [data-k="0"] .pimg';
const TOP_CARD = `$('pile').querySelector('[data-k="0"]')`;
// rien n'est parti : aucune carte en route ni demande de tri (une carte qui part le fait dès le lâcher : flyOut)
const still = () => page.eval(`!flying && !$('pile').querySelector('.out-r, .out-l') && sorts.length === 0`);
// pendant un geste tenu : déplacement de la carte et opacité des tampons
const during = () => page.eval(`(c => ({ t: c.style.transform,
  keep: +getComputedStyle(c.querySelector('.stamp.keep')).opacity,
  drop: +getComputedStyle(c.querySelector('.stamp.drop')).opacity }))(${TOP_CARD})`);

test('balayage au doigt : la carte suit et penche, « Garder » à droite ; trop court ou lent : retour', async () => {
  await page.made('zp12 dessous');
  await page.made('zp12 balayee');
  await page.eval(`sorts.length = 0`);
  await page.swipe(CARD, 30);                        // trop court, même vif : rien
  assert.equal(await still(), true, 'trié par un balayage trop court');
  assert.equal(await page.eval(`${TOP_CARD}.style.transform`), '', 'carte revenue');
  // pendant le geste : la carte suit le doigt, penche, et dit ce qui va se passer
  try {
    await page.swipe(CARD, 90, 0, { hold: true });
    await page.waitFor(`${TOP_CARD}.style.transform.startsWith('translateX(90px)')`,
      { what: 'la carte suit le doigt' });           // (déplacements remis à l'image suivante du navigateur)
    const d = await during();
    assert.match(d.t, /translateX\(90px\) rotate\([\d.]+deg\)/);
    assert.ok(d.keep > 0 && d.drop === 0, `« Garder » montré : ${JSON.stringify(d)}`);
  } finally { await page.release(300); }   // lâcher lent : rien ne part
  await page.swipe(CARD, 90, 0, { pause: 300 });     // 90 px, sous le seuil, en un geste lent : elle revient
  assert.equal(await still(), true, 'trié par un geste lent sous le seuil');
  await page.swipe(CARD, 220);                       // au-delà du tiers de la largeur : gardée
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/keep'))`, { what: 'Garder envoyé' });
  await waitUntil(() => bench.kept('zp12 balayee'), { what: 'dans les Tirages' });
  assert.equal(await page.topPrompt(), 'zp12 dessous');
  page.assertNoErrors();
});

test('geste vif : sous le seuil mais rapide, la carte part', async () => {
  await page.waitFor(`${SORT_IDLE}`, { what: 'tri précédent fini, carte suivante affichée' });
  await page.eval(`sorts.length = 0`);
  await page.swipe(CARD, 80);                        // 80 px, sous le tiers (≈ 115 px), en un geste rapide
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/keep'))`, { what: 'Garder envoyé' });
  await waitUntil(() => bench.kept('zp12 dessous'), { what: 'dans les Tirages' });
  await page.made('zp12 gauche');
  page.assertNoErrors();
});

test('balayage au doigt vers la gauche : « Jeter », puis Jeter avec son bandeau, sans changer d\'onglet', async () => {
  await page.eval(`sorts.length = 0`);
  try {
    await page.swipe(CARD, -90, 0, { hold: true });
    await page.waitFor(`${TOP_CARD}.style.transform.startsWith('translateX(-90px)')`, { what: 'la carte suit' });
    const d = await during();
    assert.ok(d.drop > 0 && d.keep === 0, `« Jeter » montré : ${JSON.stringify(d)}`);
  } finally { await page.release(300); }   // lâcher lent : rien ne part
  await page.swipe(CARD, -220);
  await page.waitFor(`!$('undoBar').hidden && !pileView().some(it => it.prompt === 'zp12 gauche')`,
    { what: 'bandeau, carte partie' });
  assert.equal(await page.eval(`mode`), 'labo', 'un balayage de carte ne change pas d\'onglet');
  assert.equal(await page.sortsSent('discard'), 0, 'rien envoyé avant la fin du bandeau');
  await page.click('#undoBtn');
  await page.waitFor(`${TOP} === 'zp12 gauche'`, { what: 'carte remise' });
  page.assertNoErrors();
});

test('pile redessinée pendant le geste : le lâcher ne trie aucune carte', async () => {
  await page.made('zp12 sous');
  await page.made('zp12 autre');
  await page.eval(`sorts.length = 0`);
  try {
    // à la souris : le lâcher atteint la pile redessinée (au doigt, il reste à la carte retirée)
    await page.swipe(CARD, 90, 0, { mouse: true, hold: true });
    await page.waitFor(`${TOP_CARD}.style.transform.startsWith('translateX(90px)')`, { what: 'la carte suit' });
    // une autre image arrive sur le dessus pendant que le doigt tient la carte
    await page.eval(`pileItems = [pileItems[1], pileItems[0], ...pileItems.slice(2)]; renderPile()`);
  } finally { await page.release(300); }   // lâcher lent : rien ne part
  assert.equal(await still(), true, 'une carte triée sans avoir été tenue');
  await page.eval(`loadPile()`);
  await page.waitFor(`${TOP} === 'zp12 autre'`, { what: 'pile relue' });
  page.assertNoErrors();
});

const FAIL_ICON = '#pile [data-k="0"] .qicon';   // (le centre d'une carte d'échec peut être son bouton Relancer)
test('carte d\'échec : elle ne se tire pas vers la droite, et ne part qu\'à gauche', async () => {
  await page.generate('FAIL zp12 échec');
  await page.waitFor(`!!$('pile').querySelector('[data-k="0"] .pfail')`, { what: 'carte de l\'échec en tête' });
  await page.eval(`sorts.length = 0`);
  try {
    await page.swipe(FAIL_ICON, 150, 0, { hold: true });
    await page.eval(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);   // gestes rendus
    assert.equal((await during()).keep, 0, '« Garder » montré sur un échec');
    assert.equal(await page.eval(`${TOP_CARD}.style.transform`), '', 'un échec suit le doigt vers la droite');
  } finally { await page.release(300); }   // lâcher lent : rien ne part
  assert.equal(await page.eval(`!!$('pile').querySelector('[data-k="0"] .pfail')`), true, 'échec toujours là');
  await page.swipe(FAIL_ICON, -220);
  await page.waitFor(`!$('pile').querySelector('.pfail') && ${TOP} === 'zp12 autre'`, { what: 'échec retiré' });
  assert.equal(await page.eval(`sorts.length`), 0, 'aucune demande pour un échec');
  page.assertNoErrors();
});

test('à la souris : à droite gardée ; un balayage n\'ouvre pas la visionneuse, un clic oui', async () => {
  await page.eval(`sorts.length = 0`);
  await page.swipe(CARD, 90, 0, { mouse: true, pause: 300 });   // lent, sous le seuil : elle revient
  assert.equal(await still(), true);
  assert.equal(await page.eval(`$('viewer').classList.contains('on')`), false,
    'un balayage n\'ouvre pas la visionneuse');
  await page.swipe(CARD, 220, 0, { mouse: true });
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/keep'))`, { what: 'Garder envoyé' });
  await waitUntil(() => bench.kept('zp12 autre'), { what: 'dans les Tirages' });
  await page.made('zp12 souris');
  await page.swipe(CARD, 2, 0, { mouse: true });     // un clic, à peine bougé : la visionneuse
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte par le clic' });
  await page.eval(`closeViewer()`);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('rechargement pendant le bandeau : rien n\'est envoyé, l\'image est encore dans la pile', async () => {
  await page.made('zp3 doute');
  await page.sort('discard', { ready: false });
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.goto(bench.url + '/');
  await page.ready('page rechargée');
  await page.waitFor(`pileItems.some(it => it.prompt === 'zp3 doute')`, { what: 'image dans la pile rechargée' });
  await elapse(5500);                               // au-delà du délai : rien n'est parti avant le rechargement
  assert.equal(await bench.inPile('zp3 doute'), true, 'image effacée malgré la fermeture de la page');
  assert.equal(await page.eval(`$('undoBar').hidden`), true);
  await page.watchSorts();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('deux ✕ de suite : le premier Jeter part tout de suite, un seul bandeau pour le second', async () => {
  await page.made('zp4 un');
  await page.made('zp4 deux');
  await page.eval(`sorts.length = 0`);
  await page.sort('discard', { ready: false });                      // zp4 deux
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp4 un' && ${SORT_IDLE}`,
    { what: 'premier bandeau, carte suivante vue' });
  await page.sort('discard', { ready: false });                      // zp4 un : le Jeter de zp4 deux part
  await waitUntil(async () => await page.sortsSent('discard') === 1, { what: 'premier Jeter envoyé' });
  await waitUntil(async () => !(await bench.inPile('zp4 deux')), { what: 'zp4 deux effacée' });
  assert.equal(await page.eval(`document.querySelectorAll('.undo:not([hidden])').length`), 1, 'un seul bandeau');
  await page.click('#undoBtn');                     // le second est annulé
  await page.waitFor(`${TOP} === 'zp4 un'`,
    { what: 'zp4 un remise' });
  assert.equal(await bench.inPile('zp4 un'), true);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('« Déjà triée » : l\'image gardée par une autre page quitte la pile', async () => {
  await page.made('zp5 disputee');
  // la page ne relit plus la pile d'elle-même : elle croit l'image encore là quand l'autre page l'a gardée
  await page.eval(`clearTimeout(statusTimer); window.realStatus = refreshStatus;
    window.refreshStatus = async () => {}`);
  const other = await chrome.phonePage();
  try {
    await other.goto(bench.url + '/');
    await other.waitFor(`pileItems.some(it => it.prompt === 'zp5 disputee')`, { what: 'pile sur l\'autre page' });
    await other.topShown();
    await other.sort('keep', { ready: false });
    await waitUntil(async () => !(await bench.inPile('zp5 disputee')), { what: 'gardée par l\'autre page' });
    other.assertNoErrors();
  } finally {
    await other.close();
  }
  await page.watchToasts();
  await page.sort('keep', { ready: false });
  await page.waitFor(`seenToasts.includes('Déjà triée') && !pileItems.length`,
    { what: '« Déjà triée », pile vide' });
  await page.eval(`window.refreshStatus = realStatus; refreshStatus()`);
  // Chrome note dans sa console la réponse 404 du Garder refusé : seule erreur attendue ici
  assert.deepEqual(page.errors.filter(e => !/status of 404 .*\/api\/keep/.test(e)), []);
  page.errors.length = 0;
});

test('✓ puis une autre carte sur le dessus avant le départ : un second ✓ ne trie rien de plus', async () => {
  await page.made('zp14 premiere');
  await page.made('zp14 seconde');
  await page.eval(`sorts.length = 0`);
  // ✓ sur la carte du dessus, puis la pile redessinée (une autre image arrive dessus) et ✓ de nouveau, avant 220 ms
  await page.eval(`${PRESS.keep}; pileItems = [pileItems[1], pileItems[0], ...pileItems.slice(2)];
    pileShown = ''; renderPile(); ${PRESS.keep}`);
  await page.waitFor(`sorts.length > 0 && !flying`, { what: 'Garder envoyé' });
  await page.topShown();                           // les deux appuis joués : la carte suivante vue, rien en route
  assert.equal(await page.eval(`sorts.length`), 1, 'deux tris pour un départ');
  assert.deepEqual([await bench.kept('zp14 seconde'), await bench.inPile('zp14 premiere')], [true, true],
    'pas l\'image du premier appui qui est gardée');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('double appui sur Jeter dans la visionneuse, et ✕ juste après un envol : la seconde image ne part pas',
  async () => {
    // décision du 24/10/2026 : Garder et Jeter bloqués jusqu'à l'image suivante affichée, 300 ms au moins
    for (const p of ['zp16 a', 'zp16 b', 'zp16 c']) await page.made(p);
    await page.click('#pile [data-k="0"] [data-open]');
    await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3 && ${VIEWER_SEEN}`,
      { what: 'visionneuse, image vue 0,3 s' });
    await page.eval(`sorts.length = 0; ${VIEWER_PRESS.discard}; ${VIEWER_PRESS.discard}`);   // double appui
    await page.waitFor(`!flying && ${VIEWER_SEEN}`, { what: 'les deux appuis joués, image suivante vue 0,3 s' });
    assert.equal(await page.sortsSent('discard'), 0, 'Jeter de la première envoyé par le second appui');
    assert.deepEqual(await page.eval(`[vList.length, vList[vIndex].prompt]`), [2, 'zp16 b'], 'seconde image triée');
    await page.click('#undoBtn');
    await page.eval(`closeViewer()`);
    await page.waitFor(`${TOP} === 'zp16 c'`, { what: 'carte remise' });
    await page.topShown();                         // (la carte remise, vue 0,3 s : verrou court)
    // ✕ puis un second ✕ juste après la fin de l'envol (220 ms) : la carte suivante ne part pas
    await page.eval(`sorts.length = 0; window.zqSecond = false; ${PRESS.discard};
      setTimeout(() => { ${PRESS.discard}; zqSecond = true; }, 250)`);
    await page.waitFor(`zqSecond && !flying`, { what: 'second ✕ joué' });
    assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé par le second ✕');
    assert.equal(await page.eval(`discarding && pileView().length`), 2, 'deux cartes encore dans la pile');
    await page.click('#undoBtn');
    await page.emptyPile(bench);
    page.assertNoErrors();
  });

test('lot : une carte par image, marquée « rang/taille »', async () => {
  await page.eval(`opt.count = 3; saveOpt(); refreshChoices()`);
  await page.generate('zp6 lot');
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);
  await page.waitFor(`pileItems.filter(it => it.prompt === 'zp6 lot').length === 3`,
    { what: 'trois images', timeout: 30000 });
  assert.equal(await page.eval(`$('pile').querySelectorAll('.pcard').length`), 3);
  const ranks = await page.eval(`[...$('pile').querySelectorAll('.plot')].map(b => b.textContent)`);
  assert.deepEqual([...ranks].sort(), ['1/3', '2/3', '3/3']);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('visionneuse de la pile : Garder, Jeter, image suivante ; ni Supprimer ni « Garder celle-ci »', async () => {
  for (const p of ['zp7 a', 'zp7 b', 'zp7 c']) await page.made(p);
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3 && ${VIEWER_SEEN}`,
    { what: 'visionneuse sur la pile, image vue 0,3 s' });
  assert.deepEqual(await page.eval(`vList.map(it => it.prompt)`), ['zp7 c', 'zp7 b', 'zp7 a']);
  assert.equal(await page.visible('#vSort'), true);
  assert.equal(await page.visible('#vDelete'), false);
  assert.equal(await page.eval(`!!$('vKeep')`), false);
  await page.eval(`${VIEWER_PRESS.keep}`);
  await page.waitFor(`vList.length === 2 && vList[vIndex].prompt === 'zp7 b' && ${VIEWER_SEEN}`,
    { what: 'image suivante après Garder, affichée' });
  await waitUntil(() => bench.kept('zp7 c'), { what: 'zp7 c gardée' });
  await page.eval(`${VIEWER_PRESS.discard}`);
  await page.waitFor(`vList.length === 1 && vList[vIndex].prompt === 'zp7 a' && !$('undoBar').hidden`,
    { what: 'image suivante après Jeter, bandeau' });
  await page.eval(`closeViewer()`);
  await page.click('#undoBtn');                     // la carte jetée revient sur le dessus de la pile
  await page.waitFor(`${TOP} === 'zp7 b'`, { what: 'zp7 b remise' });
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('vrai mode et images d\'entrée : une édition à deux références les montre toutes', async () => {
  await page.eval(`(async () => { for (const c of ['#a03070', '#30a070']) {
    const cv = document.createElement('canvas'); cv.width = cv.height = 256; const x = cv.getContext('2d');
    x.fillStyle = c; x.fillRect(0, 0, 256, 256);
    inputImages.push(await toEntry(c + '.png', cv.toDataURL('image/png'))); }
    renderInputs(); })()`);
  await page.made('zp8 édition');
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse' });
  assert.equal(await page.eval(`vList[0].mode`), 'edit');
  assert.deepEqual(await page.eval(`vList[0].inputs`), ['ref_1.png', 'ref_2.png']);
  assert.match(await page.eval(`$('vInputs').textContent`), /2 images d'entrée/);
  await page.eval(`closeViewer()`);
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('échec : carte en tête avec le message du Mac et Relancer, ✓ grisé, ✕ la retire', async () => {
  await page.made('zp9 reussie');
  await page.generate('FAIL zp9 échec');
  await page.waitFor(`!!$('pile').querySelector('[data-k="0"] .pfail')`, { what: 'carte de l\'échec en tête' });
  assert.match(await page.eval(`$('pile').querySelector('.pfail .perr').textContent`), /^Échec : /);
  assert.equal(await page.eval(`!!$('pile').querySelector('.pfail [data-again]')`), true, 'Relancer');
  assert.equal(await page.eval(`$('pileYes').disabled`), true);
  await page.eval(`sorts.length = 0`);
  await page.waitFor(`${SORT_IDLE}`, { what: 'carte d\'échec vue 0,3 s' });   // (verrou court d'une carte arrivée)
  await page.sort('discard', { ready: false });
  await page.waitFor(`!$('pile').querySelector('.pfail') && ${TOP} === 'zp9 reussie'`,
    { what: 'échec retiré, image dessous' });
  assert.equal(await page.eval(`$('undoBar').hidden && sorts.length === 0`), true,
    'ni bandeau ni demande pour un échec');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('sur les Tirages : « Image prête » mène au Labo', async () => {
  await page.watchToasts();
  await page.generate('HOLD=pret zp10 vue des Tirages');
  await page.tab('tirages');
  bench.release('pret');                           // elle finit pendant qu'on est sur les Tirages
  await page.waitFor(`seenToasts.includes('Image prête')`, { what: 'message « Image prête »' });
  await page.click('#toastBox');
  await page.waitFor(`mode === 'labo' && pileItems.some(it => it.prompt === 'HOLD=pret zp10 vue des Tirages')`,
    { what: 'Labo après le message, image dans la pile' });
  await page.emptyPile(bench);
  page.assertNoErrors();
});
