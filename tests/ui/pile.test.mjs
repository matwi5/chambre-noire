// Pile du Labo, dans la vue du téléphone : les images terminées de l'espace, lues du Mac (partagées entre appareils,
// gardées au rechargement), la dernière sur le dessus et deux devinées dessous, une carte par image d'un lot (« 2/3 »)
// ; ✓ garde (l'image passe dans les Tirages), ✕ jette après un bandeau « Annuler » de 5 s (rien n'est envoyé avant, ni
// à la fermeture de la page ; un seul bandeau à la fois) ; « Déjà triée » quand une autre page a trié l'image ; la
// visionneuse de la pile (Garder, Jeter, image suivante ; vrai mode et images d'entrée) ; carte d'échec en tête
// (message, Relancer, ✕) ; un second ✓ pendant le départ d'une carte ne trie rien de plus ; état vide ; message « Image
// prête » sur les Tirages, qui mène au Labo ; pile privée par ses routes (✕ et ✓ privés, un Garder qui arrive seul dans
// les Tirages privés affichés ; « Sortir » juste après l'entrée, pile privée pas encore lue, ou pendant le chargement
// d'une image : rien de privé demandé ensuite, ni par un Garder refusé ni par une génération privée arrivée dans la
// file pendant la sortie ; Jeter privé abandonné dès l'appui sur « Sortir », tri privé ignoré pendant la sortie ;
// images des cartes retirées vidées au redessin ; aucune adresse privée chargée en avance hors de l'espace ;
// pendant « Sortir », ni ✓, ni ✕, ni flèches, ni balayage, ni la visionneuse ne trient, une carte qui partait
// revient) ;
// balayage de la carte du dessus au doigt et à la souris (seuil, geste vif, tampons, échec qui ne part qu'à gauche,
// pile redessinée sous le doigt, clic qui ouvre la visionneuse) ; après un tri, ✓, ✕ et la visionneuse ignorent un
// double appui jusqu'à l'image suivante affichée depuis 0,3 s, comme une carte arrivée sur le dessus sans tri d'ici ;
// carte masquée par Dessiner jamais triée ; aucun geste ne trie une image pas encore affichée,
// même 3 s plus tard, et une image illisible se trie une fois son chargement en échec,
// pas pendant.
//   venv/bin/python tests/check.py --quick --ui tests/ui/pile.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse, PHONE, TOP } from './driver.mjs';

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

const CODE = 'code-du-banc-1';
// prompts des cartes dessinées, du dessus vers le dessous
const cards = () => page.eval(`[...$('pile').querySelectorAll('.pcard')]
  .map(c => c.querySelector('.pprompt').textContent)`);
// toute adresse privée donnée à une image à partir de l'appel (attachée ou non : Chrome charge une image détachée,
// et sert sans requête une image déjà chargée par la page), notée dans srcAfter ; la surveillance n'est posée qu'une
// fois par page (srcWatched), chaque appel vide la liste
const watchPrivateSrc = () => page.eval(`(() => { window.srcAfter = []; if (window.srcWatched) return;
  window.srcWatched = true; const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', { configurable: true, get: d.get,
    set(v) { if (String(v).includes('/api/private/')) srcAfter.push(String(v)); d.set.call(this, v); } }); })()`);
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
  assert.equal(await page.topPrompt(), 'zp1 premier');
  assert.equal(await bench.kept('zp1 second'), true, 'dans les Tirages');
  assert.equal(await bench.inPile('zp1 second'), false, 'plus dans la pile');
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
  await page.click('#pileNo');
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
  await page.eval(`sorts.length = 0; $('pileNo').click(); $('pileNo').click()`);   // deux appuis pendant l'envol
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp2b dessous'`, { what: 'bandeau, la suivante dessus' });
  await page.topShown();                            // les deux appuis joués : envol fini, la suivante vue 0,3 s
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé par le second appui');
  assert.equal(await page.eval(`pileView().some(it => it.prompt === 'zp2b dessous')`), true, 'la suivante reste');
  await page.click('#undoBtn');
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  // jetée depuis la visionneuse, qui passe à la suivante : le bandeau reste à portée du doigt, au-dessus d'elle
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && !sortHeld`, { what: 'visionneuse, image vue 0,3 s' });
  await page.eval(`sortFromViewer('discard')`);
  await page.waitFor(`!$('undoBar').hidden && $('viewer').classList.contains('on')`,
    { what: 'bandeau, visionneuse ouverte' });
  assert.equal(await page.eval(`(r => document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2))
    ($('undoBtn').getBoundingClientRect()) === $('undoBtn')`), true, 'Annuler caché par la visionneuse');
  await page.click('#undoBtn');
  await page.eval(`closeViewer()`);
  await page.waitFor(`${TOP} === 'zp2b double'`, { what: 'carte remise' });
  assert.equal(await page.sortsSent('discard'), 0);
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
  await waitUntil(() => bench.kept('zp12 balayee'), { what: 'dans les Tirages' });
  assert.equal(await page.topPrompt(), 'zp12 dessous');
  page.assertNoErrors();
});

test('geste vif : sous le seuil mais rapide, la carte part', async () => {
  await page.waitFor(`!sortBusy()`, { what: 'tri précédent fini, carte suivante affichée' });
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
  await clear();
  page.assertNoErrors();
});

test('rechargement pendant le bandeau : rien n\'est envoyé, l\'image est encore dans la pile', async () => {
  await page.made('zp3 doute');
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.goto(bench.url + '/');
  await page.ready('page rechargée');
  await page.waitFor(`pileItems.some(it => it.prompt === 'zp3 doute')`, { what: 'image dans la pile rechargée' });
  await elapse(5500);                               // au-delà du délai : rien n'est parti avant le rechargement
  assert.equal(await bench.inPile('zp3 doute'), true, 'image effacée malgré la fermeture de la page');
  assert.equal(await page.eval(`$('undoBar').hidden`), true);
  await page.watchSorts();
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);
  await clear();
  page.assertNoErrors();
});

test('deux ✕ de suite : le premier Jeter part tout de suite, un seul bandeau pour le second', async () => {
  await page.made('zp4 un');
  await page.made('zp4 deux');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileNo');                      // zp4 deux
  await page.waitFor(`!$('undoBar').hidden && ${TOP} === 'zp4 un' && !sortBusy()`,
    { what: 'premier bandeau, carte suivante vue' });
  await page.click('#pileNo');                      // zp4 un : le Jeter de zp4 deux part
  await waitUntil(async () => await page.sortsSent('discard') === 1, { what: 'premier Jeter envoyé' });
  await waitUntil(async () => !(await bench.inPile('zp4 deux')), { what: 'zp4 deux effacée' });
  assert.equal(await page.eval(`document.querySelectorAll('.undo:not([hidden])').length`), 1, 'un seul bandeau');
  await page.click('#undoBtn');                     // le second est annulé
  await page.waitFor(`${TOP} === 'zp4 un'`,
    { what: 'zp4 un remise' });
  assert.equal(await bench.inPile('zp4 un'), true);
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
  await other.topShown();
  await other.click('#pileYes');
  await waitUntil(async () => !(await bench.inPile('zp5 disputee')), { what: 'gardée par l\'autre page' });
  other.assertNoErrors();
  await other.close();
  await page.watchToasts();
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
  await page.topShown();                           // les deux appuis joués : la carte suivante vue, rien en route
  assert.equal(await page.eval(`sorts.length`), 1, 'deux tris pour un départ');
  assert.deepEqual([await bench.kept('zp14 seconde'), await bench.inPile('zp14 premiere')], [true, true],
    'pas l\'image du premier appui qui est gardée');
  await clear();
  page.assertNoErrors();
});

test('double appui sur Jeter dans la visionneuse, et ✕ juste après un envol : la seconde image ne part pas',
  async () => {
    // décision du 24/10/2026 : Garder et Jeter bloqués jusqu'à l'image suivante affichée, 300 ms au moins
    for (const p of ['zp16 a', 'zp16 b', 'zp16 c']) await page.made(p);
    await page.click('#pile [data-k="0"] [data-open]');
    await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3 && !sortHeld`,
      { what: 'visionneuse, image vue 0,3 s' });
    await page.eval(`sorts.length = 0; sortFromViewer('discard'); sortFromViewer('discard')`);   // double appui
    await page.waitFor(`!flying && !sortHeld`, { what: 'les deux appuis joués, image suivante vue 0,3 s' });
    assert.equal(await page.sortsSent('discard'), 0, 'Jeter de la première envoyé par le second appui');
    assert.deepEqual(await page.eval(`[vList.length, vList[vIndex].prompt]`), [2, 'zp16 b'], 'seconde image triée');
    await page.click('#undoBtn');
    await page.eval(`closeViewer()`);
    await page.waitFor(`${TOP} === 'zp16 c'`, { what: 'carte remise' });
    await page.topShown();                         // (la carte remise, vue 0,3 s : verrou court)
    // ✕ puis un second ✕ juste après la fin de l'envol (220 ms) : la carte suivante ne part pas
    await page.eval(`sorts.length = 0; window.zqSecond = false; $('pileNo').click();
      setTimeout(() => { $('pileNo').click(); zqSecond = true; }, 250)`);
    await page.waitFor(`zqSecond && !flying`, { what: 'second ✕ joué' });
    assert.equal(await page.sortsSent('discard'), 0, 'Jeter envoyé par le second ✕');
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
  await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 3 && !sortHeld`,
    { what: 'visionneuse sur la pile, image vue 0,3 s' });
  assert.deepEqual(await page.eval(`vList.map(it => it.prompt)`), ['zp7 c', 'zp7 b', 'zp7 a']);
  assert.equal(await page.visible('#vSort'), true);
  assert.equal(await page.visible('#vDelete'), false);
  assert.equal(await page.eval(`!!$('vKeep')`), false);
  await page.eval(`sortFromViewer('keep')`);
  await page.waitFor(`vList.length === 2 && vList[vIndex].prompt === 'zp7 b' && !sortHeld`,
    { what: 'image suivante après Garder, affichée' });
  await waitUntil(() => bench.kept('zp7 c'), { what: 'zp7 c gardée' });
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
  await page.waitFor(`!sortBusy()`, { what: 'carte d\'échec vue 0,3 s' });   // (verrou court d'une carte arrivée)
  await page.click('#pileNo');
  await page.waitFor(`!$('pile').querySelector('.pfail') && ${TOP} === 'zp9 reussie'`,
    { what: 'échec retiré, image dessous' });
  assert.equal(await page.eval(`$('undoBar').hidden && sorts.length === 0`), true,
    'ni bandeau ni demande pour un échec');
  await clear();
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
  await elapse(5500);                               // au-delà des 5 s du bandeau : le Jeter privé n'est pas parti
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter privé envoyé après la sortie');
  // de retour dans l'espace : l'image jetée avant la sortie y est encore ; ✓ la garde dans les Tirages privés
  assert.equal(await page.eval(`postJson('/api/private/unlock', { code: ${JSON.stringify(CODE)} })
    .then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && pileItems.length === 2`, { what: 'pile privée intacte' });
  await page.topShown();
  await page.click('#pileYes');
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/private/keep')) && pileItems.length === 1`,
    { what: 'gardée par la route privée' });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.equal(await bench.inPile('zp11 secrete garde'), false, 'rien de privé dans la pile publique');
  await clear();
  page.assertNoErrors();
});

test('espace privé : ✕ jette par la route privée après le bandeau ; un Garder arrive seul dans les Tirages privés',
  async () => {
  const privPile = () => page.eval(`fetch('/api/private/pile').then(r => r.json()).then(l => l.map(it => it.prompt))`);
  const exists = await page.eval(`privState.exists`);
  assert.equal(await page.eval(`postJson(${JSON.stringify(exists ? '/api/private/unlock' : '/api/private/create')},
    { code: ${JSON.stringify(CODE)} }).then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && pileRead`, { what: 'dans l\'espace privé, pile privée lue' });
  await clear();
  await page.made('zp20 privee jetee');
  await page.made('zp20 privee gardee');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileYes');                    // le dessus, « gardee », passe aux Tirages privés
  await page.waitFor(`sorts.length === 1 && !sortBusy() && pileView().length === 1`, { what: 'gardée' });
  await page.click('#pileNo');                     // puis « jetee », après son bandeau
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/private/discard'))`,
    { what: 'Jeter envoyé par la route privée à la fin du bandeau', timeout: 10000 });
  await waitUntil(async () => !(await privPile()).includes('zp20 privee jetee'), { what: 'jetée du Mac' });
  assert.deepEqual(await page.eval(`sorts.map(s => s.url)`), ['/api/private/keep', '/api/private/discard']);
  // Tirages privés affichés : une image gardée ailleurs (même espace) y arrive sans les relire à la main
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zp20 privee gardee')`, { what: 'Tirages privés' });
  await page.tab('labo');
  await page.made('zp20 privee ailleurs');
  await page.tab('tirages');
  await page.eval(`loadHistory()`);                 // Tirages lus avant le Garder : c'est rev qui doit les relire
  const id = await page.eval(`pileItems.find(it => it.prompt === 'zp20 privee ailleurs').id`);
  assert.equal(await page.eval(`postJson('/api/private/keep', { id: ${JSON.stringify(id)} }).then(r => r.status)`),
    200);
  await page.waitFor(`[...$('histGrid').querySelectorAll('button[data-name]')]
    .some(b => b.getAttribute('aria-label') === 'zp20 privee ailleurs')`, { what: 'tirage privé arrivé seul' });
  await page.tab('labo');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.equal(await bench.kept('zp20 privee gardee'), false, 'rien de privé dans les Tirages publics');
  page.assertNoErrors();
});

test('espace privé : un Jeter en attente est abandonné dès l\'appui sur « Sortir », pas à la réponse du Mac',
  async () => {
    await page.enterPrivate(CODE);
    await page.made('zp17 secrete');
    await page.eval(`sorts.length = 0`);
    await page.click('#pileNo');
    await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
    // la réponse du Mac à « Sortir » se fait attendre ; une image privée demandée pendant ce temps est notée
    const x = await exitHeld({ noting: true });
    try {
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      assert.deepEqual(await page.eval(`[discarding, $('undoBar').hidden]`), [null, true], 'Jeter encore en attente');
      await page.waitFor(`${TOP} === 'zp17 secrete'`, { what: 'carte remise par l\'abandon' });
      await elapse(300);                           // le temps qu'une demande de son image parte (il n'en part aucune)
      assert.deepEqual(x.after.filter(u => /\/(image|thumb)/.test(u)), [],
        'image privée demandée pendant la sortie (carte remise par l\'abandon)');
      // ✓ ou ✕ pendant la sortie : aucun tri privé ne part
      await page.eval(`sortBusy() || sortTop('keep')`);
      await elapse(600);                           // au-delà de l'envol (0,22 s), à la fin duquel un tri part
      assert.equal(await page.eval(`sorts.length`), 0, 'tri privé envoyé pendant la sortie');
      // un Jeter privé qui arriverait à sa fin pendant l'aller-retour ne part pas non plus (garde leavingPrivate)
      await page.eval(`(() => { const d = { tag: 'pzz', priv: true, body: { id: 'zz' } }; discarding = d;
        commitDiscard(d); })()`);
      assert.equal(await page.sortsSent('discard'), 0, 'Jeter privé envoyé pendant la sortie');
    } finally {
      await endExitHeld(x);
    }
    assert.equal(await page.sortsSent('discard'), 0);
    await page.enterPrivate(CODE);
    await page.waitFor(`pileItems.some(it => it.prompt === 'zp17 secrete')`,
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

// « Sortir » à réponse retenue (page.holdRequests) : le verrouillage est retenu, un Garder privé aussi tant que keep
// et pas keepDone ; quand noting, toute autre requête privée (pile, Tirages, images) est notée dans after, et un suivi
// /api/job/<id> seulement si id est dans x.privateIds (les générations privées du test : celles d'une génération
// publique ne sont pas privées)
async function exitHeld({ keep = false, noting = false } = {}) {
  const x = { after: [], noting, keepDone: false, privateIds: new Set() };
  x.locking = () => x.h.held.some(r => r.url.includes('/api/private/lock'));
  x.h = await page.holdRequests(['lock', 'keep', 'pile', 'history', 'image*', 'thumb*', 'input*']
    .map(r => '*/api/private/' + r)
    .concat(['*/api/job/*']), p => { const u = p.request.url;
    if (u.includes('/api/private/lock') || keep && !x.keepDone && u.endsWith('/api/private/keep')) return true;
    const job = /\/api\/job\/([0-9a-f]+)/.exec(u);
    if (x.noting && (!job || x.privateIds.has(job[1]))) x.after.push(u);
    return false; });
  return x;
}
// la réponse du Mac à « Sortir » arrive : sortie appliquée
async function endExitHeld(x) {
  await x.h.release();
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
}
// dans l'espace privé, pile privée lue
async function enterPile() {
  await page.enterPrivate(CODE);
  await page.waitFor(`pileRead`, { what: 'pile privée lue' });
}

test('espace privé : « Sortir » juste après l\'entrée, pile privée pas encore lue : rien de privé demandé ensuite',
  async () => {
    // les lectures de la pile privée lancées à l'entrée ne répondent qu'une fois « Sortir » appuyé, avant la réponse
    // du Mac (machine chargée) ; pileReads : chaque lecture lancée par la page, pour attendre sa fin
    await page.holdFetch(`u => u === '/api/private/pile'`);
    await page.eval(`(() => { const f = window.loadPileOrig = loadPile; window.pileReads = [];
      window.loadPile = (...a) => { const p = f(...a); pileReads.push(p); return p; }; })()`);
    let x = null;
    try {
      await page.enterPrivate(CODE, { settle: false });   // (ses lectures de la pile sont retenues)
      await page.waitFor(`pileReads.length > 0`, { what: 'pile demandée' });
      // la réponse du Mac à « Sortir » se fait attendre ; une requête privée partie pendant ce temps est notée
      x = await exitHeld({ noting: true });
      await watchPrivateSrc();
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      await page.eval(`refreshStatus()`);          // état lu pendant la sortie (il dit l'espace encore ouvert)
      await page.releaseFetch();
      await page.eval(`Promise.all(pileReads)`);   // lectures de la pile finies (réponse, rendu)
      assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
      assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image pendant la sortie');
    } finally {
      await page.releaseFetch();
      if (x) await endExitHeld(x);
      await page.eval(`window.loadPileOrig && (window.loadPile = loadPileOrig)`);
    }
    page.assertNoErrors();
  });

test('espace privé : un Garder privé refusé pendant « Sortir » ne redessine pas la pile privée',
  async () => {
    await enterPile();
    await page.made('zp22 secrete gardee');
    await page.made('zp22 secrete suivante');
    const x = await exitHeld({ keep: true });
    try {
      await page.click('#pileYes');                // Garder la carte du dessus : sa réponse se fait attendre
      await waitUntil(() => x.h.held.some(r => r.url.endsWith('/keep')), { what: 'Garder envoyé' });
      await watchPrivateSrc();
      x.noting = true;
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      // le Mac refuse le Garder : l'image revient dans la pile (sa carte serait redessinée, ses images redemandées)
      x.keepDone = true;
      for (const r of x.h.take(u => u.endsWith('/keep'))) await page.send('Fetch.fulfillRequest', {
        requestId: r.requestId, responseCode: 503,
        responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
        body: Buffer.from('{"error":"moteur occupé"}').toString('base64') });
      await page.waitFor(`!sorting.size`, { what: 'réponse du Garder reçue' });
      assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
      assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image pendant la sortie');
    } finally {
      await endExitHeld(x);
    }
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/503/.test(e)));   // le refus du Mac
    page.assertNoErrors();
  });

test('espace privé : une génération privée arrivée dans la file pendant « Sortir » n\'est pas suivie', async () => {
  await enterPile();
  const x = await exitHeld({ noting: true });
  try {
    await page.click('#privExit');
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    // lancée d'un autre appareil pendant l'aller-retour (le Mac a encore la session) ; l'état lu ensuite la montre
    const { id } = await page.launch('HOLD=zp23 zp23 secrete en file', { private: true });
    x.privateIds.add(id);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`queueState.some(e => e.id === ${JSON.stringify(id)}) && !following.size`,
      { what: 'génération privée dans la file reçue, suivi fini' });
    assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
  } finally {
    await endExitHeld(x);
    bench.release('zp23');
    await bench.idle();
  }
  page.assertNoErrors();
});

test('espace privé : un suivi de génération privée revenu pendant « Sortir » ne l\'adopte pas', async () => {
  await enterPile();
  // le suivi d'une génération privée de la file (adoption) part avant « Sortir » ; sa réponse n'arrive que pendant
  let follow = true;
  const x = await exitHeld();
  const lockOrFollow = x.h.keep;
  x.h.keep = p => lockOrFollow(p) || follow && p.request.url.includes('/api/job/');
  try {
    const { id } = await page.launch('HOLD=zp24 zp24 secrete suivie', { private: true });
    x.privateIds.add(id);
    await page.eval(`refreshStatus()`);
    await waitUntil(() => x.h.held.some(r => r.url.includes('/api/job/')), { what: 'suivi demandé' });
    follow = false;
    x.noting = true;
    await page.click('#privExit');
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await x.h.free(u => u.includes('/api/job/'));
    await page.waitFor(`!following.size`, { what: 'réponse du suivi reçue' });
    assert.equal(await page.eval(`pageJobs.some(p => p.id === ${JSON.stringify(id)})`), false,
      'génération privée adoptée pendant la sortie');
    assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
  } finally {
    await endExitHeld(x);
    bench.release('zp24');
    await bench.idle();
  }
  page.assertNoErrors();
});

test('espace privé : une génération de la page qui finit pendant « Sortir » : rien de privé demandé ni posé',
  async () => {
    await enterPile();
    await page.generate('HOLD=zp25 zp25 secrete qui finit');
    const id = await page.eval(`pageJobs.at(-1).id`);
    // tours du suivi des générations de la page (pollJobs : une attente d'une seconde par tour), comptés
    await page.eval(`(() => { const t = window.zqSetTimeout = window.setTimeout; window.zqPolls = 0;
      window.setTimeout = (f, ms, ...a) => { if (new Error().stack.includes('pollJobs')) zqPolls++;
        return t(f, ms, ...a); }; })()`);
    const x = await exitHeld();
    x.privateIds.add(id);
    try {
      await watchPrivateSrc();
      x.noting = true;
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      bench.release('zp25');                       // elle finit sur le Mac pendant l'aller-retour
      await bench.idle();
      const polls = await page.eval(`zqPolls`);
      // un tour complet du suivi pendant la sortie, ou son arrêt (plus rien d'actif à suivre)
      await page.waitFor(`!polling || zqPolls >= ${polls + 2}`, { what: 'un tour du suivi pendant la sortie' });
      // la pile redessinée pendant la sortie (par une fin, un échec ou une génération disparue) : ses images ne sont
      // pas demandées
      await page.eval(`pileShown = ''; renderPile()`);
      assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
      assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image pendant la sortie');
    } finally {
      await page.eval(`window.setTimeout = zqSetTimeout`);   // minuteur de la page rendu
      await endExitHeld(x);
    }
    page.assertNoErrors();
  });

test('espace privé : pendant « Sortir », ni Tirages, ni file, ni « Voir le lot », ni visionneuse privés ; un second '
  + 'appui ne relance rien', async () => {
  await enterPile();
  await page.made('zp26 secrete tiree');           // un tirage privé à soi, lancé seul (--name) comme après les autres
  await page.keepPile();
  await page.tab('tirages');
  await page.waitFor(`[...$('histGrid').querySelectorAll('img')].some(i => i.src.includes('/api/private/'))`,
    { what: 'Tirages privés affichés' });
  // une vignette privée des Tirages pas encore chargée (chargement différé, Tirages cachés), à une adresse que la page
  // n'a jamais chargée : celle de la grille, déjà affichée, serait servie par le cache de Chrome (déjà chargée)
  await page.tab('labo');
  await page.eval(`(() => { const im = document.createElement('img'); im.id = 'zqLazy'; im.loading = 'lazy';
    im.src = thumbOf(histItems.find(it => it.private)) + '&zq=lazy'; $('histGrid').append(im); })()`);
  assert.equal(await page.eval(`$('zqLazy').complete`), false, 'vignette pas encore chargée (prémisse)');
  const x = await exitHeld({ noting: true });
  try {
    await watchPrivateSrc();
    // feuille de la file ouverte (ses cartes ne sont dessinées qu'alors), repère posé à la place de ses cartes
    await page.eval(`openSheet('fileSheet'); $('queueList').innerHTML = '<i id="zqMark"></i>'; queueHtml = 'zq'`);
    await page.eval(`(() => { const f = window.zqFetch = window.fetch; window.zqLockCalls = 0;
      window.fetch = (u, ...a) => (String(u) === '/api/private/lock' && zqLockCalls++, f(u, ...a)); })()`);
    await page.click('#privExit', { force: true });   // feuille de la file ouverte exprès : pas au doigt
    await page.click('#privExit', { force: true });   // second appui pendant l'attente
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    assert.equal(await page.eval(`zqLockCalls`), 1, 'second verrouillage envoyé par un second appui');
    assert.equal(await page.eval(`$('zqLazy').hasAttribute('src')`), false, 'vignette différée encore à charger');
    // la vignette différée appelée à l'écran (chargement immédiat) avant que les Tirages ne soient redessinés : une
    // adresse restée lui ferait demander son image, notée dans x.after ; sans adresse, elle est aussitôt complète
    await page.eval(`$('zqLazy').loading = 'eager'`);
    await page.waitFor(`$('zqLazy').complete`, { what: 'vignette différée chargée, ou sans adresse' });
    // vignette des Tirages en échec : sa seconde tentative (minuteur de 0,7 s, joué tout de suite ici)
    await page.eval(`(() => { const t = window.setTimeout; window.setTimeout = f => { f(); return 0; };
      try { const im = $('histGrid').querySelector('img'); delete im.dataset.retry; im.onerror(); }
      finally { window.setTimeout = t; } })()`);
    await page.tab('tirages', { force: true });    // les Tirages ouverts pendant la sortie, sous la feuille
    await page.eval(`histShown = ''; renderGallery()`);   // et redessinés (par une suppression, par exemple)
    await page.eval(`renderQueue()`);              // la file redessinée (son état relu pendant la sortie)
    // visionneuse ouverte sur une image privée qui a des images d'entrée
    await page.eval(`openViewer(0, [{ private: true, pile: true, id: 'zq3', name: 'prive_zq3',
      inputs: ['init.png'] }])`);
    assert.equal(await page.eval(`$('viewer').classList.contains('on')`), false,
      'visionneuse ouverte pendant la sortie');
    // « Voir le lot » d'une image privée de la pile
    await page.eval(`(() => { const lot = n => ({ private: true, pile: true, id: 'zq' + n, name: 'prive_zq' + n,
      lot: { id: 'zqL', rank: n, size: 2 } }); vList = [lot(1), lot(2)]; vIndex = 0; openLot(); })()`);
    assert.deepEqual(await page.eval(`[!!$('zqMark'), openedSheet === $('fileSheet')]`), [true, true],
      'file ou « Voir le lot » redessinés pendant la sortie');
    assert.deepEqual(x.after, [], 'requête privée partie pendant la sortie');
    assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image pendant la sortie');
  } finally {
    await page.eval(`window.zqFetch && (window.fetch = zqFetch); vList = []; vIndex = -1; closeSheet(); closeViewer()`);
    await endExitHeld(x);
    await page.tab('labo');
  }
  page.assertNoErrors();
});

test('espace privé : « Sortir » pendant le chargement d\'une image de la pile : rien de privé demandé ensuite',
  async () => {
    await page.enterPrivate(CODE);
    // images privées retenues en route (miniature et image) ; notées avant ou après l'appui sur « Sortir »
    const seen = [];
    let out = false;
    const h = await page.holdRequests(['*/api/private/thumb*', '*/api/private/image*'],
      p => (seen.push({ url: p.request.url, out }), true));
    const fail = async () => { for (const r of h.take()) await page.send('Fetch.failRequest',
      { requestId: r.requestId, errorReason: 'Aborted' }).catch(() => {}); };
    try {
      await page.made('zp15 secrete en route', { shown: false });
      await waitUntil(() => seen.length > 0, { what: 'image privée demandée' });
      // la pile redessinée pendant le chargement : l'image de l'ancienne carte, détachée, l'attend encore
      await page.eval(`pileShown = ''; renderPile()`);
      out = true;
      await watchPrivateSrc();
      await page.click('#privExit');
      await page.waitFor(`!inPrivate()`, { what: 'sorti' });
      // les chargements retenus échouent (abandonnés par la page) : une image qui les attendait ne redemande rien
      for (let k = 0; k < 2; k++) {
        await elapse(400);                         // une demande refaite par une image en échec arrive, retenue
        await fail();
      }
    } finally {
      await fail();
      await h.release();
    }
    assert.deepEqual(seen.filter(r => r.out).map(r => r.url), [], 'image privée demandée après « Sortir »');
    assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image après « Sortir »');
    assert.deepEqual(await page.leaks(['zp15 secrete']), [], 'prompt privé resté dans la page');
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_ABORTED|ERR_FAILED/.test(e)));
    page.assertNoErrors();
  });

test('espace privé : la pile redessinée efface les images des cartes qu\'elle retire', async () => {
  await enterPile();
  await page.made('zp24 secrete dessous');
  await page.made('zp24 secrete dessus');
  try {
    // (la pile privée peut garder des images des tests d'avant : deux cartes au moins)
    await page.waitFor(`(l => l.length >= 2 && l.every(i => i.getAttribute('src')))(
      [...$('pile').querySelectorAll('.pimg img')])`, { what: 'images des cartes posées' });
    // les images des cartes dessinées (bouton Avant compris), gardées après leur retrait de la page
    await page.eval(`window.oldImgs = [...$('pile').querySelectorAll('img')]`);
    await page.click('#pileYes');
    await page.waitFor(`!oldImgs[0].isConnected && !sortBusy()`, { what: 'pile redessinée' });
    assert.deepEqual(await page.eval(`oldImgs.filter(i => i.getAttribute('src') || i.want).length`), 0,
      'image privée gardée par une carte retirée');
  } finally {
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  }
  page.assertNoErrors();
});

test('hors de l\'espace privé : aucune adresse privée n\'est chargée en avance', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await watchPrivateSrc();
  // aucun chemin de la page n'y mène hors de l'espace (rappel tardif d'une image privée) : appel direct
  const u = '/api/private/thumb?id=zz';
  assert.equal(await page.eval(`preload(${JSON.stringify(u)}).gone === true && !ready.has(${JSON.stringify(u)})`),
    true, 'adresse privée chargée hors de l\'espace');
  assert.deepEqual(await page.eval(`srcAfter`), [], 'adresse privée donnée à une image hors de l\'espace');
  // une adresse qui n'est pas de l'espace se charge toujours
  assert.equal(await page.eval(`preload('data:image/gif;base64,R0lGODlhAQABAAAAACw=').gone`), undefined);
  page.assertNoErrors();
});

// pendant « Sortir » (réponse du Mac retenue), la carte du dessus privée : son prompt, son image posée, partie ou non
// (out-l, out-r), déplacée ou tamponnée (transform, --swipe), un départ en cours, un Jeter en attente, les tris envoyés
const stillTop = () => page.eval(`(() => { const c = $('pile').querySelector('[data-k="0"]');
  return { top: c?.querySelector('.pprompt')?.textContent, img: !!c?.querySelector('.pimg img')?.getAttribute('src'),
    out: /out-[lr]/.test(c?.className || ''),
    moved: !!c?.style.transform || !!Number(c?.style.getPropertyValue('--swipe')),
    flying, discarding: !!discarding, sorts: sorts.length }; })()`);
// pile privée vidée, puis deux images dessus ; renvoie la sortie à réponse retenue, pas encore demandée
async function privateTwo(tag) {
  await enterPile();
  await clear();
  await page.made(`${tag} secrete dessous`);
  await page.made(`${tag} secrete dessus`);
  await page.waitFor(`!sortBusy()`, { what: 'pile au repos' });
  await page.eval(`sorts.length = 0`);
  return exitHeld();
}

test('espace privé : pendant « Sortir », ✓, ✕, les flèches et le balayage ne font rien sur la carte du dessus',
  async () => {
    const x = await privateTwo('zp28');
    const calm = { top: 'zp28 secrete dessus', img: true, out: false, moved: false, flying: false, discarding: false,
      sorts: 0 };
    try {
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      for (const [what, act] of [['✓', () => page.click('#pileYes')], ['✕', () => page.click('#pileNo')],
        ['→', () => page.press('ArrowRight')], ['←', () => page.press('ArrowLeft')],
        ['balayage', () => page.swipe('#pile .pimg', -200)]]) {
        await act();
        await elapse(400);                         // (au-delà de l'envol d'une carte, 0,22 s)
        assert.deepEqual(await stillTop(), calm, `${what} pendant « Sortir »`);
      }
    } finally {
      await endExitHeld(x);
    }
    await page.enterPrivate(CODE);
    await page.waitFor(`pileItems.filter(it => it.prompt.startsWith('zp28 secrete')).length === 2`,
      { what: 'les deux images encore dans la pile privée' });
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    page.assertNoErrors();
  });

test('espace privé : une carte privée déjà en partance à l\'appui sur « Sortir » revient sur la pile, sans tri',
  async () => {
    const x = await privateTwo('zp29');
    try {
      // ✕ puis « Sortir » pendant l'envol, la carte lâchée comme au bout d'un balayage à gauche (--swipe : tampon
      // « Jeter » montré)
      await page.eval(`$('pile').querySelector('[data-k="0"]').style.setProperty('--swipe', '-1.6');
        $('pileNo').click(); $('privExit').click()`);
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      await elapse(400);
      assert.deepEqual(await stillTop(),
        { top: 'zp29 secrete dessus', img: true, out: false, moved: false, flying: false, discarding: false, sorts: 0 },
        'carte partie');
      assert.deepEqual(await page.eval(`[...$('pile').querySelectorAll('[data-k="0"] .stamp')]
        .map(s => getComputedStyle(s).opacity)`), ['0', '0'], 'tampon resté sur la carte revenue');
    } finally {
      await endExitHeld(x);
    }
    page.assertNoErrors();
  });

test('espace privé : pendant « Sortir », Garder et Jeter de la visionneuse ne font rien', async () => {
  await enterPile();
  await clear();
  await page.made('zp30 secrete seule');
  await page.viewPile('zp30 secrete seule');
  await page.eval(`sorts.length = 0`);
  const x = await exitHeld();
  try {
    // (la visionneuse couvre l'en-tête au doigt ; le clavier y mène par Tab puis Entrée : ici, appui par la page)
    await page.eval(`$('privExit').click()`);
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    for (const k of [0, 1]) {                      // Jeter, puis Garder
      await page.eval(`$('vSort').querySelectorAll('.btn')[${k}].click()`);
      await elapse(400);
      assert.deepEqual(await page.eval(`[vIndex >= 0 && vList[vIndex]?.prompt, !!discarding, sorts.length]`),
        ['zp30 secrete seule', false, 0], `${k ? 'Garder' : 'Jeter'} de la visionneuse pendant « Sortir »`);
    }
  } finally {
    await endExitHeld(x);
  }
  page.assertNoErrors();
});

// carte du dessus publique : son prompt, son image posée (posed : miniature ou image, chargement fini), un Jeter en
// attente, les tris envoyés
const TOP_IMG = `$('pile').querySelector('[data-k="0"] .pimg img')`;
const topState = () => page.eval(`({ top: ${TOP}, posed: posed(${TOP_IMG}), discarding: !!discarding,
  sorts: sorts.length })`);
// une image neuve sur le dessus, ses images (miniature, image complète) retenues avant le Mac
async function heldTop(prompt) {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made(`${prompt} dessous`);
  await page.waitFor(`!sortBusy()`, { what: 'pile au repos' });
  const h = await page.holdRequests(['*/api/result*', '*/api/thumb*'], () => true);
  await page.generate(`${prompt} dessus`);
  await page.waitFor(`${TOP} === ${JSON.stringify(`${prompt} dessus`)}`, { what: 'carte du dessus dessinée' });
  await waitUntil(() => h.held.length > 0, { what: 'image du dessus demandée' });
  await page.eval(`sorts.length = 0`);
  return h;
}

test('image du dessus pas encore affichée : ni ✓, ni ✕, ni flèches, ni balayage, ni la visionneuse ne la trient',
  async () => {
  const h = await heldTop('zp31');
  const unseen = { top: 'zp31 dessus', posed: false, discarding: false, sorts: 0 };
  try {
    // verrou court levé à la main : seule la garde de l'image affichée (posed) reste, c'est elle qu'on éprouve
    await page.eval(`releaseSort()`);
    for (const [what, act] of [['✓', () => page.click('#pileYes')], ['✕', () => page.click('#pileNo')],
      ['→', () => page.press('ArrowRight')], ['←', () => page.press('ArrowLeft')],
      ['balayage', () => page.swipe('#pile .pimg', -200)]]) {
      await act();
      await elapse(400);
      assert.deepEqual(await topState(), unseen, `${what} sur une image pas affichée`);
    }
    await page.viewPile('zp31 dessus', { seen: false });   // visionneuse : son image retenue elle aussi
    await page.eval(`$('vSort').querySelector('.btn').click()`);   // Jeter
    await elapse(400);
    assert.deepEqual(await page.eval(`[vIndex >= 0 && vList[vIndex]?.prompt, !!discarding, sorts.length]`),
      ['zp31 dessus', false, 0], 'Jeter de la visionneuse sur une image pas affichée');
    await page.closeViewer();
  } finally {
    await h.release();
  }
  // l'image arrive : ✕ la jette (bandeau), comme d'habitude
  await page.topShown();
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('après un tri, la suivante pas encore affichée : ✕ ne la jette pas, même 3 s plus tard',
  async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  // images des deux cartes retenues dès leur création ; celles du dessus seules libérées ensuite (pass)
  let pass = null;
  const h = await page.holdRequests(['*/api/result*', '*/api/thumb*'], p => !(pass && p.request.url.includes(pass)));
  try {
    await page.made('zp33 suivante', { shown: false });
    await page.made('zp33 dessus', { shown: false });
    await page.waitFor(`${TOP} === 'zp33 dessus'`, { what: 'carte du dessus dessinée' });
    pass = encodeURIComponent(await page.eval(`pileItems.find(it => it.prompt === 'zp33 dessus').name`));
    await h.free(u => u.includes(pass));
    await page.topShown();
    await page.eval(`sorts.length = 0`);
    await page.click('#pileYes');                  // le dessus gardé : la suivante dessus, sans son image
    await page.waitFor(`${TOP} === 'zp33 suivante'`, { what: 'suivante sur le dessus' });
    await elapse(3200);                            // (l'ancien plafond du verrou, 3 s, dépassé)
    await page.click('#pileNo');
    await elapse(400);
    assert.deepEqual(await topState(), { top: 'zp33 suivante', posed: false, discarding: false, sorts: 1 },
      '✕ 3 s plus tard sur une image pas affichée (seul le Garder d\'avant envoyé)');
  } finally {
    await h.release();
  }
  await clear();
  page.assertNoErrors();
});

test('image du dessus illisible : la carte se trie une fois l\'échec du chargement constaté, pas pendant',
  async () => {
  const h = await heldTop('zp32');
  const fail = async () => { for (const r of h.take()) await page.send('Fetch.failRequest',
    { requestId: r.requestId, errorReason: 'Failed' }).catch(() => {}); };
  try {
    await fail();                                  // chargement à part en échec
    // la page redonne l'adresse au navigateur, qui la redemande (retenue) : adresse posée, chargement en cours
    await page.waitFor(`(i => !!i?.getAttribute('src') && !i.complete)(${TOP_IMG})`,
      { what: 'nouvel essai du navigateur en cours' });
    await page.click('#pileNo');
    await elapse(400);
    assert.deepEqual(await topState(), { top: 'zp32 dessus', posed: false, discarding: false, sorts: 0 },
      '✕ pendant le nouvel essai');
    await waitUntil(async () => (await fail(), (await topState()).posed), { what: 'échec du chargement constaté' });
  } finally {
    await h.release();
  }
  await page.waitFor(`!sortBusy()`, { what: 'pile au repos' });
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau sur la carte illisible' });
  await page.click('#undoBtn');
  await clear();
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_FAILED|ERR_ABORTED/.test(e)));
  page.assertNoErrors();
});

// « Rien ne bouge pendant Sortir, partout » : demandes de génération envoyées par la page (/api/generate), comptées
// dans asked à partir de l'appel
const watchGenerate = () => page.eval(`(() => { window.asked = 0; if (window.askWatched) return;
  window.askWatched = true; const f = window.fetch;
  window.fetch = (u, o) => { if (String(u) === '/api/generate') asked++; return f(u, o); }; })()`);
// la carte du dessus et les images de la pile affichée : chacune a une adresse (aucune carte redessinée sans image)
const pileShot = () => page.eval(`({ top: ${TOP}, bare: [...$('pile').querySelectorAll('.pimg img')]
  .filter(i => !i.getAttribute('src')).length, discarding: !!discarding, undo: !$('undoBar').hidden, held: sortHeld,
  sorts: sorts.length })`);

test('espace privé : pendant « Sortir », Relancer d\'une carte d\'échec privée ne fait rien', async () => {
  await enterPile();
  await page.generate('FAIL zp34 secrete echec');
  await page.waitFor(`!!$('pile').querySelector('[data-k="0"] .pfail [data-again]')`,
    { what: 'carte d\'échec privée en tête' });
  await watchGenerate();
  const x = await exitHeld();
  try {
    await page.click('#privExit');
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await page.click('#pile [data-k="0"] [data-again]');
    await elapse(400);
    assert.deepEqual(await page.eval(`[asked, !!$('pile').querySelector('[data-k="0"] .pfail')]`), [0, true],
      'Relancer pendant « Sortir »');
  } finally {
    await endExitHeld(x);
  }
  page.assertNoErrors();
});

test('espace privé : pendant « Sortir », Relancer de la visionneuse et « Révéler » ne partent pas', async () => {
  await enterPile();
  await clear();
  await page.made('zp35 secrete vue');
  await page.viewPile('zp35 secrete vue');
  await page.eval(`$('prompt').value = 'zp35 secrete saisie'`);
  await watchGenerate();
  const x = await exitHeld();
  try {
    await page.eval(`$('privExit').click()`);      // (la visionneuse couvre l'en-tête)
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await page.eval(`$('vAgain').click()`);
    await elapse(400);
    assert.deepEqual(await page.eval(`[asked, vIndex >= 0 && vList[vIndex]?.prompt]`), [0, 'zp35 secrete vue'],
      'Relancer de la visionneuse pendant « Sortir »');
    await page.eval(`$('go').click()`);
    await elapse(400);
    assert.equal(await page.eval(`asked`), 0, '« Révéler » pendant « Sortir »');
  } finally {
    await endExitHeld(x);
  }
  page.assertNoErrors();
});

test('espace privé : « Révéler » confirmé (génération longue) après l\'appui sur « Sortir » ne part pas',
  async () => {
    await enterPile();
    await page.eval(`$('prompt').value = 'zp38 secrete longue'; estSeconds = 7200`);   // (plus d'une heure : confirmée)
    await watchGenerate();
    const x = await exitHeld();
    try {
      await page.eval(`$('go').click()`);
      await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de la génération longue' });
      await page.eval(`$('privExit').click()`);    // (la feuille couvre l'en-tête)
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      await page.eval(`answer(true)`);
      await elapse(400);
      assert.equal(await page.eval(`asked`), 0, '« Révéler » parti pendant « Sortir »');
    } finally {
      await endExitHeld(x);
    }
    page.assertNoErrors();
  });

test('espace privé : un Jeter privé en attente à l\'appui sur « Sortir » : la carte revient avec son image, sans'
  + ' verrou, et y reste après un refus', async () => {
  const x = await privateTwo('zp36');
  try {
    await page.topShown();
    await page.click('#pileNo');                   // le dessus jeté : bandeau, le dessous sur le dessus
    await page.waitFor(`!!discarding && ${TOP} === 'zp36 secrete dessous'`, { what: 'Jeter en attente' });
    await page.topShown();
    // verrou de la visionneuse tenu comme si son image suivante n'était jamais vue (il ne se lèverait pas)
    await page.eval(`holdSort(() => ({ key: 'zp36', shown: false }))`);
    await page.click('#privExit');
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await elapse(400);
    const back = { top: 'zp36 secrete dessus', bare: 0, discarding: false, undo: false, held: false, sorts: 0 };
    assert.deepEqual(await pileShot(), back, 'pile pendant « Sortir »');
    await page.refuseExit(x.h);
    // la carte du dessus redessinée au refus (son image a pu être abandonnée) reprend le verrou court
    assert.equal(await page.eval(`topHeld`), true, 'carte remise sans verrou court après le refus');
    await page.topShown();
    assert.deepEqual(await pileShot(), back, 'pile après le refus');
  } finally {
    await x.h.release();
  }
  await page.privateIdle();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.deepEqual(page.errors.filter(e => !/status of 500/.test(e)), [], 'erreurs de la console');
  page.errors.length = 0;
});

// bouton de la visionneuse qui appelle ce code (onclick)
const vBtn = code => `document.querySelector(${JSON.stringify(`#viewer [onclick="${code}"]`)})`;

test('espace privé : pendant « Sortir », aucune action de la visionneuse ne part (Éditer, Dessiner, Reprendre,'
  + ' Supprimer, Copier, Télécharger)', async () => {
  await enterPile();
  await clear();
  await page.made('zp39 secrete vue');
  await page.viewPile('zp39 secrete vue');
  const x = await exitHeld({ noting: true });
  x.privateIds = new Set(await page.eval(`pageJobs.filter(p => p.private).map(p => p.id)`));
  try {
    await page.eval(`$('privExit').click()`);      // (la visionneuse couvre l'en-tête)
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    const n = await page.eval(`inputImages.length`);
    for (const code of [`viewerAction('edit')`, `viewerAction('mask')`, `viewerAction('resume')`,
      `viewerAction('delete')`, 'viewerCopy()']) {
      await page.eval(`${vBtn(code)}.click()`);
      await elapse(300);
      assert.deepEqual(await page.eval(`[vIndex >= 0 && vList[vIndex]?.prompt, openedSheet?.id ?? null,
        inputImages.length]`), ['zp39 secrete vue', null, n], `${code} pendant « Sortir »`);
    }
    assert.equal(await page.eval(`(e => { $('vDl').dispatchEvent(e); return e.defaultPrevented; })(
      new MouseEvent('click', { cancelable: true }))`), true, 'téléchargement pendant « Sortir »');
    assert.deepEqual(x.after, [], 'requête privée partie pendant « Sortir »');
  } finally {
    await endExitHeld(x);
  }
  page.assertNoErrors();
});

test('espace privé : Supprimer confirmé après l\'appui sur « Sortir » ne supprime rien', async () => {
  await enterPile();
  await clear();
  await page.made('zp40 secrete tirage');
  await page.keepPile();                           // (dans les Tirages privés)
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zp40 secrete tirage')`, { what: 'tirage privé' });
  await page.eval(`openViewer(histItems.findIndex(it => it.prompt === 'zp40 secrete tirage'), histItems)`);
  await page.eval(`sorts.length = 0; ${vBtn(`viewerAction('delete')`)}.click()`);
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de suppression' });
  const x = await exitHeld();
  try {
    await page.eval(`$('privExit').click()`);      // (la feuille couvre l'en-tête)
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await page.eval(`answer(true)`);
    await elapse(400);
    assert.equal(await page.sortsSent('delete'), 0, 'suppression privée envoyée pendant « Sortir »');
  } finally {
    await endExitHeld(x);
    await page.tab('labo');
  }
  page.assertNoErrors();
});

test('espace privé : Dessiner et Reprendre confirmés après l\'appui sur « Sortir » ne lisent aucune image privée',
  async () => {
    await enterPile();
    await clear();
    await page.made('zp42 secrete vue');
    await page.pasteImage();                       // saisie non vide : Dessiner et Reprendre demandent confirmation
    await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
    for (const [what, code] of [['Dessiner', `viewerAction('mask')`], ['Reprendre', `viewerAction('resume')`]]) {
      await page.viewPile('zp42 secrete vue');
      await page.eval(`${vBtn(code)}.click()`);
      await page.waitFor(`openedSheet === $('askSheet')`, { what: `confirmation de ${what}` });
      const x = await exitHeld({ noting: true });
      try {
        await page.eval(`$('privExit').click()`);  // (la feuille couvre l'en-tête)
        await waitUntil(() => x.locking(), { what: 'sortie demandée' });
        await page.eval(`answer(true)`);
        await elapse(400);
        assert.deepEqual(x.after, [], `${what} : image privée lue pendant « Sortir »`);
        assert.equal(await page.eval(`inputImages.length`), 1, `${what} : saisie changée pendant « Sortir »`);
        await page.refuseExit(x.h);                // (on reste dans l'espace pour le suivant)
      } finally {
        await x.h.release();
      }
    }
    await page.privateIdle();
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    assert.deepEqual(page.errors.filter(e => !/status of 500/.test(e)), [], 'erreurs de la console');
    page.errors.length = 0;
  });

test('espace privé : pendant « Sortir », les images d\'entrée affichées ne changent pas', async () => {
  await enterPile();
  await clear();
  const ref = color => `(() => { const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d'); g.fillStyle = '${color}'; g.fillRect(0, 0, 64, 64); return c.toDataURL(); })()`;
  const refs = [await page.eval(ref('#a03020')), await page.eval(ref('#2030a0'))];
  await page.launch('zp43 secrete deux', { private: true, mode: 'edit', steps: 2, ref_images: refs });
  await bench.idle({ page });
  await page.eval(`loadPile()`);
  await page.viewPile('zp43 secrete deux');
  await page.eval(`$('vInputs').click()`);
  await page.imageShown('#ivImg', 'première image d\'entrée');
  const shot = () => page.eval(`[ivIndex, $('ivCount').textContent, $('ivImg').getAttribute('src'),
    $('ivDl').getAttribute('href')]`);
  const before = await shot();
  const x = await exitHeld();
  try {
    await page.eval(`$('privExit').click()`);      // (la vue couvre l'en-tête)
    await waitUntil(() => x.locking(), { what: 'sortie demandée' });
    await page.press('ArrowRight');
    await elapse(300);
    assert.deepEqual(await shot(), before, 'image d\'entrée suivante pendant « Sortir »');
  } finally {
    await endExitHeld(x);
  }
  page.assertNoErrors();
});

test('espace privé : pendant « Sortir », la pile n\'est pas redessinée (échec privé arrivé pendant l\'attente)',
  async () => {
    const x = await privateTwo('zp41');
    try {
      await page.topShown();
      await page.eval(`window.cardsBefore = [...$('pile').querySelectorAll('.pcard')]`);
      await page.click('#privExit');
      await waitUntil(() => x.locking(), { what: 'sortie demandée' });
      // une génération privée de la page finie en échec pendant l'attente, comme le dirait finish, puis le dessin
      await page.eval(`pageJobs.push({ id: 'zp41fail', private: true, prompt: 'zp41 secrete echec', doneAt: Date.now(),
        j: { id: 'zp41fail', status: 'failed', error: 'test', private: true } }); renderPile()`);
      assert.deepEqual(await page.eval(`(c => [c.length, c.every((e, k) => e === cardsBefore[k]),
        [...$('pile').querySelectorAll('.pimg img')].filter(i => !i.getAttribute('src')).length])(
        [...$('pile').querySelectorAll('.pcard')])`), [2, true, 0], 'pile redessinée pendant « Sortir »');
    } finally {
      await endExitHeld(x);
    }
    page.assertNoErrors();
  });

test('espace privé : une carte privée en partance quand le Mac ferme l\'espace revient, sans verrou', async () => {
  await enterPile();
  await clear();
  await page.made('zp37 secrete dessus');
  await page.topShown();
  await page.eval(`sorts.length = 0`);
  await page.privateIdle();
  // l'espace fermé par le Mac, sans « Sortir » ; ✕ juste avant que la page l'apprenne : elle l'apprend (l'état lu,
  // appliqué comme le fait refreshStatus) pendant l'envol (0,22 s), vérifié dans la même évaluation
  await page.eval(`postJson('/api/private/lock', {})`);
  assert.deepEqual(await page.eval(`(() => { $('pileNo').click(); const was = flying;
    applyPrivate({ ...privState, unlocked: false }); return [was, flying, !!flight, sortHeld]; })()`),
  [true, false, false, false], 'carte privée en vol, ou verrou de tri tenu');
  await page.eval(`refreshStatus()`);
  await elapse(400);                               // (au-delà de l'envol)
  assert.deepEqual(await page.eval(`[inPrivate(), sorts.length]`), [false, 0], 'tri envoyé');
  page.assertNoErrors();
});

// Verrou de tri qui suit ce que l'œil voit (F4) : SORT_GAP (0,3 s) compté depuis l'affichage de la carte du dessus,
// après un tri comme quand elle est remplacée sans tri d'ici. seenThenNo(prompt) : dans la page, attend que la carte
// du dessus à ce prompt ait son image à l'écran, puis appuie sur ✕ 0,12 s plus tard ; renvoie si un Jeter est parti
const seenThenNo = prompt => page.eval(`(async () => { const t0 = Date.now();
  const img = () => $('pile').querySelector('[data-k="0"] .pimg img');
  while (!(${TOP} === ${JSON.stringify(prompt)} && posed(img()))) {
    if (Date.now() - t0 > 20000) throw new Error('carte du dessus jamais affichée : ' + ${JSON.stringify(prompt)});
    await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
  await new Promise(r => setTimeout(r, 120));      // règle levée : appui 0,12 s après l'affichage, avant SORT_GAP
  $('pileNo').click(); await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
  return !!discarding; })()`);

test('après un tri, ✕ ignoré 0,3 s après l\'affichage de la carte suivante, même arrivée tard', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  let pass = null;                                 // images du dessous retenues jusqu'au tri du dessus
  const h = await page.holdRequests(['*/api/result*', '*/api/thumb*'], p => !(pass && p.request.url.includes(pass)));
  try {
    await page.made('zp44 suivante', { shown: false });
    await page.made('zp44 dessus', { shown: false });
    await page.waitFor(`${TOP} === 'zp44 dessus'`, { what: 'carte du dessus dessinée' });
    pass = encodeURIComponent(await page.eval(`pileItems.find(it => it.prompt === 'zp44 dessus').name`));
    await h.free(u => u.includes(pass));
    await page.topShown();
    await page.eval(`sorts.length = 0`);
    await page.click('#pileYes');                  // le dessus gardé : la suivante dessus, son image retenue
    await page.waitFor(`${TOP} === 'zp44 suivante'`, { what: 'suivante sur le dessus' });
    await elapse(600);                             // (au-delà de SORT_GAP compté depuis le tri)
    const shown = seenThenNo('zp44 suivante');
    await h.release();                             // l'image arrive
    assert.equal(await shown, false, '✕ 0,12 s après l\'affichage de la suivante');
  } finally {
    await h.release();
  }
  await elapse(300);
  await page.click('#pileNo');
  await page.waitFor(`!!discarding`, { what: '✕ une fois la suivante vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('carte du dessus remplacée sans tri d\'ici (nouvelle image) : ✕ ignoré 0,3 s après son affichage', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp45 ancienne');
  await page.topShown();
  await page.eval(`sorts.length = 0`);
  await page.launch('zp45 nouvelle', { steps: 2 });   // (comme depuis un autre appareil)
  const shown = seenThenNo('zp45 nouvelle');
  await bench.idle({ page });
  await page.eval(`refreshStatus()`);
  assert.equal(await shown, false, '✕ 0,12 s après l\'arrivée de la nouvelle carte');
  assert.equal(await page.eval(`sorts.length`), 0);
  await elapse(300);
  await page.click('#pileNo');
  await page.waitFor(`!!discarding && ${TOP} === 'zp45 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

// la carte du dessus masquée par Dessiner (sous 1024 px) : Chrome retire le focus du ✕ qui l'avait, aucune touche
// n'atteint ✓ ni ✕ (le cas que craignait la revue du groupe E n'est pas atteignable ; si Chrome changeait, ce test
// tomberait)
test('carte du dessus masquée par Dessiner : ✕ perd le focus, Entrée ne trie rien', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp46 dessus');
  await page.topShown();
  await page.eval(`sorts.length = 0`);
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'image collée' });
  await page.eval(`$('pileNo').focus()`);
  await page.eval(`$('drawBtn').click()`);
  try {
    await page.waitFor(`drawOn && !shownTop()`, { what: 'carte du dessus masquée par Dessiner' });
    await page.waitFor(`document.activeElement !== $('pileNo')`, { what: '✕ sans le focus' });
    await page.press('Enter');
    await elapse(400);
    assert.deepEqual(await page.eval(`[!!discarding, sorts.length, ${TOP}]`), [false, 0, 'zp46 dessus'],
      'carte masquée triée');
  } finally {
    await page.eval(`drawOn && $('drawBtn').click(); inputImages.length = 0; renderInputs()`);
  }
  await clear();
  page.assertNoErrors();
});

test('visionneuse : après Jeter, Jeter ignoré 0,3 s après l\'affichage de l\'image suivante, même arrivée tard',
  async () => {
    await page.waitFor(`!inPrivate()`, { what: 'espace public' });
    await clear();
    let pass = null;                               // images du dessous retenues jusqu'au Jeter du dessus
    const h = await page.holdRequests(['*/api/result*', '*/api/thumb*'],
      p => !(pass && p.request.url.includes(pass)));
    try {
      await page.made('zp47 suivante', { shown: false });
      await page.made('zp47 dessus', { shown: false });
      await page.waitFor(`${TOP} === 'zp47 dessus'`, { what: 'carte du dessus dessinée' });
      pass = encodeURIComponent(await page.eval(`pileItems.find(it => it.prompt === 'zp47 dessus').name`));
      await h.free(u => u.includes(pass));
      await page.topShown();
      await page.viewPile('zp47 dessus');
      await page.imageShown('#vImg', 'image du dessus en grand');
      await page.eval(`sorts.length = 0; sortFromViewer('discard')`);   // la suivante, son image retenue
      await page.waitFor(`vList.length === 1 && vList[vIndex]?.prompt === 'zp47 suivante'`,
        { what: 'visionneuse sur la suivante' });
      await elapse(600);                           // (au-delà de SORT_GAP compté depuis le Jeter)
      const again = page.eval(`(async () => { const t0 = Date.now();
        while (!posed($('vImg'))) {
          if (Date.now() - t0 > 20000) throw new Error('image suivante jamais affichée');
          await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
        await new Promise(r => setTimeout(r, 120));   // règle levée : Jeter 0,12 s après l'affichage, avant SORT_GAP
        sortFromViewer('discard'); return [vIndex >= 0, sorts.length]; })()`);
      await h.release();                           // l'image arrive
      assert.deepEqual(await again, [true, 0], 'Jeter 0,12 s après l\'affichage de la suivante');
    } finally {
      await h.release();
    }
    await page.waitFor(`!sortHeld`, { what: 'image suivante vue 0,3 s' });
    await page.eval(`sortFromViewer('discard')`);  // vue 0,3 s : Jeter part (le premier Jeter envoyé)
    await page.waitFor(`vIndex < 0 && !!discarding && sorts.length === 1`, { what: 'Jeter une fois vue 0,3 s' });
    await page.closeViewer();
    await page.click('#undoBtn');
    await clear();
    page.assertNoErrors();
  });

test('carte arrivée sous la visionneuse : ✕ ignoré 0,3 s après la fin de son effacement', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp48 ancienne');
  await page.viewPile('zp48 ancienne');
  await page.eval(`sorts.length = 0`);
  await page.launch('zp48 nouvelle', { steps: 2 });   // (comme depuis un autre appareil)
  await bench.idle({ page });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`${TOP} === 'zp48 nouvelle' && posed($('pile').querySelector('[data-k="0"] .pimg img'))`,
    { what: 'nouvelle carte posée sous la visionneuse' });
  await elapse(500);                               // (au-delà de SORT_GAP, sous la visionneuse)
  // ✕ 0,42 s après la fermeture : la visionneuse s'efface encore 0,3 s, la carte n'est vue qu'ensuite
  assert.equal(await page.eval(`(async () => { closeViewer();
    await new Promise(r => setTimeout(r, 420));      // règle levée : ✕ pendant les 0,3 s qui suivent l'effacement
    $('pileNo').click(); await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
    return !!discarding; })()`), false, '✕ 0,42 s après la fermeture de la visionneuse');
  await page.topShown();
  await page.click('#pileNo');
  await page.waitFor(`!!discarding && ${TOP} === 'zp48 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('carte arrivée hors de l\'écran (page défilée) : ✕ ignoré 0,3 s après son retour à l\'écran', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp49 ancienne');
  await page.setView({ ...PHONE, height: 420 });   // (fenêtre basse : le champ déplié repousse la pile hors de l'écran)
  try {
    await page.eval(`sorts.length = 0; openComposer(); scrollTo(0, document.documentElement.scrollHeight)`);
    await page.waitFor(`(r => r.bottom < 0 || r.top > innerHeight)(
      $('pile').querySelector('.pimg').getBoundingClientRect())`,
      { what: 'image de la pile sortie de l\'écran par défilement' });
    await page.launch('zp49 nouvelle', { steps: 2 });   // (comme depuis un autre appareil)
    await bench.idle({ page });
    await page.eval(`refreshStatus()`);
    await page.waitFor(`${TOP} === 'zp49 nouvelle' && posed($('pile').querySelector('[data-k="0"] .pimg img'))`,
      { what: 'nouvelle carte posée hors de l\'écran' });
    await elapse(500);                               // (au-delà de SORT_GAP, hors de l'écran)
    assert.equal(await page.eval(`(async () => { scrollTo(0, 0);
      await new Promise(r => setTimeout(r, 120));   // règle levée : ✕ 0,12 s après le retour à l'écran, avant SORT_GAP
      $('pileNo').click(); await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
      return !!discarding; })()`), false, '✕ 0,12 s après le retour de la carte à l\'écran');
  } finally { await page.setView(PHONE); }
  await page.topShown();
  await page.click('#pileNo');
  await page.waitFor(`!!discarding && ${TOP} === 'zp49 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

// Page cachée (G3) : la page passe derrière un autre onglet, ouvert au premier plan ; behind(during) joue during
// pendant qu'elle est cachée, puis ferme l'onglet : la page revient au premier plan. Le retour est noté dans la page
// (zqBack : instant où elle redevient visible)
async function behind(during) {
  const other = await chrome.phonePage();
  try {
    await page.waitFor(`document.hidden`, { what: 'page cachée derrière l\'autre onglet' });
    await during();
    await page.eval(`(() => { window.zqBack = null; document.addEventListener('visibilitychange',
      () => { if (!document.hidden) zqBack = performance.now(); }, { once: true }); })()`);
  } finally {
    await other.close();
  }
}
// geste act (source évaluée dans la page) 0,12 s après le retour de la page au premier plan ; renvoie le délai réel
// et l'état que rend state (source)
const afterBack = (act, state) => page.eval(`(async () => { const t0 = Date.now();
  while (zqBack == null) {
    if (Date.now() - t0 > 20000) throw new Error('page jamais revenue au premier plan');
    await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant du retour compte
  await new Promise(r => setTimeout(r, Math.max(0, 120 - (performance.now() - zqBack))));   // règle levée
  const late = Math.round(performance.now() - zqBack); ${act};
  await new Promise(r => setTimeout(r, 300));      // règle levée : au-delà de l'envol (0,22 s)
  return [late < SORT_GAP, ${state}]; })()`);

test('carte arrivée page cachée (autre onglet) : ✕ ignoré 0,3 s après le retour de la page', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp52 ancienne');
  await page.topShown();
  await page.eval(`sorts.length = 0`);
  await behind(async () => {
    await page.launch('zp52 nouvelle', { steps: 2 });   // (comme depuis un autre appareil)
    await bench.idle();
    await page.eval(`refreshStatus()`);
    await page.waitFor(`${TOP} === 'zp52 nouvelle' && posed($('pile').querySelector('[data-k="0"] .pimg img'))`,
      { what: 'nouvelle carte posée, page cachée' });
    await elapse(2500);    // au-delà de SORT_GAP, même aux minuteurs ralentis d'une page cachée (une fois par seconde)
    assert.equal(await page.eval(`topHeld`), true, 'carte vue page cachée');
  });
  assert.deepEqual(await afterBack(`$('pileNo').click()`, `!!discarding`), [true, false],
    '✕ 0,12 s après le retour de la page');
  await page.topShown();
  await page.click('#pileNo');
  await page.waitFor(`!!discarding && ${TOP} === 'zp52 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

// page gelée ou en arrière-plan sans qu'aucun relevé du verrou ne tombe pendant l'absence (iOS gèle vite une appli
// quittée) : simulée par un fil de la page bloqué 0,6 s, minuteurs compris ; le premier relevé d'après ne compte pas
// le temps de l'absence
test('carte vue 0,1 s puis page gelée 0,6 s : ✕ ignoré dans les 0,3 s qui suivent la reprise', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp55 ancienne');
  await page.topShown();
  await page.eval(`sorts.length = 0`);
  await page.launch('zp55 nouvelle', { steps: 2 });   // (comme depuis un autre appareil)
  const frozen = page.eval(`(async () => { const t0 = Date.now();
    const img = () => $('pile').querySelector('[data-k="0"] .pimg img');
    while (!(${TOP} === 'zp55 nouvelle' && posed(img()))) {
      if (Date.now() - t0 > 20000) throw new Error('nouvelle carte jamais affichée');
      await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
    await new Promise(r => setTimeout(r, 100));      // règle levée : vue 0,1 s
    for (const end = performance.now() + 600; performance.now() < end;) { /* page gelée */ }
    await new Promise(r => setTimeout(r, 80));       // règle levée : un relevé du verrou après la reprise
    $('pileNo').click(); await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
    return !!discarding; })()`);
  await bench.idle({ page });
  await page.eval(`refreshStatus()`);
  assert.equal(await frozen, false, '✕ 0,08 s après la reprise d\'une page gelée');
  await page.topShown();
  await page.click('#pileNo');
  await page.waitFor(`!!discarding && ${TOP} === 'zp55 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('carte déjà vue avant que la page passe derrière un autre onglet : ✕ la trie dès le retour', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp54 vue');
  await page.topShown();
  await behind(async () => {});
  // décision du porteur du 29/10/2026 (groupe G) : la même carte à l'écran au retour, sans nouveau verrou
  assert.deepEqual(await afterBack(`$('pileNo').click()`, `!!discarding`), [true, true],
    '✕ ignoré au retour sur une carte déjà vue');
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('visionneuse : image passée page cachée (autre onglet), Jeter ignoré 0,3 s après le retour', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp53 a');
  await page.made('zp53 b');
  await page.eval(`sorts.length = 0`);
  await page.viewPile('zp53 b');
  await behind(async () => {
    await page.eval(`stepViewer(1)`);              // (l'image suivante, montrée pendant que la page est cachée)
    await page.waitFor(`vList[vIndex]?.prompt === 'zp53 a' && posed($('vImg'))`,
      { what: 'image suivante posée, page cachée' });
    await elapse(2500);    // au-delà de SORT_GAP, même aux minuteurs ralentis d'une page cachée (une fois par seconde)
    assert.equal(await page.eval(`sortHeld`), true, 'image vue page cachée');
  });
  assert.deepEqual(await afterBack(`sortFromViewer('discard')`, `[vIndex >= 0, sorts.length, !!discarding]`),
    [true, [true, 0, false]], 'Jeter 0,12 s après le retour de la page');
  await page.waitFor(`!sortHeld`, { what: 'image vue 0,3 s' });
  await page.eval(`sortFromViewer('discard')`);
  await page.waitFor(`!!discarding`, { what: 'Jeter une fois vue 0,3 s' });
  await page.closeViewer();
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

// Jeter dans la visionneuse 0,12 s après l'affichage de son image : renvoie [visionneuse ouverte, demandes envoyées,
// Jeter en attente]
const viewerSeenThenNo = () => page.eval(`(async () => { const t0 = Date.now();
  while (!posed($('vImg'))) {
    if (Date.now() - t0 > 20000) throw new Error('image de la visionneuse jamais affichée');
    await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
  await new Promise(r => setTimeout(r, 120));      // règle levée : Jeter 0,12 s après l'affichage, avant SORT_GAP
  sortFromViewer('discard'); return [vIndex >= 0, sorts.length, !!discarding]; })()`);

test('visionneuse : Jeter ignoré dans les 0,3 s qui suivent l\'ouverture ou un pas (← →)', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await clear();
  await page.made('zp50 a');
  await page.made('zp50 b');
  await page.eval(`sorts.length = 0`);
  await page.viewPile('zp50 b', { seen: false });
  assert.deepEqual(await viewerSeenThenNo(), [true, 0, false], 'Jeter 0,12 s après l\'ouverture');
  await page.waitFor(`!sortHeld`, { what: 'image vue 0,3 s' });
  await page.eval(`stepViewer(1)`);
  assert.deepEqual(await viewerSeenThenNo(), [true, 0, false], 'Jeter 0,12 s après un pas');
  assert.equal(await page.eval(`vList[vIndex].prompt`), 'zp50 a');
  await page.waitFor(`!sortHeld`, { what: 'image vue 0,3 s' });
  await page.eval(`sortFromViewer('discard')`);    // vue 0,3 s : Jeter part au bandeau
  await page.waitFor(`!!discarding`, { what: 'Jeter une fois vue 0,3 s' });
  await page.closeViewer();
  await page.click('#undoBtn');
  await clear();
  page.assertNoErrors();
});

test('espace privé : « Sortir » refusé, l\'image de la pile ouverte en grand reprend son verrou court', async () => {
  await enterPile();
  await clear();
  await page.made('zp51 secrete vue');
  await page.viewPile('zp51 secrete vue');
  const x = await exitHeld();
  try {
    await page.eval(`$('privExit').click()`);      // (la visionneuse couvre l'en-tête)
    await page.refuseExit(x.h);
    assert.equal(await page.eval(`sortHeld`), true, 'Garder et Jeter permis aussitôt après le refus');
  } finally {
    await x.h.release();
  }
  await page.waitFor(`!sortHeld`, { what: 'image vue 0,3 s' });
  await page.closeViewer();
  await page.privateIdle();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.deepEqual(page.errors.filter(e => !/status of 500/.test(e)), [], 'erreurs de la console');
  page.errors.length = 0;
});
