// Pile du Labo, dans la vue du téléphone : les images terminées de l'espace, lues du Mac (partagées entre appareils,
// gardées au rechargement), la dernière sur le dessus et deux devinées dessous, une carte par image d'un lot
// (« 2/3 ») ; ✓ garde (l'image passe dans les Tirages), ✕ jette après un bandeau « Annuler » de 5 s (rien n'est envoyé
// avant, ni à la fermeture de la page ; un seul bandeau à la fois) ; « Déjà triée » quand une autre page a trié
// l'image ; la visionneuse de la pile (Garder, Jeter, image suivante ; vrai mode et images d'entrée) ; carte d'échec en
// tête (message, Relancer, ✕) ; un second ✓ pendant le départ d'une carte ne trie rien de plus ; état vide ; message
// « Image prête » sur les Tirages, qui mène au Labo ; pile privée par ses routes (« Sortir » pendant le chargement
// d'une image : rien de privé demandé ensuite ; Jeter privé abandonné dès l'appui sur « Sortir », tri privé ignoré
// pendant la sortie) ; balayage de la carte du dessus au doigt et à la souris (seuil, geste vif, tampons, échec qui ne
// part qu'à gauche, pile redessinée sous le doigt, clic qui ouvre la visionneuse) ; après un tri, ✓, ✕ et la
// visionneuse ignorent un double appui jusqu'à l'image suivante affichée (0,3 s au moins).
//   venv/bin/python tests/check.py --quick --ui tests/ui/pile.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

let bench, chrome, page;
// requêtes retenues par Fetch.enable (test de la sortie pendant un chargement) : paused les note, held les garde
let paused = null;
const held = [];

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  page.on('Fetch.requestPaused', p => paused ? paused(p)
    : page.send('Fetch.continueRequest', { requestId: p.requestId }).catch(() => {}));
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);   // générations courtes
  await watchSorts();
});

after(async () => {
  bench?.release('pret');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const inPile = async prompt => (await bench.api('/api/pile')).some(it => it.prompt === prompt);
const kept = async prompt => (await bench.api('/api/history')).some(it => it.prompt === prompt);
// prompts des cartes dessinées, du dessus vers le dessous
const cards = () => page.eval(`[...$('pile').querySelectorAll('.pcard')]
  .map(c => c.querySelector('.pprompt').textContent)`);
const TOP = `$('pile').querySelector('[data-k="0"] .pprompt')?.textContent`;   // prompt de la carte du dessus
const top = () => page.eval(TOP);
// demandes de tri envoyées par la page (route et instant), notées au passage ; rechargée, la page ne les note plus
const watchSorts = () => page.eval(`(() => { window.sorts = []; const f = window.fetch;
  window.fetch = (u, o) => { if (/\\/(keep|discard)$/.test(String(u))) sorts.push({ url: String(u), at: Date.now() });
    return f(u, o); }; })()`);
const discards = () => page.eval(`sorts.filter(s => s.url.endsWith('/discard')).length`);
const watchToasts = () => page.eval(`(() => { window.seenToasts = []; window.toastWatch?.disconnect();
  window.toastWatch = new MutationObserver(() => seenToasts.push($('toastBox').textContent));
  toastWatch.observe($('toastBox'), { childList: true, characterData: true, subtree: true }); })()`);
// toutes les images de la pile affichée gardées, pour repartir d'une pile vide
async function clear() {
  await bench.idle({ page });
  await page.keepPile();
}

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
  assert.deepEqual(await cards(), ['zp1 second', 'zp1 premier']);
  assert.equal(await page.visible('#pileEmpty'), false);
  assert.equal(await page.eval(`$('pileCount').textContent`), '2 à trier');
  assert.equal(await page.eval(`$('runCount').textContent`), '2', 'pastille de l\'onglet : le nombre de la pile');
  assert.match(await page.eval(`$('pile').querySelector('[data-k="0"] .pset').textContent`), /^512×512 · 8 étapes/);
  await page.waitFor(`(i => i.complete && i.naturalWidth > 0)($('pile').querySelector('[data-k="0"] img'))`,
    { what: 'image de la carte du dessus' });
  assert.deepEqual(await page.overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/pile.png');
  await page.click('#pileYes');
  await page.waitFor(`!pileItems.some(it => it.prompt === 'zp1 second') && $('runCount').textContent === '1'`,
    { what: 'carte gardée' });
  assert.equal(await top(), 'zp1 premier');
  assert.equal(await kept('zp1 second'), true, 'dans les Tirages');
  assert.equal(await inPile('zp1 second'), false, 'plus dans la pile');
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zp1 second')`, { what: 'image gardée dans les Tirages' });
  await page.tab('labo');
  await clear();
  page.assertNoErrors();
});

test('✕ : bandeau « Annuler » de 5 s, rien envoyé avant ; « Annuler » remet la carte', async () => {
  await page.made('zp2 a jeter');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden && !$('pile').querySelector('.pcard')`, { what: 'bandeau, carte partie' });
  assert.equal(await page.eval(`$('undoBar').textContent`), 'Image jetéeAnnuler');
  assert.equal(await page.eval(`$('runCount').hidden`), true, 'l\'image jetée ne compte plus');
  await new Promise(r => setTimeout(r, 2500));      // au milieu du délai : rien n'est parti
  assert.equal(await discards(), 0, 'Jeter envoyé avant la fin du bandeau');
  await page.click('#undoBtn');
  await page.waitFor(`$('undoBar').hidden && ${TOP} === 'zp2 a jeter'`,
    { what: 'carte remise sur le dessus' });
  await new Promise(r => setTimeout(r, 3500));      // au-delà des 5 s du premier geste : toujours rien
  assert.equal(await discards(), 0, 'Jeter envoyé malgré « Annuler »');
  assert.equal(await inPile('zp2 a jeter'), true);
  // ✕ jusqu'au bout : la demande part à la fin du bandeau, pas avant
  const at = Date.now();
  await page.click('#pileNo');
  await page.waitFor(`sorts.some(s => s.url.endsWith('/discard'))`, { what: 'Jeter envoyé', timeout: 10000 });
  const sent = await page.eval(`sorts.find(s => s.url.endsWith('/discard')).at`);
  assert.ok(sent - at >= 4900, `Jeter envoyé après ${sent - at} ms`);
  await waitUntil(async () => !(await inPile('zp2 a jeter')), { what: 'image effacée de la pile' });
  assert.equal(await kept('zp2 a jeter'), false, 'pas dans les Tirages');
  await page.waitFor(`$('undoBar').hidden && !pileItems.length`, { what: 'bandeau parti, pile vide' });
  page.assertNoErrors();
});

test('double appui sur ✕ : une seule image part, rien avant 5 s ; Annuler, visionneuse ouverte', async () => {
  await page.made('zp2b dessous');
  await page.made('zp2b double');
  await page.eval(`sorts.length = 0; $('pileNo').click(); $('pileNo').click()`);   // deux appuis pendant l'envol
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp2b dessous'`, { what: 'bandeau, la suivante dessus' });
  await new Promise(r => setTimeout(r, 1000));
  assert.equal(await discards(), 0, 'Jeter envoyé par le second appui');
  assert.equal(await page.eval(`pileView().some(it => it.prompt === 'zp2b dessous')`), true, 'la suivante reste');
  await page.click('#undoBtn');
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  // jetée depuis la visionneuse, qui passe à la suivante : le bandeau reste à portée du doigt, au-dessus d'elle
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse' });
  await page.eval(`sortFromViewer('discard')`);
  await page.waitFor(`!$('undoBar').hidden && $('viewer').classList.contains('on')`,
    { what: 'bandeau, visionneuse ouverte' });
  assert.equal(await page.eval(`(r => document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2))
    ($('undoBtn').getBoundingClientRect()) === $('undoBtn')`), true, 'Annuler caché par la visionneuse');
  await page.click('#undoBtn');
  await page.eval(`closeViewer()`);
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  assert.equal(await discards(), 0);
  await clear();
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
  await waitUntil(() => kept('zp12 balayee'), { what: 'dans les Tirages' });
  assert.equal(await top(), 'zp12 dessous');
  page.assertNoErrors();
});

test('geste vif : sous le seuil mais rapide, la carte part', async () => {
  await page.waitFor(`!sortBusy()`, { what: 'tri précédent fini, carte suivante affichée' });
  await page.eval(`sorts.length = 0`);
  await page.swipe(CARD, 80);                        // 80 px, sous le tiers (≈ 115 px), en un geste rapide
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/keep'))`, { what: 'Garder envoyé' });
  await waitUntil(() => kept('zp12 dessous'), { what: 'dans les Tirages' });
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
  assert.equal(await discards(), 0, 'rien envoyé avant la fin du bandeau');
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
  await waitUntil(() => kept('zp12 autre'), { what: 'dans les Tirages' });
  await page.made('zp12 souris');
  await page.swipe(CARD, 2, 0, { mouse: true });     // un clic, à peine bougé : la visionneuse
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte par le clic' });
  await page.eval(`closeViewer()`);
  await clear();
  page.assertNoErrors();
});

test('rechargement pendant le bandeau : rien n\'est envoyé, l\'image est encore dans la pile', async () => {
  await page.made('zp3 doute');
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'page rechargée' });
  await page.waitFor(`pileItems.some(it => it.prompt === 'zp3 doute')`, { what: 'image dans la pile rechargée' });
  await new Promise(r => setTimeout(r, 5500));      // au-delà du délai : rien n'est parti avant le rechargement
  assert.equal(await inPile('zp3 doute'), true, 'image effacée malgré la fermeture de la page');
  assert.equal(await page.eval(`$('undoBar').hidden`), true);
  await watchSorts();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);
  await clear();
  page.assertNoErrors();
});

test('deux ✕ de suite : le premier Jeter part tout de suite, un seul bandeau pour le second', async () => {
  await page.made('zp4 un');
  await page.made('zp4 deux');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileNo');                      // zp4 deux
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp4 un' && !sortHeld`,
    { what: 'premier bandeau, carte suivante vue' });
  await page.click('#pileNo');                      // zp4 un : le Jeter de zp4 deux part
  await page.waitFor(`sorts.filter(s => s.url.endsWith('/discard')).length === 1`, { what: 'premier Jeter envoyé' });
  await waitUntil(async () => !(await inPile('zp4 deux')), { what: 'zp4 deux effacée' });
  assert.equal(await page.eval(`document.querySelectorAll('.undo:not([hidden])').length`), 1, 'un seul bandeau');
  await page.click('#undoBtn');                     // le second est annulé
  await page.waitFor(`${TOP} === 'zp4 un'`,
    { what: 'zp4 un remise' });
  assert.equal(await inPile('zp4 un'), true);
  await clear();
  page.assertNoErrors();
});

test('« Déjà triée » : l\'image gardée par une autre page quitte la pile', async () => {
  await page.made('zp5 disputee');
  // la page ne relit plus la pile d'elle-même : elle croit l'image encore là quand l'autre page l'a gardée
  await page.eval(`clearTimeout(statusTimer); window.realStatus = refreshStatus;
    window.refreshStatus = async () => {}`);
  const other = await chrome.phonePage();
  await other.goto(bench.url + '/');
  await other.waitFor(`pileItems.some(it => it.prompt === 'zp5 disputee')`, { what: 'pile sur l\'autre page' });
  await other.click('#pileYes');
  await waitUntil(async () => !(await inPile('zp5 disputee')), { what: 'gardée par l\'autre page' });
  other.assertNoErrors();
  other.close();
  await watchToasts();
  await page.click('#pileYes');
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
  await page.eval(`$('pileYes').click(); pileItems = [pileItems[1], pileItems[0], ...pileItems.slice(2)];
    pileShown = ''; renderPile(); $('pileYes').click()`);
  await page.waitFor(`sorts.length > 0 && !flying`, { what: 'Garder envoyé' });
  await new Promise(r => setTimeout(r, 600));
  assert.equal(await page.eval(`sorts.length`), 1, 'deux tris pour un départ');
  assert.deepEqual([await kept('zp14 seconde'), await inPile('zp14 premiere')], [true, true],
    'pas l\'image du premier appui qui est gardée');
  await clear();
  page.assertNoErrors();
});

test('double appui sur Jeter dans la visionneuse, et ✕ juste après un envol : la seconde image ne part pas',
  async () => {
    // décision du 24/10/2026 : Garder et Jeter bloqués jusqu'à l'image suivante affichée, 300 ms au moins
    for (const p of ['zp16 a', 'zp16 b', 'zp16 c']) await page.made(p);
    await page.click('#pile [data-k="0"] [data-open]');
    await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3`, { what: 'visionneuse' });
    await page.eval(`sorts.length = 0; sortFromViewer('discard'); sortFromViewer('discard')`);   // double appui
    await new Promise(r => setTimeout(r, 1000));
    assert.equal(await discards(), 0, 'Jeter de la première envoyé par le second appui');
    assert.deepEqual(await page.eval(`[vList.length, vList[vIndex].prompt]`), [2, 'zp16 b'], 'seconde image triée');
    await page.click('#undoBtn');
    await page.eval(`closeViewer()`);
    await page.waitFor(`${TOP} === 'zp16 c'`, { what: 'carte remise' });
    // ✕ puis un second ✕ juste après la fin de l'envol (220 ms) : la carte suivante ne part pas
    await page.eval(`sorts.length = 0; $('pileNo').click(); setTimeout(() => $('pileNo').click(), 250)`);
    await new Promise(r => setTimeout(r, 1000));
    assert.equal(await discards(), 0, 'Jeter envoyé par le second ✕');
    assert.equal(await page.eval(`discarding && pileView().length`), 2, 'deux cartes encore dans la pile');
    await page.click('#undoBtn');
    await clear();
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
  await clear();
  page.assertNoErrors();
});

test('visionneuse de la pile : Garder, Jeter, image suivante ; ni Supprimer ni « Garder celle-ci »', async () => {
  for (const p of ['zp7 a', 'zp7 b', 'zp7 c']) await page.made(p);
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3`, { what: 'visionneuse sur la pile' });
  assert.deepEqual(await page.eval(`vList.map(it => it.prompt)`), ['zp7 c', 'zp7 b', 'zp7 a']);
  assert.equal(await page.visible('#vSort'), true);
  assert.equal(await page.visible('#vDelete'), false);
  assert.equal(await page.eval(`!!$('vKeep')`), false);
  await page.eval(`sortFromViewer('keep')`);
  await page.waitFor(`vList.length === 2 && vList[vIndex].prompt === 'zp7 b' && !sortHeld`,
    { what: 'image suivante après Garder, affichée' });
  await waitUntil(() => kept('zp7 c'), { what: 'zp7 c gardée' });
  await page.eval(`sortFromViewer('discard')`);
  await page.waitFor(`vList.length === 1 && vList[vIndex].prompt === 'zp7 a' && !$('undoBar').hidden`,
    { what: 'image suivante après Jeter, bandeau' });
  await page.eval(`closeViewer()`);
  await page.click('#undoBtn');                     // la carte jetée revient sur le dessus de la pile
  await page.waitFor(`${TOP} === 'zp7 b'`, { what: 'zp7 b remise' });
  await clear();
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
  await clear();
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
  await page.click('#pileNo');
  await page.waitFor(`!$('pile').querySelector('.pfail') && ${TOP} === 'zp9 reussie'`,
    { what: 'échec retiré, image dessous' });
  assert.equal(await page.eval(`$('undoBar').hidden && sorts.length === 0`), true,
    'ni bandeau ni demande pour un échec');
  await clear();
  page.assertNoErrors();
});

test('sur les Tirages : « Image prête » mène au Labo', async () => {
  await watchToasts();
  await page.generate('HOLD=pret zp10 vue des Tirages');
  await page.tab('tirages');
  bench.release('pret');                           // elle finit pendant qu'on est sur les Tirages
  await page.waitFor(`seenToasts.includes('Image prête')`, { what: 'message « Image prête »' });
  await page.click('#toastBox');
  await page.waitFor(`mode === 'labo' && pileItems.some(it => it.prompt === 'HOLD=pret zp10 vue des Tirages')`,
    { what: 'Labo après le message, image dans la pile' });
  await clear();
  page.assertNoErrors();
});

test('espace privé : pile privée par ses routes ; un Jeter en attente à la sortie est abandonné', async () => {
  await page.made('zp11 publique');
  const exists = await page.eval(`privState.exists`);
  assert.equal(await page.eval(`postJson(${JSON.stringify(exists ? '/api/private/unlock' : '/api/private/create')},
    { code: ${JSON.stringify(CODE)} }).then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && !pileItems.length`, { what: 'dans l\'espace privé, pile privée vide' });
  await page.made('zp11 secrete garde');
  await page.made('zp11 secrete jete');
  assert.deepEqual(await cards(), ['zp11 secrete jete', 'zp11 secrete garde'], 'aucune carte publique');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.click('#privExit');                   // sortie pendant le bandeau
  await page.waitFor(`!inPrivate() && pileItems.some(it => it.prompt === 'zp11 publique')`, { what: 'pile publique' });
  assert.equal(await page.eval(`$('undoBar').hidden`), true, 'bandeau privé parti avec l\'espace');
  assert.deepEqual(await cards(), ['zp11 publique']);
  await new Promise(r => setTimeout(r, 5500));
  assert.equal(await discards(), 0, 'Jeter privé envoyé après la sortie');
  // de retour dans l'espace : l'image jetée avant la sortie y est encore ; ✓ la garde dans les Tirages privés
  assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
    .then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && pileItems.length === 2`, { what: 'pile privée intacte' });
  await page.click('#pileYes');
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/private/keep')) && pileItems.length === 1`,
    { what: 'gardée par la route privée' });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.equal(await inPile('zp11 secrete garde'), false, 'rien de privé dans la pile publique');
  await clear();
  page.assertNoErrors();
});

test('espace privé : un Jeter en attente est abandonné dès l\'appui sur « Sortir », pas à la réponse du Mac',
  async () => {
    assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
      .then(r => r.status)`), 200);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
    await page.made('zp17 secrete');
    await page.eval(`sorts.length = 0`);
    await page.click('#pileNo');
    await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
    // la réponse du Mac à « Sortir » se fait attendre ; une image privée demandée pendant ce temps est notée
    const privateAfter = [];
    paused = p => { if (p.request.url.includes('/api/private/lock')) held.push(p.requestId);
      else { privateAfter.push(p.request.url); page.send('Fetch.continueRequest', { requestId: p.requestId })
        .catch(() => {}); } };
    await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/private/lock' },
      { urlPattern: '*/api/private/image*' }, { urlPattern: '*/api/private/thumb*' }] });
    try {
      await page.click('#privExit');
      await waitUntil(() => held.length > 0, { what: 'sortie demandée' });
      assert.deepEqual(await page.eval(`[discarding, $('undoBar').hidden]`), [null, true], 'Jeter encore en attente');
      await new Promise(r => setTimeout(r, 300));
      assert.deepEqual(privateAfter, [], 'image privée demandée pendant la sortie (carte remise par l\'abandon)');
      // ✓ ou ✕ pendant la sortie : aucun tri privé ne part
      await page.eval(`sortBusy() || sortTop('keep')`);
      await new Promise(r => setTimeout(r, 600));
      assert.equal(await page.eval(`sorts.length`), 0, 'tri privé envoyé pendant la sortie');
      // un Jeter privé qui arriverait à sa fin pendant l'aller-retour ne part pas non plus (garde leavingPrivate)
      await page.eval(`(() => { const d = { tag: 'pzz', priv: true, body: { id: 'zz' } }; discarding = d;
        commitDiscard(d); })()`);
      assert.equal(await discards(), 0, 'Jeter privé envoyé pendant la sortie');
    } finally {
      paused = null;
      for (const id of held.splice(0)) await page.send('Fetch.continueRequest', { requestId: id }).catch(() => {});
      await page.send('Fetch.disable');
    }
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    assert.equal(await discards(), 0);
    assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
      .then(r => r.status)`), 200);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`inPrivate() && pileItems.some(it => it.prompt === 'zp17 secrete')`,
      { what: 'image privée encore dans sa pile' });
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    page.assertNoErrors();
  });

test('espace privé : une pile privée lue pendant la sortie n\'arrive pas dans la pile publique', async () => {
  assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
    .then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && pileItems.some(it => it.private)`, { what: 'pile privée' });
  // la prochaine lecture de la pile privée part dans l'espace, mais sa réponse n'arrive qu'après la sortie
  await page.holdFetch(`u => u === '/api/private/pile'`);
  await page.eval(`void (window.lateRead = loadPile())`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate() && !pileItems.some(it => it.private)`, { what: 'sorti, pile publique' });
  await page.releaseFetch();
  await page.eval(`lateRead`);                     // la lecture et sa suite (json, rendu), finies
  assert.equal(await page.eval(`pileItems.some(it => it.private)`), false, 'image privée dans la pile publique');
  assert.deepEqual(await page.leaks(['zp11 secrete', 'zp17 secrete']), [], 'prompt privé resté dans la page');
  page.assertNoErrors();
});

test('espace privé : « Sortir » pendant le chargement d\'une image de la pile : rien de privé demandé ensuite',
  async () => {
    assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
      .then(r => r.status)`), 200);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
    // images privées retenues en route (miniature et image) ; notées avant ou après l'appui sur « Sortir »
    const seen = [];
    let out = false;
    paused = p => { seen.push({ url: p.request.url, out }); held.push(p.requestId); };
    await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/private/thumb*' },
      { urlPattern: '*/api/private/image*' }] });
    try {
      await page.made('zp15 secrete en route');
      await waitUntil(() => seen.length > 0, { what: 'image privée demandée' });
      // la pile redessinée pendant le chargement : l'image de l'ancienne carte, détachée, l'attend encore
      await page.eval(`pileShown = ''; renderPile()`);
      out = true;
      // toute adresse privée donnée à une image après l'appui (attachée ou non : Chrome charge une image détachée)
      await page.eval(`(() => { window.srcAfter = [];
        const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
        Object.defineProperty(HTMLImageElement.prototype, 'src', { configurable: true, get: d.get,
          set(v) { if (String(v).includes('/api/private/')) srcAfter.push(String(v)); d.set.call(this, v); } }); })()`);
      await page.click('#privExit');
      await page.waitFor(`!inPrivate()`, { what: 'sorti' });
      // les chargements retenus échouent (abandonnés par la page) : une image qui les attendait ne redemande rien
      for (let k = 0; k < 2; k++) {
        await new Promise(r => setTimeout(r, 400));
        for (const id of held.splice(0)) await page.send('Fetch.failRequest', { requestId: id, errorReason: 'Aborted' })
          .catch(() => {});
      }
    } finally {
      paused = null;
      for (const id of held.splice(0)) await page.send('Fetch.failRequest', { requestId: id, errorReason: 'Aborted' })
        .catch(() => {});
      await page.send('Fetch.disable');
    }
    assert.deepEqual(seen.filter(r => r.out).map(r => r.url), [], 'image privée demandée après « Sortir »');
    assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image après « Sortir »');
    assert.deepEqual(await page.leaks(['zp15 secrete']), [], 'prompt privé resté dans la page');
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_ABORTED|ERR_FAILED/.test(e)));
    page.assertNoErrors();
  });
