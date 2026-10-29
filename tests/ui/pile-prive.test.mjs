// Pile du Labo dans l'espace privé, vue du téléphone : pile privée par ses routes (✕ et ✓ privés, un Garder qui
// arrive seul dans les Tirages privés affichés) ; « Sortir » juste après l'entrée, pile privée pas encore lue, ou
// pendant le chargement d'une image : rien de privé demandé ensuite, ni par un Garder refusé ni par une génération
// privée arrivée dans la file pendant la sortie ; Jeter privé abandonné dès l'appui sur « Sortir », tri privé ignoré
// pendant la sortie ; images des cartes retirées vidées au redessin ; aucune adresse privée chargée en avance hors de
// l'espace ; pendant « Sortir », ni ✓, ni ✕, ni flèches, ni balayage, ni la visionneuse ne trient, une carte qui
// partait revient, et rien ne part (Relancer, « Révéler », Supprimer, Dessiner, Reprendre, actions de la
// visionneuse) ; « Sortir » refusé : l'image ouverte en grand reprend son verrou court. Découpé de pile.test.mjs.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/pile-prive.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse, TOP } from './driver.mjs';

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
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
// toute adresse privée donnée à une image à partir de l'appel (attachée ou non : Chrome charge une image détachée,
// et sert sans requête une image déjà chargée par la page), notée dans srcAfter ; la surveillance n'est posée qu'une
// fois par page (srcWatched), chaque appel vide la liste
const watchPrivateSrc = () => page.eval(`(() => { window.srcAfter = []; if (window.srcWatched) return;
  window.srcWatched = true; const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', { configurable: true, get: d.get,
    set(v) { if (String(v).includes('/api/private/')) srcAfter.push(String(v)); d.set.call(this, v); } }); })()`);

test('espace privé : pile privée par ses routes ; un Jeter en attente à la sortie est abandonné', async () => {
  await page.made('zp11 publique');
  const exists = await page.eval(`privState.exists`);
  assert.equal(await page.eval(`postJson(${JSON.stringify(exists ? '/api/private/unlock' : '/api/private/create')},
    { code: ${JSON.stringify(CODE)} }).then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate() && !pileItems.length`, { what: 'dans l\'espace privé, pile privée vide' });
  await page.made('zp11 secrete garde');
  await page.made('zp11 secrete jete');
  assert.deepEqual(await page.pileCards(), ['zp11 secrete jete', 'zp11 secrete garde'], 'aucune carte publique');
  await page.eval(`sorts.length = 0`);
  await page.click('#pileNo');
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.click('#privExit');                   // sortie pendant le bandeau
  await page.waitFor(`!inPrivate() && pileItems.some(it => it.prompt === 'zp11 publique')`, { what: 'pile publique' });
  assert.equal(await page.eval(`$('undoBar').hidden`), true, 'bandeau privé parti avec l\'espace');
  assert.deepEqual(await page.pileCards(), ['zp11 publique']);
  await elapse(5500);                               // au-delà des 5 s du bandeau : le Jeter privé n'est pas parti
  assert.equal(await page.sortsSent('discard'), 0, 'Jeter privé envoyé après la sortie');
  // de retour dans l'espace : l'image jetée avant la sortie y est encore ; ✓ la garde dans les Tirages privés
  await page.enterPrivate(CODE);
  await page.waitFor(`inPrivate() && pileItems.length === 2`, { what: 'pile privée intacte' });
  await page.topShown();
  await page.click('#pileYes');
  await page.waitFor(`sorts.some(s => s.url.endsWith('/api/private/keep')) && pileItems.length === 1`,
    { what: 'gardée par la route privée' });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  assert.equal(await bench.inPile('zp11 secrete garde'), false, 'rien de privé dans la pile publique');
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
  await page.enterPrivate(CODE);
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
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
    await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
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

test('espace privé : « Sortir » refusé, l\'image de la pile ouverte en grand reprend son verrou court', async () => {
  await enterPile();
  await page.emptyPile(bench);
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
