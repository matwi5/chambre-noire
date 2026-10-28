// Étanchéité de l'espace privé, dans la vue du téléphone : après un parcours privé complet (pile et son Jeter en
// attente, Tirages, visionneuse, images d'entrée, lot, Labo et sa file, prompts enregistrés, saisie, suppression),
// puis la sortie par « Sortir » ou par la fermeture que décide le Mac, rien de privé ne reste dans la page : ni dans
// le HTML (attributs et textes cachés compris), ni dans les champs, ni dans la mémoire de la page (toutes ses
// variables globales et leur contenu : listes d'images, générations suivies, images prêtes, prompts, file…), ni dans
// localStorage (page.leaks du pilote). La recherche porte sur des marqueurs : identifiants des images, des générations
// et des lots privés, mots des prompts privés, routes /api/private/ et noms prive_….
// Les deux premiers tests se suivent : le second rouvre l'espace et les Tirages que le premier a remplis. Le
// troisième sort de l'espace pendant qu'un aperçu privé est révélé sur le canevas de la carte en cours, que
// page.leaks ne fouille pas : il en lit les pixels. Les deux derniers simulent le retour par « Retour » sur une page
// fermée dans l'espace (pageshow persisted) : affichage et saisie privés effacés, espace reverrouillé avant tout état
// lu, même si le Mac ne répond pas d'abord. Les suivants : effacement dès la fermeture (pagehide), champs de code
// compris ; page rechargée après une fermeture dans l'espace dont le verrouillage s'est perdu (marque de l'onglet,
// sessionStorage) ; code retapé pendant un reverrouillage en route, ou après un reverrouillage sans réponse ; mémoire
// de l'onglet refusée ; code d'accès redemandé dans l'espace (le verrouillage passe sans lui ; un 401 ne vaut pas
// verrouillé).
//   venv/bin/python tests/check.py --quick --ui tests/ui/etancheite.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse } from './driver.mjs';

let bench, chrome, page, kept;                     // kept : images privées que le premier test laisse
let navigated = false;                             // nouveau document chargé (Page.frameNavigated)

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  page.on('Page.frameNavigated', p => { if (!p.frame.parentId) navigated = true; });
  await page.goto(bench.url + '/');
  await page.ready();
});

after(async () => {
  bench?.release('etanche');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const post = (url, body) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
const ref = `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '#a03070'; x.fillRect(0, 0, 256, 256);
  return c.toDataURL('image/png'); })()`;
const generate = extra => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 2, cfg: 1, seed: -1,
  preview: false, ref_images: [], private: true, ...${extra} }).then(r => r.status)`);
// mots des prompts privés : chacun n'apparaît que dans l'espace privé
const WORDS = ['zqE0pile', 'zqE1edition', 'zqE2lot', 'zqE3resultat', 'zqE4file', 'zqE5titre', 'zqE5texte',
  'zqE6saisie', 'zqE7supprimee', 'zqE8vignette', 'zqE9saisie'];

const enter = () => page.enterPrivate(CODE);

// parcours privé : tout ce qui affiche une donnée privée est ouvert au moins une fois ; renvoie les marqueurs
async function privateTour() {
  assert.equal(await generate(`{ mode: 'edit', prompt: 'zqE1edition', ref_images: [${ref}] }`), 202);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE2lot', count: 2 }`), 202);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE7supprimee' }`), 202);
  await bench.idle();
  // une génération de la page jusqu'à la pile du Labo ; toutes gardées par ✓ (Tirages privés), sauf une dernière,
  // ouverte en grand puis laissée dans la pile ; puis une autre gardée en file
  await page.typePrompt('zqE3resultat');
  await page.click('#go');
  await page.waitFor(`pileItems.length === 5 && (img => img && img.complete && img.naturalWidth > 0)
    ($('pile').querySelector('[data-k="0"] img'))`, { what: 'images privées dans la pile', timeout: 30000 });
  assert.equal(await page.keepPile(), 5);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE0pile' }`), 202);
  await page.waitFor(`pileItems.length === 1 && (img => img && img.complete && img.naturalWidth > 0)
    ($('pile').querySelector('[data-k="0"] img'))`, { what: 'image privée dans la pile', timeout: 30000 });
  await page.topShown();                           // (vue 0,3 s : ✕ la jette plus bas, sous la visionneuse)
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('vImg').complete && $('vImg').naturalWidth > 0`, { what: 'image de la pile en grand' });
  await page.eval(`closeViewer()`);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'HOLD=etanche zqE4file' }`), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pageJobs.some(p => p.private && p.adopted)`, { what: 'génération privée suivie en file' });
  // une édition de la page en file derrière elle : sa carte porte la vignette de son image d'entrée (data:)
  await page.eval(`(async () => { const c = document.createElement('canvas'); c.width = c.height = 200;
    const x = c.getContext('2d'); x.fillStyle = '#5040c0'; x.fillRect(0, 0, 200, 200); x.fillStyle = '#e0b030';
    x.fillRect(40, 60, 90, 30); inputImages.push(await toEntry('zqE8.png', c.toDataURL('image/png')));
    renderInputs(); })()`);
  await page.typePrompt('zqE8vignette');
  await page.click('#go');
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('queueChip').hidden`, { what: 'pastille de la file' });
  await page.click('#queueChip');                  // la file dans sa feuille
  await page.waitFor(`!!$('queueList').querySelector('.qcard.own img[src^="data:"]')
    && $('queueList').textContent.includes('zqE8vignette')`, { what: 'carte privée avec sa vignette d\'entrée' });
  const thumb = await page.eval(`$('queueList').querySelector('.qcard.own img').getAttribute('src')`);
  await page.eval(`closeSheet()`);
  await page.typePrompt('zqE6saisie');             // saisie privée laissée en place : texte et image d'entrée
  await page.eval(`(async () => { inputImages.push(await toEntry('zqE9saisie.png', ${ref})); renderInputs(); })()`);
  // prompts enregistrés de l'espace
  assert.equal(await post('/api/private/prompts', { title: 'zqE5titre', text: 'zqE5texte', usage: 't2i' }), 200);
  await page.eval(`openPrompts()`);
  await page.waitFor(`$('promptSheet').textContent.includes('zqE5titre')`, { what: 'prompt privé affiché' });
  await page.eval(`closeSheet()`);
  // galerie, suppression d'une image, visionneuse, images d'entrée, feuille du lot
  await page.tab('tirages');
  await page.waitFor(`histItems.length === 5 && histItems.every(it => it.private)`, { what: 'galerie privée' });
  await page.eval(`(() => { openViewer(histItems.findIndex(it => it.prompt === 'zqE7supprimee'), histItems);
    viewerAction('delete'); })()`);                // sans attendre la fin : elle attend la confirmation
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de suppression' });
  await page.eval(`answer(true)`);
  await page.waitFor(`histItems.length === 4`, { what: 'image privée supprimée' });
  const markers = await page.eval(`[...histItems.map(it => it.id), ...pageJobs.filter(p => p.private).map(p => p.id),
    ...histItems.filter(it => it.lot).map(it => it.lot.id), ...pileItems.map(it => it.id)]`);
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0)`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  await page.eval(`closeInputs(); openViewer(histItems.findIndex(it => it.lot), histItems); openLot()`);
  await page.waitFor(`openedSheet === $('lotSheet')`, { what: 'feuille du lot privé' });
  await page.tab('labo', { force: true });         // (visionneuse et feuille du lot ouvertes : pas au doigt)
  // un Jeter privé qui attend la fin de son bandeau à la sortie (sous la visionneuse : pas au doigt)
  await page.click('#pileNo', { force: true });
  await page.waitFor(`!!discarding && !$('undoBar').hidden`, { what: 'Jeter privé en attente' });
  return [...new Set([...markers, ...WORDS, '/api/private/', 'prive_', thumb.slice(-120, -40)])];
}

// marqueurs trouvés dans la page (aside : la saisie privée mise de côté, asideInput, compte ; imgsSeen, les images
// que retient watchImages, ci-dessous, ne compte pas : sans lui, celles qui ne sont plus nommées seraient libérées)
const scan = (markers, aside) => page.leaks(markers, { skip: aside ? ['imgsSeen'] : ['asideInput', 'imgsSeen'] });
// toute image de la page retenue dans imgsSeen à partir de l'appel, dès qu'elle est insérée (notée aussi dans
// imgsShown) ou reçoit une adresse : attachée, détachée par un contenu remplacé (que page.leaks ne voit plus : plus
// rien ne la nomme), ou jamais attachée (Image() de ready) ; l'espion n'est posé qu'une fois par page
const watchImages = () => page.eval(`(() => { window.imgsSeen = new Set(); window.imgsShown = new WeakSet();
  const note = n => { if (n.nodeType !== 1) return; const all = n.tagName === 'IMG' ? [n] : n.querySelectorAll('img');
    all.forEach(i => { imgsSeen.add(i); imgsShown.add(i); }); };
  document.querySelectorAll('img').forEach(note);
  if (window.imgsWatched) return; window.imgsWatched = true;
  const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', { configurable: true, get: d.get,
    set(v) { imgsSeen.add(this); d.set.call(this, v); } });
  new MutationObserver(rs => rs.forEach(r => r.addedNodes.forEach(n => note(n))))
    .observe(document.documentElement, { childList: true, subtree: true }); })()`);
// adresses privées que ces images gardent encore : routes privées, aperçus /api/job/, et data URL d'une image passée
// à l'écran (vignettes de la saisie et de la file) : toute génération et toute saisie de ces tests est privée ; all
// faux : seulement les images retirées de l'écran (détachées, ni prêtes dans ready), les seules qui ne doivent plus en
// avoir tant que l'espace reste ouvert (début de l'adresse seulement)
const privateLeft = all => page.eval(`(() => { const held = new Set([...ready.values()].map(e => e.el));
  return [...imgsSeen].filter(i => ${all} || !i.isConnected && !held.has(i))
    .filter(i => (s => /\\/api\\/(private|job)\\//.test(s) || s.startsWith('data:') && imgsShown.has(i))(
      i.getAttribute('src') || '')).map(i => i.getAttribute('src').slice(0, 60)); })()`);

test('« Sortir » : plus rien de l\'espace privé dans la page', async () => {
  await enter();
  await watchImages();
  const markers = await privateTour();
  kept = await page.eval(`histItems.length`);
  // images chargées en avance évincées de ready par d'autres (publiques) : elles quittent aussi leur adresse
  await page.eval(`for (let i = 0; i < READY_MAX + 2; i++) preload('/logo.svg?e=' + i)`);
  await page.waitFor(`secretLoads.size === 0`, { what: 'chargements privés réglés' });
  assert.deepEqual(await privateLeft(false), [], 'image retirée de l\'écran qui garde une adresse privée');
  await page.click('#privExit', { force: true });  // visionneuse et feuille du lot ouvertes exprès : pas au doigt
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await scan(markers, true), [], 'données privées restées dans la page');
  assert.deepEqual(await privateLeft(true), [], 'image (détachée comprise) qui garde une adresse privée');
  assert.equal(await page.eval(`$('undoBar').hidden`), true, 'bandeau du Jeter privé resté');
  page.assertNoErrors();
});

test('fermeture par le Mac : plus rien de l\'espace privé dans la page (hors saisie mise de côté)', async () => {
  await enter();
  await page.tab('tirages');
  await page.waitFor(`histItems.length === ${kept} && histItems.every(it => it.private)`, { what: 'galerie privée' });
  const markers = [...new Set([...await page.eval(`histItems.map(it => it.id)`), ...WORDS, '/api/private/', 'prive_'])];
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0); openPrompts()`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  // session close par le serveur, sans « Sortir » : la page l'apprend à son interrogation suivante
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé' });
  // visionneuse et images d'entrée ouvertes sur une image privée : fermer les images d'entrée recalcule la barre d'état
  // pendant que la visionneuse montre encore l'image privée ; le cache tints ne doit pas garder son adresse
  assert.deepEqual(await scan(markers, false), [], 'données privées restées dans la page');
  bench.release('etanche');
  await bench.idle();
  page.assertNoErrors();
});

test('« Sortir » pendant la révélation d\'une génération privée : son canevas est vidé', async () => {
  await enter();
  await page.tab('labo');
  await page.eval(`$('previewChk').checked = true; opt.steps = 'high'; saveOpt(); refreshChoices()`);
  await watchImages();
  await page.typePrompt('SLOW=0.4 zqE10revelee');
  await page.click('#go');
  // (deux aperçus au moins : le premier remplacé par le second sur la mosaïque)
  await page.waitFor(`shown && shown.private && !!reveal.img && reveal.pv >= 2`,
    { what: 'aperçus privés en mosaïque', timeout: 30000 });
  assert.ok((await page.canvasInk('#revealCanvas')).ink > 0, 'mosaïque dessinée');
  // /api/status retenu : une réponse demandée dans l'espace (qui le dit encore ouvert) n'arrive qu'après « Sortir »,
  // et les suivantes pas avant la fin des vérifications : la page ne montre que ce qu'elle sait de l'espace public
  await page.holdFetch(`u => u === '/api/status'`);
  await page.eval(`void (window.lateStatus = refreshStatus())`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.canvasInk('#revealCanvas'), { width: 0, height: 0, ink: 0 }, 'aperçu privé resté');
  // l'aperçu lâché par la mosaïque (remplacé, ou à la sortie) ne garde pas son adresse, même détaché
  assert.deepEqual(await privateLeft(true), [], 'aperçu privé (détaché compris) qui garde son adresse');
  assert.deepEqual(await page.eval(`[reveal.img, $('runCard').hidden, $('queueChip').hidden, queueState.length]`),
    [null, true, true, 0], 'génération ou file privée à l\'écran');
  assert.deepEqual(await scan(['zqE10revelee'], true), [], 'données privées restées dans la page');
  await page.releaseFetch();
  await page.eval(`lateStatus`);   // la réponse d'avant la sortie, puis une nouvelle
  assert.equal(await page.eval(`inPrivate()`), false, 'réponse d\'avant la sortie : l\'espace rouvert dans la page');
  assert.deepEqual(await scan(['zqE10revelee'], true), [], 'données privées revenues dans la page');
  await bench.idle();
  page.assertNoErrors();
});

// le Mac fait échouer les requêtes retenues r (holdRequests) : chargement constaté en échec par la page
const failAll = async rs => { for (const { requestId } of rs) await page.send('Fetch.failRequest',
  { requestId, errorReason: 'Failed' }).catch(() => {}); };

test('espace privé : image évincée pendant son chargement, image illisible, vignette en échec retirée : vidées',
  async () => {
    await enter();
    await page.tab('tirages');
    await page.waitFor(`histItems.length >= 2 && histItems.every(it => it.private)`, { what: 'galerie privée' });
    await watchImages();
    const [a, b] = await page.eval(`histItems.slice(0, 2).map(it => it.id)`);
    const h = await page.holdRequests(['*/api/private/image*'], () => true);   // images complètes retenues
    try {
      // a chargée en avance, puis évincée de ready par d'autres (publiques) pendant son chargement ; b ensuite,
      // illisible
      await page.eval(`preload(srcOf(histItems[0]))`);
      await waitUntil(() => h.held.some(r => r.url.includes(a)), { what: 'image a demandée' });
      await page.eval(`for (let i = 0; i < READY_MAX + 2; i++) preload('/logo.svg?f=' + i);
        preload(srcOf(histItems[1]))`);
      await waitUntil(() => h.held.some(r => r.url.includes(b)), { what: 'image b demandée' });
      await h.free(u => u.includes(a));
      await failAll(h.take(u => u.includes(b)));
      await page.waitFor(`secretLoads.size === 0`, { what: 'chargements privés réglés' });
      assert.deepEqual(await privateLeft(false), [], 'image évincée ou illisible qui garde son adresse');
    } finally {
      await h.release();
    }
    // vignette des Tirages en échec, puis la grille redessinée avant sa seconde tentative (0,7 s plus tard)
    const t = await page.holdRequests(['*/api/private/thumb*'], () => true);
    try {
      await page.eval(`histShown = ''; renderGallery()`);
      await waitUntil(() => t.held.length > 0, { what: 'vignette demandée' });
      await failAll(t.take());
      await page.waitFor(`[...$('histGrid').querySelectorAll('img')].some(i => i.dataset.retry)`,
        { what: 'seconde tentative prévue' });
      await page.eval(`histShown = ''; renderGallery()`);   // les vignettes en échec retirées de la grille
      await elapse(900);
      assert.deepEqual(await privateLeft(false), [], 'vignette retirée qui reprend son adresse');
    } finally {
      await t.release();
    }
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_FAILED|ERR_ABORTED/.test(e)));
    page.assertNoErrors();
  });

// page restaurée depuis la mémoire du navigateur (« Retour », bfcache) : Chrome sans écran ne la rejoue pas de façon
// fiable, l'événement pageshow (persisted) est simulé ; le verrouillage de la fermeture (pagehide) n'a pas eu lieu,
// comme quand il se perd : c'est le reverrouillage du retour qui ferme l'espace
const restored = `dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))`;
// espace ouvert, une image privée dans la pile affichée et une saisie privée ; renvoie les marqueurs privés
async function privateScreen(word) {
  await enter();
  await page.tab('labo');
  assert.equal(await generate(`{ mode: 't2i', prompt: '${word}pile' }`), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pileItems.some(it => it.prompt === '${word}pile') && (img => img && img.complete
    && img.naturalWidth > 0)($('pile').querySelector('[data-k="0"] img'))`, { what: 'image privée dans la pile',
    timeout: 30000 });
  await page.typePrompt(`${word}saisie`);
  const ids = await page.eval(`pileItems.map(it => it.id)`);
  return [...ids, `${word}pile`, `${word}saisie`, '/api/private/', 'prive_'];
}

test('« Retour » vers une page de l\'espace privé : affichage et saisie privés effacés, espace reverrouillé',
  async () => {
  const markers = await privateScreen('zqE11');
  // dès l'événement, avant toute réponse du Mac : plus rien de l'espace à l'écran, et le champ (qui avait le curseur)
  // l'a perdu : les touches suivantes n'iraient pas dans la saisie publique sans qu'on le voie
  await page.eval(`openComposer(); $('prompt').focus()`);
  await page.waitFor(`document.activeElement === $('prompt')`, { what: 'curseur dans le champ privé' });
  assert.deepEqual(await page.eval(`(() => { ${restored}; return [inPrivate(),
    document.documentElement.classList.contains('priv'), pileItems.length, $('prompt').value,
    document.activeElement === $('prompt')]; })()`), [false, false, 0, '', false]);
  assert.equal(await page.eval(`$('toastBox').textContent`), 'Espace privé verrouillé à la fermeture de la page');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.private.unlocked)`,
    { what: 'espace reverrouillé sur le Mac' });
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`inPrivate()`), false);
  assert.deepEqual(await scan(markers, true), [], 'données privées restées dans la page (saisie comprise)');
  page.assertNoErrors();
});

test('« Retour », Mac injoignable au reverrouillage : la page ne rentre pas dans l\'espace resté ouvert', async () => {
  await privateScreen('zqE12');
  // le verrouillage n'arrive pas au Mac : sa session reste ouverte tant que la page ne l'a pas fermée
  await page.eval(`(() => { const f = window.zqFetch = window.fetch; window.zqLocks = 0;
    window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? (zqLocks++, Promise.reject(new TypeError('coupé')))
      : f(u, ...a); })()`);
  await page.eval(restored);
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.unlocked)`), true,
    'session du Mac encore ouverte');
  assert.deepEqual(await page.eval(`[inPrivate(), pileItems.length, $('lamp').classList.contains('err')]`),
    [false, 0, true], 'page rentrée dans l\'espace sans code');
  // refermée avant que le Mac ait accepté le verrouillage : elle le renvoie, comme une page fermée dans l'espace
  const sent = await page.eval(`zqLocks`);
  await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))`);
  assert.equal(await page.eval(`zqLocks`), sent + 1, 'verrouillage renvoyé à la fermeture');
  // de retour sur la page, le Mac répond de nouveau et le code privé est retapé : l'espace s'ouvre, sans être
  // refermé par le reverrouillage
  await page.eval(`window.fetch = zqFetch`);
  await page.eval(restored);
  await page.eval(`($('puCode').value = ${JSON.stringify(CODE)}, privUnlock())`);
  assert.equal(await page.eval(`inPrivate()`), true, 'espace rouvert par le code');
  assert.equal(await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.unlocked)`), true);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  await bench.idle();
  page.assertNoErrors();
});

test('« Retour » vers une page fermée hors de l\'espace : la saisie privée mise de côté est oubliée', async () => {
  await enter();
  await page.typePrompt('zqE13aside');
  // fermeture par le Mac (15 minutes) : la saisie privée reste en mémoire de la page pour le retour dans l'espace
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé par le Mac' });
  assert.notDeepEqual(await scan(['zqE13aside'], true), [], 'saisie privée mise de côté (prémisse)');
  await page.eval(`${restored}; refreshStatus()`);
  assert.deepEqual(await scan(['zqE13aside'], true), [], 'saisie privée restée en mémoire après le retour');
  page.assertNoErrors();
});

// champs de code des feuilles privées, tels que la page les désigne (PRIV_CODES : ceux qu'elle vide)
const fields = `[...document.querySelectorAll(PRIV_CODES)]`;
const fillCodes = value => page.eval(`${fields}.forEach(i => i.value = ${JSON.stringify(value)})`);
const codes = `${fields}.map(i => i.value).join('')`;
const MARK = `(() => { try { return sessionStorage.getItem(RELOCK_MARK); } catch (e) { return 'refusé'; } })()`;
const macUnlocked = () => page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.unlocked)`);
const isLock = p => p.request.url.includes('/api/private/lock');

test('fermeture de la page dans l\'espace privé : tout est effacé dès pagehide, champs de code compris', async () => {
  const markers = await privateScreen('zqE14');
  // (les champs désignés comprennent ceux de l'entrée et de la création)
  assert.equal(await page.eval(`$('puCode').matches(PRIV_CODES) && $('pcCode').matches(PRIV_CODES)`), true);
  await fillCodes('zqE14code');
  // dès l'événement de fermeture (page gardée pour un « Retour ») : même effacement que « Sortir »
  assert.deepEqual(await page.eval(`(() => { dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    return [inPrivate(), document.documentElement.classList.contains('priv'), pileItems.length, $('prompt').value,
      ${codes}]; })()`), [false, false, 0, '', ''], 'affichage, saisie ou code privés gardés à la fermeture');
  assert.deepEqual(await scan([...markers, 'zqE14code'], true), [], 'données privées restées dans la page fermée');
  assert.equal(await page.eval(MARK), '1', 'marque de l\'onglet posée');
  // « Retour » : champ de code rempli entre-temps (restauré par le navigateur), vidé ; message, reverrouillage
  await fillCodes('zqE14code');
  await page.eval(restored);
  assert.equal(await page.eval(codes), '', 'champ de code restauré');
  assert.equal(await page.eval(`$('toastBox').textContent`), 'Espace privé verrouillé à la fermeture de la page');
  await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
  assert.equal(await macUnlocked(), false);
  assert.equal(await page.eval(MARK), null, 'marque effacée une fois le verrouillage accepté');
  page.assertNoErrors();
});

test('page rechargée après une fermeture dans l\'espace, verrouillage perdu : reverrouillée avant tout état',
  async () => {
    await privateScreen('zqE15');
    // le verrouillage de la fermeture n'arrive pas au Mac (réseau coupé) : sa session reste ouverte
    await page.eval(`(() => { const f = window.fetch;
      window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? Promise.reject(new TypeError('coupé'))
        : f(u, ...a); })()`);
    // verrouillage retenu ; toute autre requête privée ou de l'état (/api/status) du nouveau document est notée
    const seen = [];
    const h = await page.holdRequests(['*/api/private/*', '*/api/status'],
      p => isLock(p) || (navigated && seen.push(p.request.url), false));
    try {
      navigated = false;
      await page.goto(bench.url + '/');            // rechargement : nouvelle page, même onglet
      await waitUntil(async () => h.held.length > 0 || await page.eval(`inPrivate()`),
        { what: 'reverrouillage demandé, ou page dans l\'espace' });
      assert.deepEqual(await page.eval(`[inPrivate(), relock, ${MARK}]`), [false, true, '1'],
        'page rentrée dans l\'espace sans code, ou marque perdue');
      assert.deepEqual(seen, [], 'état demandé avant le reverrouillage');
      assert.equal(await macUnlocked(), true, 'session du Mac encore ouverte (prémisse)');
    } finally {
      await h.release();
    }
    await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
    assert.equal(await macUnlocked(), false);
    assert.deepEqual(await page.eval(`[inPrivate(), ${MARK}]`), [false, null]);
    page.assertNoErrors();
  });

test('reverrouillage en route quand le code privé est retapé : l\'entrée l\'attend, l\'espace reste ouvert',
  async () => {
    await privateScreen('zqE16');
    // ordre vu par la page : réponse du verrouillage (« verrou »), envoi du code (« code »)
    await page.eval(`(() => { const f = window.zqFetch = window.fetch; window.zqOrder = [];
      window.fetch = (u, ...a) => { const k = String(u); if (k === '/api/private/unlock') zqOrder.push('code');
        const r = f(u, ...a); if (k === '/api/private/lock') r.then(() => zqOrder.push('verrou'), () => {});
        return r; }; })()`);
    const h = await page.holdRequests(['*/api/private/lock'], () => true);
    try {
      await page.eval(restored);                   // « Retour » : reverrouillage envoyé, sa réponse se fait attendre
      await waitUntil(() => h.held.length > 0, { what: 'reverrouillage envoyé' });
      await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
    } finally {
      await h.release();                           // le Mac accepte le verrouillage ; l'entrée va jusqu'au bout
    }
    await page.eval(`zqEntry`);
    await page.eval(`window.fetch = zqFetch`);
    assert.deepEqual(await page.eval(`zqOrder.slice(0, 2)`), ['verrou', 'code'],
      'code envoyé avant la fin du reverrouillage');
    assert.deepEqual(await page.eval(`[inPrivate(), relock]`), [true, false], 'espace refermé par le reverrouillage');
    assert.equal(await macUnlocked(), true);
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'sorti' });
    await bench.idle();
    page.assertNoErrors();
  });

test('reverrouillage sans réponse, code retapé : aucun verrouillage ne part pendant l\'entrée', async () => {
  await privateScreen('zqE17');
  // le Mac ne reçoit aucun verrouillage (réseau coupé pour lui seul) : relock reste vrai
  await page.eval(`(() => { const f = window.zqFetch = window.fetch; window.zqLocks = 0;
    window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? (zqLocks++, Promise.reject(new TypeError('coupé')))
      : f(u, ...a); })()`);
  await page.eval(restored);
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`relock`), true, 'reverrouillage pas accepté (prémisse)');
  // le code part (sa réponse retenue) ; une interrogation de l'état tombe pendant l'aller-retour
  const h = await page.holdRequests(['*/api/private/unlock'], () => true);
  try {
    await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
    await waitUntil(() => h.held.length > 0, { what: 'code envoyé' });
    const sent = await page.eval(`zqLocks`);
    await page.eval(`refreshStatus()`);
    assert.equal(await page.eval(`zqLocks`), sent, 'verrouillage lancé pendant l\'entrée');
  } finally {
    await h.release();
  }
  await page.eval(`zqEntry`);
  await page.eval(`window.fetch = zqFetch`);
  assert.deepEqual(await page.eval(`[inPrivate(), relock]`), [true, false], 'espace ouvert par le code');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  await bench.idle();
  page.assertNoErrors();
});

test('mémoire de l\'onglet refusée par le navigateur : la page se charge et fonctionne comme sans marque', async () => {
  const { identifier } = await page.send('Page.addScriptToEvaluateOnNewDocument', { source: `Object.defineProperty(
    window, 'sessionStorage', { get() { throw new DOMException('refusé', 'SecurityError'); } })` });
  try {
    await page.goto(bench.url + '/');
    await page.ready();
    assert.equal(await page.eval(`relock`), false);
    await enter();
    await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))`);
    await page.eval(restored);
    await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
    assert.equal(await page.eval(`inPrivate()`), false);
  } finally {
    await page.send('Page.removeScriptToEvaluateOnNewDocument', { identifier });
  }
  page.assertNoErrors();
});

// appels de fetch de la page notés (zqCalls : adresses) ; verrouillages comptés (zqLocks) ; zqDone : réponse du code
// reçue ; zqAfter : interrogations de l'état parties après elle
const watchFetch = () => page.eval(`(() => { const f = window.zqFetch = window.fetch;
  Object.assign(window, { zqCalls: [], zqLocks: 0, zqDone: false, zqAfter: 0 });
  window.fetch = (u, ...a) => { const k = String(u); zqCalls.push(k);
    if (k === '/api/private/lock') zqLocks++;
    if (k === '/api/status' && zqDone) zqAfter++;
    const r = f(u, ...a); if (k === '/api/private/unlock') r.then(() => { zqDone = true; }, () => {});
    return r; }; })()`);
const hide = `dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))`;
// « Retour » sur la page fermée : reverrouillage accepté, espace fermé sur le Mac, marque effacée
async function backLocked() {
  await page.eval(`window.fetch = zqFetch`);
  await page.eval(restored);
  await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
  assert.equal(await macUnlocked(), false, 'espace encore ouvert sur le Mac');
  assert.equal(await page.eval(MARK), null);
}

test('page fermée juste après l\'acceptation du code, état pas encore relu : verrouillée, marque posée', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
  await watchFetch();
  const h = await page.holdRequests(['*/api/status'], () => true);   // l'état relu se fait attendre
  try {
    await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
    await page.waitFor(`zqDone && zqAfter > 0`, { what: 'code accepté, état demandé' });
    assert.equal(await page.eval(`inPrivate()`), false, 'état pas encore relu (prémisse)');
    const sent = await page.eval(`zqLocks`);
    await page.eval(hide);
    assert.deepEqual(await page.eval(`[zqLocks - ${sent}, relock, ${MARK}]`), [1, true, '1'],
      'fermeture sans verrouillage ni marque');
  } finally {
    await h.release();
  }
  await page.eval(`zqEntry`);
  await backLocked();
  page.assertNoErrors();
});

test('page fermée pendant l\'envoi du code : verrouillée, code annulé, aucune session ouverte après la fermeture',
  async () => {
    await page.goto(bench.url + '/');
    await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
    await watchFetch();
    const h = await page.holdRequests(['*/api/private/unlock'], () => true);
    try {
      await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
      await waitUntil(() => h.held.length > 0, { what: 'code envoyé' });
      const sent = await page.eval(`zqLocks`);
      await page.eval(hide);
      assert.deepEqual(await page.eval(`[zqLocks - ${sent}, relock, ${MARK}]`), [1, true, '1'],
        'fermeture sans verrouillage ni marque');
    } finally {
      await h.release();                           // le code retenu part, s'il n'a pas été annulé à la fermeture
    }
    await page.eval(`zqEntry`);
    assert.equal(await page.eval(`inPrivate()`), false, 'entrée réussie après la fermeture');
    assert.equal(await macUnlocked(), false, 'session ouverte sur le Mac par un code parti avant la fermeture');
    assert.deepEqual(await page.eval(`[relock, ${MARK}]`), [true, '1'], 'marque levée après la fermeture');
    await backLocked();
    page.assertNoErrors();
  });

test('rechargement avec marque, premier reverrouillage perdu : les générations de ce navigateur reviennent ensuite',
  async () => {
    await page.goto(bench.url + '/');
    await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête' });
    await page.generate('HOLD=zqE18 zqE18 publique en cours');
    const own = await page.eval(`pageJobs.at(-1).id`);
    await enter();
    // le verrouillage de la fermeture se perd, puis le premier reverrouillage de la page rechargée aussi
    await page.eval(`(() => { const f = window.fetch;
      window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? Promise.reject(new TypeError('coupé'))
        : f(u, ...a); })()`);
    let first = true;
    const h = await page.holdRequests(['*/api/private/lock'], p => isLock(p) && first);
    try {
      await page.goto(bench.url + '/');
      await waitUntil(() => h.held.length > 0, { what: 'premier reverrouillage' });
      first = false;
      for (const r of h.take()) await page.send('Fetch.failRequest', { requestId: r.requestId,
        errorReason: 'ConnectionRefused' });
      await page.waitFor(`!relock`, { what: 'reverrouillage suivant accepté', timeout: 30000 });
      await page.waitFor(`pageJobs.some(p => p.id === ${JSON.stringify(own)})`,
        { what: 'génération publique de ce navigateur reprise' });
    } finally {
      await h.release();
      bench.release('zqE18');
      await bench.idle();
    }
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_CONNECTION_REFUSED/.test(e)));
    page.assertNoErrors();
  });

test('fermeture dans l\'espace : aucune relecture publique au moment de pagehide, refaite au retour', async () => {
  await privateScreen('zqE19');
  await page.tab('tirages');
  await watchFetch();
  await page.eval(hide);
  const reads = `zqCalls.filter(u => u === '/api/pile' || u.startsWith('/api/history') || u.startsWith('/api/job/'))`;
  assert.deepEqual(await page.eval(reads), [], 'relecture publique lancée à la fermeture');
  await page.eval(restored);
  await page.waitFor(`!relock && zqCalls.includes('/api/pile') && zqCalls.some(u => u.startsWith('/api/history'))`,
    { what: 'pile et Tirages publics relus au retour' });
  await page.eval(`window.fetch = zqFetch`);
  await page.tab('labo');
  page.assertNoErrors();
});

test('marque posée dès l\'entrée : onglet tué sans pagehide puis rechargé, reverrouillé avant tout état ; levée par '
  + '« Sortir » et par la fermeture du Mac', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
  await enter();
  assert.equal(await page.eval(MARK), '1', 'marque posée à l\'entrée');
  // l'onglet est tué en arrière-plan : ni pagehide ni verrouillage (écouteur de la page court-circuité)
  await page.eval(`addEventListener('pagehide', e => e.stopImmediatePropagation(), true)`);
  const seen = [];
  const h = await page.holdRequests(['*/api/private/*', '*/api/status'],
    p => isLock(p) || (navigated && seen.push(p.request.url), false));
  try {
    navigated = false;
    await page.goto(bench.url + '/');
    await waitUntil(async () => h.held.length > 0 || await page.eval(`inPrivate()`),
      { what: 'reverrouillage demandé, ou page dans l\'espace' });
    assert.deepEqual(await page.eval(`[inPrivate(), relock, ${MARK}]`), [false, true, '1'],
      'page rentrée dans l\'espace sans code, ou marque perdue');
    assert.deepEqual(seen, [], 'état demandé avant le reverrouillage');
    assert.equal(await macUnlocked(), true, 'session du Mac encore ouverte (prémisse)');
  } finally {
    await h.release();
  }
  await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
  assert.deepEqual([await macUnlocked(), await page.eval(MARK)], [false, null]);
  // « Sortir » accepté : marque levée
  await enter();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.equal(await page.eval(MARK), null, 'marque restée après « Sortir »');
  // fermeture par le Mac (15 minutes sans requête privée : l'espace est au repos) : levée à l'état lu
  await enter();
  await page.privateIdle();
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé par le Mac' });
  assert.equal(await page.eval(MARK), null, 'marque restée après la fermeture par le Mac');
  page.assertNoErrors();
});

// réponses données au verrouillage à la place du Mac (Fetch.fulfillRequest) : celle du Mac sans module de chiffrement,
// et deux pannes sans réponse claire du Mac (relais Tailscale, erreur interne)
const UNAVAILABLE = { responseCode: 503, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
  body: Buffer.from(JSON.stringify({ error: 'espace privé indisponible : bibliothèque cryptography non installée' }))
    .toString('base64') };
const BAD_GATEWAY = { responseCode: 502, responseHeaders: [{ name: 'Content-Type', value: 'text/plain' }],
  body: Buffer.from('Bad Gateway').toString('base64') };
const INTERNAL = { responseCode: 500, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
  body: Buffer.from('{"error":"erreur interne"}').toString('base64') };
const answerLock = async (h, reply) => {
  await waitUntil(() => h.held.length > 0, { what: 'verrouillage envoyé' });
  for (const r of h.take()) await page.send('Fetch.fulfillRequest', { requestId: r.requestId, ...reply });
};

test('reverrouillage : un refus clair du Mac vaut verrouillé (onglet débloqué) ; une panne sans réponse claire non',
  async () => {
    await enter();
    // verrouillages retenus tant que hold ; sinon (fermeture réelle sur le Mac, faite par le test) ils passent
    let hold = true;
    const h = await page.holdRequests(['*/api/private/lock'], () => hold);
    const lockMac = async () => { hold = false; assert.equal(await post('/api/private/lock', {}), 200); hold = true; };
    try {
      await page.eval(restored);
      await waitUntil(() => h.held.length > 0, { what: 'verrouillage envoyé' });
      await lockMac();                             // l'espace est fermé sur le Mac ; la page attend sa réponse
      for (const reply of [BAD_GATEWAY, INTERNAL]) {
        await answerLock(h, reply);
        await page.waitFor(`!relocking && $('lamp').classList.contains('err')`, { what: 'réponse lue' });
        assert.deepEqual(await page.eval(`[relock, ${MARK}, inPrivate()]`), [true, '1', false],
          `reverrouillage tenu pour accepté sur une réponse ${reply.responseCode} sans refus du Mac`);
        await page.eval(`void refreshStatus()`);   // nouvel essai
      }
      await answerLock(h, UNAVAILABLE);
      await page.waitFor(`!relock && $('lamp').classList.contains('ok')`, { what: 'onglet débloqué, état lu' });
      assert.equal(await page.eval(MARK), null);
      // « Sortir » refusé de même par le Mac : la sortie est appliquée
      await enter();
      await page.privateIdle();
      await page.click('#privExit');
      await waitUntil(() => h.held.length > 0, { what: 'sortie demandée' });
      await lockMac();
      await answerLock(h, UNAVAILABLE);
      await page.waitFor(`!inPrivate() && $('toastBox').textContent === ${JSON.stringify('Sorti de l\'espace privé')}`,
        { what: 'sortie appliquée' });
    } finally {
      await h.release();
    }
    // (les réponses données à la place du Mac, et elles seules, sont notées en erreur par Chrome)
    page.errors.splice(0, page.errors.length, ...page.errors.filter(e =>
      !/status of 50[023] \(.*\) \(http:\/\/[^/]+\/api\/private\/lock\)$/.test(e)));
    page.assertNoErrors();
  });

test('code accepté, état relu en échec, page fermée : traitée comme dans l\'espace (verrouillée, marquée)',
  async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
  await watchFetch();
  const h = await page.holdRequests(['*/api/status'], () => true);   // coupure brève : l'état relu échoue
  try {
    await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
    await page.waitFor(`zqDone && zqAfter > 0`, { what: 'code accepté, état demandé' });
    await waitUntil(() => h.held.length > 0, { what: 'état demandé' });
    for (const r of h.take()) await page.send('Fetch.failRequest', { requestId: r.requestId,
      errorReason: 'ConnectionRefused' });
    await page.eval(`zqEntry`);
    assert.deepEqual(await page.eval(`[inPrivate(), relock, entering]`), [false, false, false], 'prémisse');
    const sent = await page.eval(`zqLocks`);
    await page.eval(hide);
    assert.deepEqual(await page.eval(`[zqLocks - ${sent}, relock, hidInPrivate, ${MARK}]`), [1, true, true, '1'],
      'fermeture sans verrouillage alors que la session est ouverte');
  } finally {
    await h.release();
  }
  await backLocked();
  assert.equal(await page.eval(`inPrivate()`), false, 'rentrée dans l\'espace sans code');
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_CONNECTION_REFUSED/.test(e)));
  page.assertNoErrors();
});

test('état servi avant la fermeture, reçu après : jamais appliqué (l\'espace reste à reverrouiller)', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
  await watchFetch();
  // le code est accepté ; l'état relu ensuite est servi par le Mac (espace ouvert) mais sa réponse se fait attendre
  await page.holdFetch(`u => u === '/api/status' && zqDone`);
  await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
  await page.waitFor(`zqDone && zqAfter > 0`, { what: 'code accepté, état demandé' });
  await page.eval(hide);                           // fermée pendant l'entrée : verrouillage et marque
  await page.releaseFetch();
  await page.eval(`zqEntry`);
  assert.deepEqual(await page.eval(`[inPrivate(), relock, pileItems.some(it => it.private)]`), [false, true, false],
    'état d\'avant le verrouillage appliqué');
  await backLocked();
  page.assertNoErrors();
});

test('page fermée puis revenue avant la réponse du code : entrée refusée, à retaper', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok') && !relock`, { what: 'page prête, hors de l\'espace' });
  await watchFetch();
  await page.eval(`openPrivSheet('privUnlockSheet')`);
  await page.holdFetch(`u => u === '/api/private/unlock'`);
  await page.eval(`void (window.zqEntry = ($('puCode').value = ${JSON.stringify(CODE)}, privUnlock()))`);
  await page.waitFor(`zqCalls.includes('/api/private/unlock')`, { what: 'code envoyé' });
  await page.eval(hide);
  await page.eval(`window.fetch = zqFetch`);
  await page.eval(restored);
  await page.releaseFetch();
  await page.eval(`zqEntry`);
  assert.deepEqual(await page.eval(`[openedSheet === $('privUnlockSheet'), $('puErr').textContent, inPrivate()]`),
    [true, 'Page fermée pendant l\'envoi : retapez le code.', false]);
  await page.waitFor(`!relock`, { what: 'reverrouillage accepté' });
  assert.equal(await macUnlocked(), false);
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('« Sortir » en attente quand la page se ferme : rien n\'est redessiné ni annoncé à la réponse du Mac',
  async () => {
  await enter();
  await page.privateIdle();
  await watchFetch();
  const h = await page.holdRequests(['*/api/private/lock'], () => true);
  try {
    await page.click('#privExit');
    await waitUntil(() => h.held.length > 0, { what: 'sortie demandée' });
    await page.eval(hide);                         // fermée pendant l'attente (son verrouillage est retenu aussi)
    await page.eval(`zqCalls.length = 0; toast('zq')`);
    await answerLock(h, BAD_GATEWAY);              // le Mac ne répond pas clairement à « Sortir »
    await page.waitFor(`!leavingPrivate`, { what: 'réponse de « Sortir » lue' });
    assert.deepEqual(await page.eval(`[$('toastBox').textContent, zqCalls.filter(u => u === '/api/pile')]`),
      ['zq', []], 'sortie refusée annoncée ou pile relue sur une page fermée');
  } finally {
    await h.release();
  }
  await backLocked();
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e =>
    !/status of 502 \(.*\) \(http:\/\/[^/]+\/api\/private\/lock\)$/.test(e)));
  page.assertNoErrors();
});

test('code d\'accès redemandé dans l\'espace privé : « Sortir » ferme quand même la session, puis la page du code',
  async () => {
  await enter();
  await page.privateIdle();
  // cookie d'accès seul effacé : le verrouillage passe sans lui (il ne ferme que la session de cette page)
  await page.send('Network.deleteCookies', { name: 'qwen_access', url: bench.url });
  await page.click('#privExit');
  await waitUntil(() => page.eval(`!!document.getElementById('c')`).catch(() => false),
    { what: 'page du code d\'accès' });
  // (sur la page du code, RELOCK_MARK n'existe pas : la marque est lue sous son nom)
  assert.equal(await page.eval(`sessionStorage.getItem('relock')`), null, 'sortie acceptée, marque restée');
  await bench.login(page);
  await page.ready('interface rouverte');
  assert.deepEqual(await page.eval(`[inPrivate(), ${MARK}]`), [false, null], 'rentrée dans l\'espace sans code');
  assert.equal(await macUnlocked(), false, 'session du Mac restée ouverte');
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/status of 401 \(Unauthorized\)/.test(e)));
  page.assertNoErrors();
});

const UNAUTHORIZED = { responseCode: 401, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
  body: Buffer.from(JSON.stringify({ error: 'code d\'accès requis' })).toString('base64') };

// session privée de cette page vue par le Mac, hors de la page : cookies lus dans le navigateur (HttpOnly compris)
// avant qu'un test n'efface le cookie d'accès ; rend une fonction qui demande au Mac si la session est ouverte
async function macSessionOf() {
  const { cookies } = await page.send('Network.getCookies', { urls: [bench.url] });
  const header = ['qwen_access', 'qwen_private'].map(n => `${n}=${cookies.find(c => c.name === n)?.value ?? ''}`)
    .join('; ');
  return async () => (await (await fetch(bench.direct + '/api/status', { headers: { Cookie: header } })).json())
    .private.unlocked;
}

test('verrouillage refusé par un 401 (serveur d\'avant) : ne vaut pas verrouillé, reverrouillé après le code',
  async () => {
  await enter();
  await page.privateIdle();
  const unlocked = await macSessionOf();
  await page.send('Network.deleteCookies', { name: 'qwen_access', url: bench.url });
  // ancien serveur : aucun verrouillage n'arrive au Mac (retenus) ; celui de « Sortir » reçoit 401, les autres
  // (fermeture de l'interface, page du code) aussi, une fois la page du code affichée
  const h = await page.holdRequests(['*/api/private/lock'], () => true);
  try {
    await page.click('#privExit');
    await answerLock(h, UNAUTHORIZED);
    await waitUntil(() => page.eval(`!!document.getElementById('c')`).catch(() => false),
      { what: 'page du code d\'accès' });
    assert.equal(await page.eval(`sessionStorage.getItem('relock')`), '1', 'marque levée sans verrouillage du Mac');
    assert.equal(await unlocked(), true, 'session du Mac fermée : le scénario ne simule plus un ancien serveur');
    for (const r of h.take()) await page.send('Fetch.fulfillRequest', { requestId: r.requestId, ...UNAUTHORIZED });
  } finally {
    await h.release();
  }
  await bench.login(page);                         // code saisi : la page revient, marquée
  await page.waitFor(`!relock && $('lamp').classList.contains('ok')`, { what: 'reverrouillée, état lu' });
  assert.deepEqual(await page.eval(`[inPrivate(), ${MARK}]`), [false, null], 'rentrée dans l\'espace sans code');
  assert.equal(await unlocked(), false, 'session du Mac restée ouverte');
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/status of 401 \(Unauthorized\)/.test(e)));
  page.assertNoErrors();
});

test('page du code chargée avec la marque : elle ferme la session du Mac sans attendre le code', async () => {
  await enter();
  await page.privateIdle();
  const unlocked = await macSessionOf();
  await page.send('Network.deleteCookies', { name: 'qwen_access', url: bench.url });
  // le verrouillage de la fermeture de l'interface se perd (réseau coupé) : seule la page du code peut le refaire
  await page.eval(`(() => { const f = window.fetch;
    window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? Promise.reject(new TypeError('coupé'))
      : f(u, ...a); })()`);
  await page.goto(bench.url + '/');                // rechargement sans cookie d'accès : page du code, marque posée
  await page.waitFor(`!!document.getElementById('c')`, { what: 'page du code d\'accès' });
  assert.equal(await page.eval(`sessionStorage.getItem('relock')`), '1', 'marque levée par la page du code');
  await waitUntil(async () => !(await unlocked()), { what: 'session du Mac fermée par la page du code' });
  await bench.login(page);
  await page.waitFor(`!relock && $('lamp').classList.contains('ok')`, { what: 'reverrouillée, état lu' });
  assert.deepEqual(await page.eval(`[inPrivate(), ${MARK}]`), [false, null], 'rentrée dans l\'espace sans code');
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/status of 401 \(Unauthorized\)/.test(e)));
  page.assertNoErrors();
});
