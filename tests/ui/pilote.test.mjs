// Aides du pilote (driver.mjs) et délais des tests d'interface : page.leaks trouve un marqueur laissé dans une variable
// globale, un texte caché, un attribut ou un élément détaché ; bench.disk voit un fichier écrit ; chrome.phonePage
// est connectée au banc (le Mac demande le code d'accès : sans le cookie, il reçoit la page du code) ; page.eval et
// bench.idle échouent dans leur délai ; une erreur de console n'échoue que le test où elle apparaît, qu'elle nomme ;
// page.click refuse un élément recouvert ou hors de l'écran ; un test bloqué lancé par check.py échoue dans le délai
// par test, sans laisser Chrome ni le serveur du banc.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/pilote.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startBench, launchChrome, waitUntil, elapse, PHONE, PC, TABLET, TABLET_WIDE } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.ready();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const MARKS = ['zpLet', 'zpVar', 'zpCache', 'zpHidden', 'zpAttr', 'zpDetached'];

test('page.leaks : un marqueur laissé dans l\'état global ou caché dans la page est trouvé', async () => {
  assert.deepEqual(await page.leaks(MARKS), [], 'page neuve : rien');
  // fuites volontaires : let de premier niveau (Map dans un objet), var globale (Set), texte caché, attribut, élément
  // détaché gardé en mémoire
  await page.eval(`(() => {
    const s = document.createElement('script');
    s.textContent = "let zpPlanted = { cache: new Map([['k', { deep: ['zpLet'] }], ['zpCache', 1]]) };";
    document.head.append(s);
    window.zpGlobal = new Set(['x', 'zpVar']);
    const h = document.createElement('div'); h.hidden = true; h.textContent = 'zpHidden'; document.body.append(h);
    document.body.dataset.trace = 'zpAttr';
    window.zpKept = document.createElement('p'); zpKept.textContent = 'zpDetached';
  })()`);
  const found = await page.leaks(MARKS);
  for (const m of MARKS) assert.ok(found.some(f => f.endsWith(' : ' + m)), `${m} non trouvé : ${found.join(' ; ')}`);
  assert.ok(found.includes('mémoire zpPlanted.cache.get(k).deep[0] : zpLet'), found.join(' ; '));
  const skipped = await page.leaks(['zpLet', 'zpVar'], { skip: ['zpPlanted'] });
  assert.deepEqual(skipped, ['mémoire zpGlobal[1] : zpVar']);
  await page.goto(bench.url + '/');
  assert.deepEqual(await page.leaks(MARKS), [], 'page rechargée : plus rien');
  page.assertNoErrors();
});

test('bench.disk : une image enregistrée est vue, rien quand rien n\'est écrit', async () => {
  await page.ready();
  const disk = bench.disk();
  assert.deepEqual(disk.written(), []);
  await page.generate('zp1 disque');
  await bench.idle();
  const written = disk.written();
  assert.ok(written.length > 0 && written.some(f => f.startsWith('outputs')), written.join(', '));
  page.assertNoErrors();
});

test('chrome.phonePage : connectée au banc ; sans le cookie, le Mac lui-même reçoit la page du code', async () => {
  const alone = await launchChrome();              // profil à part : ses cookies effacés ne touchent pas page
  try {
    const p = await alone.phonePage();
    await p.goto(bench.url + '/');
    await p.ready('interface ouverte, sans saisie du code');
    await p.send('Network.clearBrowserCookies');
    await p.goto(bench.url + '/');
    await p.waitFor(`!!document.getElementById('c')`, { what: 'champ du code d\'accès' });
    assert.match(await p.eval(`document.body.innerText`),
      /Sur cet ordinateur : ouvrez Chambre noire par son raccourci/);
    assert.deepEqual((await bench.api('/api/status')).queue, [], 'bench.api : le Mac, avec le cookie');
  } finally {
    await alone.close();
  }
});

test('chrome.phonePage s\'ouvre au premier plan ; page.close ferme l\'onglet : la page restée ouverte y repasse',
  async () => {
  const other = await chrome.phonePage();
  try {
    await other.goto(bench.url + '/');
    await other.ready();
    assert.equal(await other.eval(`document.visibilityState`), 'visible', 'nouvelle page au premier plan');
    assert.equal(await page.eval(`document.visibilityState`), 'hidden', 'page derrière l\'autre onglet (prémisse)');
    other.assertNoErrors();
  } finally { await other.close(); }
  await page.waitFor(`document.visibilityState === 'visible'`, { what: 'page de nouveau au premier plan' });
  page.assertNoErrors();
});

test('page.close dans l\'espace privé : chaque page de l\'espace attendue au repos avant la fermeture', async () => {
  await page.enterPrivate('code-du-pilote');
  const other = await chrome.phonePage();
  let held = null, closing = null;
  try {
    await other.goto(bench.url + '/');
    await other.waitFor(`inPrivate()`, { what: 'autre page dans l\'espace' });
    // une lecture privée de la page restée ouverte encore en route (retenue avant le Mac)
    held = await page.holdRequests(['*/api/private/pile'], () => true);
    await page.eval(`void loadPile()`);
    await waitUntil(() => held.held.length > 0, { what: 'lecture privée en route' });
    let closed = false;
    closing = other.close().then(() => { closed = true; });
    await elapse(500);
    assert.equal(closed, false, 'onglet fermé (espace reverrouillé) avec une requête privée en route');
  } finally {
    await held?.release();
    await (closing || other.close());                // une seule fermeture, attendue aussi sur un échec
  }
  await page.lockedOnMac();                          // la page fermée dans l'espace l'a reverrouillé (pagehide)
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'page sortie de l\'espace' });
  page.assertNoErrors();
});

test('page.close dans l\'espace privé : une requête privée partie avant tout appel du pilote est attendue aussi',
  async () => {
    await page.enterPrivate('code-du-pilote');
    const other = await chrome.phonePage();
    let held = null, closing = null;
    try {
      // l'autre page est entrée d'elle-même (état lu du Mac), sans enterPrivate ni privateIdle du pilote ; une
      // lecture privée qui ne retient pas la pile (pileRead) part ensuite
      await other.goto(bench.url + '/');
      await other.waitFor(`inPrivate() && pileRead`, { what: 'autre page dans l\'espace, pile lue' });
      held = await other.holdRequests(['*/api/private/history'], () => true);
      await other.eval(`void fetch('/api/private/history')`);
      await waitUntil(() => held.held.length > 0, { what: 'lecture privée de l\'autre page en route' });
      let closed = false;
      closing = other.close().then(() => { closed = true; });
      await elapse(500);
      assert.equal(closed, false, 'onglet fermé (espace reverrouillé) avec sa propre requête privée en route');
    } finally {
      await held?.release();
      await (closing || other.close());
    }
    await page.lockedOnMac();
    await page.eval(`refreshStatus()`);
    await page.waitFor(`!inPrivate()`, { what: 'page sortie de l\'espace' });
    page.assertNoErrors();
  });

test('page.privateIdle : une vignette privée différée jamais chargée ne la retient pas, une image privée en route si',
  async () => {
    await page.enterPrivate('code-du-pilote');
    await page.made('zp3 secrete');
    const thumb = await page.eval(`thumbOf(pileItems.find(it => it.private))`);
    // vignette différée dans un bloc caché (comme les Tirages quand on est au Labo) : sa requête ne part jamais
    await page.eval(`(() => { const d = document.createElement('div'); d.id = 'zpLazy'; d.hidden = true;
      const im = document.createElement('img'); im.loading = 'lazy'; im.src = ${JSON.stringify(thumb + '&zp=lazy')};
      d.append(im); document.body.append(d); })()`);
    assert.equal(await page.eval(`$('zpLazy').firstChild.complete`), false, 'vignette pas chargée (prémisse)');
    await page.privateIdle();
    assert.equal(await page.eval(`$('zpLazy').firstChild.complete`), false, 'vignette différée chargée quand même');
    // une image privée dont la requête est partie (retenue avant le Mac) : attendue jusqu'à sa réponse
    const held = await page.holdRequests(['*/api/private/thumb*'], p => p.request.url.includes('zp=held'));
    let idle = false, waiting = null;
    try {
      // (image détachée, comme celles que la page charge à part : seule sa requête la montre)
      await page.eval(`(() => { window.zpHeld = new Image(); zpHeld.src = ${JSON.stringify(thumb + '&zp=held')}; })()`);
      await waitUntil(() => held.held.length > 0, { what: 'image privée en route' });
      waiting = page.privateIdle().then(() => { idle = true; });
      await elapse(500);
      assert.equal(idle, false, 'espace dit au repos avec une image privée en route');
    } finally {
      await held.release();
    }
    await waiting;
    await page.eval(`$('zpLazy').remove(); window.zpHeld = null`);
    await page.keepPile();
    await page.click('#privExit');
    await page.waitFor(`!inPrivate()`, { what: 'page sortie de l\'espace' });
    page.assertNoErrors();
  });

test('page.close dans l\'espace privé : la vignette différée d\'une page restée derrière part avant le verrouillage',
  async () => {
    await page.enterPrivate('code-du-pilote');
    await page.made('zp4 secrete', { shown: false });
    const thumb = await page.eval(`thumbOf(pileItems.find(it => it.private))`);
    const other = await chrome.phonePage();          // au premier plan : page passe derrière
    let closed = false;
    try {
      await other.goto(bench.url + '/');
      await other.waitFor(`inPrivate() && pileRead`, { what: 'autre page dans l\'espace' });
      await page.waitFor(`document.hidden`, { what: 'page derrière l\'autre onglet' });
      // vignette différée à l'écran de la page cachée : elle ne demandera son image qu'une fois la page devant
      await page.eval(`(() => { const im = document.createElement('img'); im.id = 'zpLate'; im.loading = 'lazy';
        im.style.cssText = 'position:fixed;left:0;top:0;width:40px;height:40px;z-index:90';
        im.src = ${JSON.stringify(thumb + '&zp=late')}; document.body.append(im); })()`);
      await other.close();
      closed = true;
    } finally {
      if (!closed) await other.close();
    }
    await page.lockedOnMac();
    await page.waitFor(`$('zpLate').complete`, { what: 'vignette différée arrivée' });
    assert.equal(await page.eval(`$('zpLate').naturalWidth > 0`), true, 'vignette différée refusée (403)');
    await page.eval(`$('zpLate').remove()`);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`!inPrivate()`, { what: 'page sortie de l\'espace' });
    page.assertNoErrors();
  });

// ce que la page voit de sa vue : largeur, pointeur principal, survol et tactile
const SEEN = `({ width: innerWidth, height: innerHeight, coarse: matchMedia('(pointer: coarse)').matches,
  hover: matchMedia('(hover: hover)').matches, touch: navigator.maxTouchPoints > 0 })`;

test('chrome.newPage : vues PC (souris) et tablette (tactile, en hauteur et en largeur) ; page.setView', async () => {
  const seen = {};
  for (const [name, view] of Object.entries({ PHONE, PC, TABLET, TABLET_WIDE })) {
    const p = await chrome.newPage(view);
    try {
      await p.goto(bench.url + '/');
      await p.ready();
      seen[name] = await p.eval(SEEN);
      p.assertNoErrors();
    } finally { await p.close(); }
  }
  assert.deepEqual(seen, {
    PHONE: { width: 367, height: 760, coarse: true, hover: false, touch: true },
    PC: { width: 1280, height: 800, coarse: false, hover: true, touch: false },
    TABLET: { width: 800, height: 1280, coarse: true, hover: false, touch: true },
    TABLET_WIDE: { width: 1280, height: 800, coarse: true, hover: false, touch: true },
  });
  const p = await chrome.newPage(PC);
  try {
    await p.goto(bench.url + '/');
    await p.ready();
    await p.setView(TABLET);
    assert.deepEqual(await p.eval(SEEN), seen.TABLET, 'PC devenue tablette, sans rechargement');
    await p.setView(PC);
    assert.deepEqual(await p.eval(SEEN), seen.PC, 'puis PC de nouveau');
  } finally { await p.close(); }
});

test('page.keyDown, keyUp, press : touche maintenue, répétée, relâchée, avec modificateurs', async () => {
  const p = await chrome.newPage(PC);
  try {
    await p.goto(bench.url + '/');
    await p.ready();
    await p.eval(`(() => { window.zpKeys = []; const log = e => zpKeys.push([e.type, e.key, e.code, e.repeat,
      ['ctrlKey', 'metaKey', 'shiftKey', 'altKey'].filter(m => e[m]).join('+')].join(' '));
      addEventListener('keydown', log); addEventListener('keyup', log); })()`);
    await p.keyDown(' ');
    await p.keyDown(' ', { repeat: true });
    await p.keyDown(' ', { repeat: true });
    await p.keyUp(' ');
    await p.press('ArrowLeft');
    await p.press('z', { modifiers: ['ctrl'] });
    await p.press('Enter', { modifiers: ['meta'] });
    await p.press('Escape');
    assert.deepEqual(await p.eval(`zpKeys`), [
      'keydown   Space false ', 'keydown   Space true ', 'keydown   Space true ', 'keyup   Space false ',
      'keydown ArrowLeft ArrowLeft false ', 'keyup ArrowLeft ArrowLeft false ',
      'keydown Control ControlLeft false ctrlKey', 'keydown z KeyZ false ctrlKey', 'keyup z KeyZ false ctrlKey',
      'keyup Control ControlLeft false ',
      'keydown Meta MetaLeft false metaKey', 'keydown Enter Enter false metaKey', 'keyup Enter Enter false metaKey',
      'keyup Meta MetaLeft false ',
      'keydown Escape Escape false ', 'keyup Escape Escape false ']);
    // aucune touche, laissée passer par la page, n'a ouvert d'onglet de Chrome par-dessus elle
    await p.press('ArrowLeft');
    await p.press('ArrowRight');
    await p.eval(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
    assert.deepEqual((await p.send('Target.getTargets')).targetInfos
      .filter(t => t.type === 'page' && t.url.startsWith('chrome:'))
      .map(t => t.url), [], 'onglet de Chrome ouvert par une touche');
    assert.equal(await p.eval(`document.visibilityState`), 'visible', 'page cachée par une touche');
    p.assertNoErrors();
  } finally { await p.close(); }
});

test('page.hold puis page.release : appui maintenu sur un élément, au doigt et à la souris', async () => {
  for (const [view, mouse, type] of [[TABLET, false, 'touch'], [PC, true, 'mouse']]) {
    const p = await chrome.newPage(view);
    try {
      await p.goto(bench.url + '/');
      await p.ready();
      await p.eval(`(() => { const b = document.createElement('button'); b.id = 'zpHold'; b.textContent = 'zp';
        b.style.cssText = 'position:fixed;left:40px;top:300px;width:90px;height:50px;z-index:50;touch-action:none';
        window.zpPointer = []; const log = e => zpPointer.push(e.type + ' ' + e.pointerType);
        b.addEventListener('pointerdown', log); b.addEventListener('pointerup', log); document.body.append(b); })()`);
      await p.hold('#zpHold', { mouse });
      assert.deepEqual(await p.eval(`zpPointer`), [`pointerdown ${type}`], 'appui tenu : pas encore relâché');
      await p.release();
      assert.deepEqual(await p.eval(`zpPointer`), [`pointerdown ${type}`, `pointerup ${type}`]);
      p.assertNoErrors();
    } finally { await p.close(); }
  }
});

test('délais : page.eval et bench.idle échouent au lieu d\'attendre sans fin', async () => {
  await assert.rejects(page.eval('new Promise(() => {})', { timeout: 300 }), /pas de réponse après 0.3 s/);
  assert.equal(await page.eval(`postJson('/api/generate', { prompt: 'HOLD=pilote zp2', width: 512, height: 512,
    steps: 2, cfg: 1, seed: -1, ref_images: [] }).then(r => r.status)`), 202);
  await assert.rejects(bench.idle({ timeout: 300 }), /Mac au repos/);
  bench.release('pilote');
  await bench.idle();
  page.assertNoErrors();
});

test('erreurs : une erreur de console laissée par ce test…', async () => {
  await page.eval(`console.error('zpErr1')`);
  await waitUntil(() => page.errors.length > 0, { what: 'erreur reçue par le pilote' });
  assert.match(page.errors[0], /^« erreurs : une erreur de console laissée par ce test… » : console\.error : zpErr1/);
});

test('erreurs : …n\'échoue pas le suivant ; l\'échec nomme son test', async () => {
  page.assertNoErrors();
  await page.eval(`console.error('zpErr2')`);
  await waitUntil(() => page.errors.length > 0, { what: 'erreur reçue par le pilote' });
  assert.throws(() => page.assertNoErrors(),
    /« erreurs : …n'échoue pas le suivant ; l'échec nomme son test » : console\.error : zpErr2/);
  assert.ok(!page.errors.some(e => e.includes('zpErr1')), page.errors.join(' ; '));
  page.errors.length = 0;
});

test('page.click : échoue sur un élément recouvert ou hors de l\'écran, en nommant ce qui le recouvre', async () => {
  await page.eval(`(() => { const b = document.createElement('button'); b.id = 'zpBtn'; b.textContent = 'zp';
    b.style.cssText = 'position:fixed;left:20px;top:200px;width:80px;height:40px;z-index:50';
    b.onclick = () => { window.zpClicks = (window.zpClicks || 0) + 1; }; document.body.append(b);
    const c = document.createElement('div'); c.id = 'zpCover';
    c.style.cssText = 'position:fixed;left:0;top:150px;width:200px;height:200px;z-index:60'; document.body.append(c);
  })()`);
  await assert.rejects(page.click('#zpBtn', { timeout: 300 }), /élément recouvert par #zpCover : #zpBtn/);
  assert.equal(await page.eval(`window.zpClicks || 0`), 0, 'recouvert : pas d\'appui');
  await page.eval(`$('zpCover').remove()`);
  await page.click('#zpBtn');
  assert.equal(await page.eval(`zpClicks`), 1);
  await page.eval(`$('zpBtn').style.left = '-500px'`);
  await assert.rejects(page.click('#zpBtn', { timeout: 300 }), /élément hors de l'écran : #zpBtn/);
  await page.eval(`$('zpBtn').remove()`);
  page.assertNoErrors();
});

test('check.py : un test bloqué échoue dans le délai par test, sans Chrome ni banc restants', () => {
  const journal = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-pilote-')), 'check.log');
  const start = Date.now();
  const r = spawnSync(process.env.PYTHON || 'python3', ['tests/check.py', '--no-bench', '--ui',
    'tests/ui/fixtures/bloque.mjs'], { encoding: 'utf8', timeout: 120000,
    env: { ...process.env, QWEN_UI_TEST_TIMEOUT: '5000', QWEN_CHECK_JOURNAL: journal } });
  const out = r.stdout + r.stderr;
  fs.rmSync(path.dirname(journal), { recursive: true, force: true });
  assert.equal(r.status, 1, out);
  assert.match(out, /test timed out after 5000ms/);
  assert.ok(Date.now() - start < 60000, `trop long : ${(Date.now() - start) / 1000} s`);
  const pids = JSON.parse(out.match(/PIDS (\[[\d, ]+\])/)[1]);
  assert.equal(pids.length, 2);
  const alive = pids.filter(pid => { try { process.kill(pid, 0); return true; } catch { return false; } });
  assert.deepEqual(alive, [], 'Chrome ou le serveur du banc encore là');
});
