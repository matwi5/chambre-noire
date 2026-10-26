// En-tête, dans la vue du téléphone : réduit au logo, au nom et à la lampe d'état (grise pendant la connexion, ambre
// fixe moteur prêt, ambre pulsée pendant un calcul, rouge Mac injoignable), dont le toucher ouvre la feuille du moteur
// avec « Ouvrir depuis le téléphone » (sur le Mac) et la ligne « Espace privé » au cadenas ; dans l'espace privé, «
// Sortir » à côté de la lampe ; animations réduites : un anneau fixe pendant un calcul, ambre ou vert. Le cas « pas le
// Mac » (sans « Ouvrir depuis le téléphone ») est dans relais.test.mjs.
//   venv/bin/python tests/check.py --quick --ui tests/ui/entete.test.mjs
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
  bench?.release('lampe');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const lamp = () => page.eval(`({ cls: [...$('lamp').classList].filter(c => c !== 'lamp').sort().join(' '),
  label: $('lamp').getAttribute('aria-label'), pulse: getComputedStyle($('lamp'), '::after').animationName })`);

test('connexion : la lampe est grise tant que le Mac n\'a pas répondu, puis ambre fixe', async () => {
  // /api/status retenue par Chrome jusqu'à la fin de la vérification
  const paused = [];
  page.on('Fetch.requestPaused', p => paused.push(p.requestId));
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/status*' }] });
  await page.goto(bench.url + '/');
  await page.waitFor(`document.readyState === 'complete'`);
  assert.deepEqual(await lamp(), { cls: '', label: 'Connexion au Mac…', pulse: 'none' });
  await page.send('Fetch.disable');
  await Promise.all(paused.map(requestId => page.send('Fetch.continueRequest', { requestId }).catch(() => {})));
  await page.eval(`refreshStatus()`);
  await page.ready();
  assert.deepEqual(await lamp(), { cls: 'ok', label: 'Moteur prêt · Q4', pulse: 'none' });
  assert.equal(await page.eval(`!!$('phoneBtn') || !!$('statusChip') || !!$('status') || !!$('island')`), false,
    'anciens éléments de l\'en-tête retirés');
  page.assertNoErrors();
});

test('calcul : ambre pulsée tant qu\'une génération tourne ; rouge quand le Mac ne répond plus', async () => {
  const held = await page.launch('HOLD=lampe en cours');
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('lamp').classList.contains('busy')`, { what: 'lampe du calcul' });
  assert.deepEqual(await lamp(), { cls: 'busy ok', label: 'Calcul en cours · Q4', pulse: 'lamp-pulse' });
  await page.eval(`postJson('/api/job/' + ${JSON.stringify(held.id)} + '/cancel', {})`);
  bench.release('lampe');
  await bench.idle();
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('lamp').classList.contains('busy')`, { what: 'calcul fini' });
  // réponse de /api/status changée le temps d'une interrogation : change(s) → état reçu par la page, ou une erreur
  const once = change => page.eval(`(async () => { const f = window.fetch, change = ${change};
    window.fetch = (u, ...a) => String(u) !== '/api/status' ? f(u, ...a)
      : f(u, ...a).then(r => r.json()).then(s => new Response(JSON.stringify(change(s))));
    try { await refreshStatus(); } finally { window.fetch = f; } })()`);
  // file non vide, rien en calcul (génération d'un autre espace qui attend son tour) : ambre pulsée aussi
  await once(`s => ({ ...s, busy: false, queued: 1 })`);
  assert.deepEqual(await lamp(), { cls: 'busy ok', label: 'Calcul en cours · Q4', pulse: 'lamp-pulse' });
  // moteur indisponible (fichiers manquants) : rouge, la feuille dit ce qui manque
  await once(`s => ({ ...s, sd_ready: false, detail: 'fichiers manquants : zq-modele.gguf' })`);
  assert.deepEqual(await lamp(), { cls: 'err', label: 'Moteur indisponible', pulse: 'none' });
  assert.match(await page.eval(`$('engineFacts').textContent`), /fichiers manquants : zq-modele\.gguf/);
  // Mac injoignable : /api/status refusée
  await once(`() => { throw new TypeError('réseau coupé'); }`);
  assert.deepEqual(await lamp(), { cls: 'err', label: 'Mac injoignable', pulse: 'none' });
  // l'erreur garde une icône (rouge jamais seul) : le point devient le pictogramme d'erreur en pixels
  assert.notEqual(await page.eval(`getComputedStyle($('lamp'), '::after').maskImage`), 'none');
  await page.eval(`refreshStatus()`);
  await page.ready('moteur de nouveau prêt');
  page.assertNoErrors();
});

test('la lampe ouvre sa feuille : état, « Ouvrir depuis le téléphone » (Mac), « Espace privé », journal', async () => {
  await page.click('#lamp');
  await page.waitFor(`openedSheet === $('engineSheet')`, { what: 'feuille de la lampe' });
  assert.match(await page.eval(`$('engineFacts').textContent`), /État.*prêt/);
  assert.equal(await page.visible('#phone'), true, 'sur le Mac : adresses et code du téléphone');
  assert.equal(await page.eval(`$('phone').querySelector('h3').textContent`), 'Ouvrir depuis le téléphone');
  assert.equal(await page.visible('#privEntry'), true, 'ligne de l\'espace privé');
  assert.equal(await page.eval(`$('privEntry').textContent.trim()`), 'Espace privé');
  assert.equal(await page.eval(`!!$('privEntry').querySelector('svg')`), true, 'avec le cadenas');
  assert.equal(await page.eval(`$('engineSheet').contains($('log'))`), true);
  // dans l'ordre : état, téléphone, espace privé, journal
  const order = await page.eval(`['engineFacts', 'phone', 'privEntry', 'log']
    .map(id => $(id).getBoundingClientRect().top)`);
  assert.deepEqual([...order].sort((a, b) => a - b), order);
  assert.equal(await page.eval(`!!document.querySelector('#pane-tirages #privEntry, .topbar #privEntry')`), false,
    'plus de cadenas hors de la feuille');
  await page.click('#privEntry');                   // pas d'espace : la feuille de création remplace celle-ci
  await page.waitFor(`openedSheet === $('privCreateSheet')`, { what: 'création de l\'espace privé' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('en-tête à 367 px : nom, lampe et « Sortir » sur une ligne, en public et dans l\'espace privé', async () => {
  const boxes = () => page.eval(`['.brand', '#lamp', '#privExit'].map(s => document.querySelector(s))
    .map(el => el.getClientRects().length ? (r => [r.left, r.right, r.top, r.bottom])(el.getBoundingClientRect())
      : null)`);
  let [brand, lampBox, exit] = await boxes();
  assert.equal(exit, null, 'pas de « Sortir » dans l\'espace public');
  assert.ok(brand[1] <= lampBox[0] + .5 && lampBox[1] <= await page.eval(`innerWidth`), 'lampe à droite du nom');
  assert.deepEqual(await page.overflowing(), []);
  await page.enterPrivate(CODE);
  [brand, lampBox, exit] = await boxes();
  assert.ok(brand[1] <= lampBox[0] + .5 && lampBox[1] <= exit[0] + .5, 'nom, lampe puis « Sortir »');
  assert.ok(exit[1] <= await page.eval(`innerWidth`), '« Sortir » dans la vue');
  assert.ok(lampBox[2] < exit[3] && exit[2] < lampBox[3], 'sur la même ligne');
  assert.equal(await page.visible('.topbar h1'), true, 'le nom reste affiché');
  assert.equal(await page.eval(`$('privExit').textContent.trim()`), 'Sortir');
  assert.deepEqual(await page.overflowing(), []);
  await page.click('#lamp');
  await page.waitFor(`openedSheet === $('engineSheet')`, { what: 'feuille de la lampe' });
  assert.equal(await page.visible('#privEntry'), false, 'dans l\'espace : pas d\'entrée, la sortie est en haut');
  await page.eval(`closeSheet()`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.equal(await page.visible('#privExit'), false);
  page.assertNoErrors();
});

test('animations réduites : pendant un calcul, un anneau fixe au lieu du point plein, ambre ou vert', async () => {
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  // point de la lampe : fond et ombre calculés, et la teinte de l'espace affiché (--accent) en rgb ; lus deux images
  // plus tard (animations réduites : chaque changement de style passe encore par une transition de 0,01 ms)
  const dot = () => page.eval(`(async () => { await new Promise(r => requestAnimationFrame(() =>
    requestAnimationFrame(r))); const s = getComputedStyle($('lamp'), '::after');
    const t = document.createElement('i'); t.style.color = 'var(--accent)'; document.body.append(t);
    const accent = getComputedStyle(t).color; t.remove();
    return { fill: s.backgroundColor === accent, ring: s.boxShadow.includes('inset') && s.boxShadow.includes(accent),
      pulse: s.animationName }; })()`);
  // /api/status reçue avec un calcul en cours (busy), le temps d'une interrogation
  const busy = () => page.eval(`(async () => { const f = window.fetch;
    window.fetch = (u, ...a) => String(u) !== '/api/status' ? f(u, ...a)
      : f(u, ...a).then(r => r.json()).then(s => new Response(JSON.stringify({ ...s, busy: true })));
    try { await refreshStatus(); } finally { window.fetch = f; } })()`);
  try {
    for (const space of ['public', 'privé']) {
      if (space === 'privé') await page.enterPrivate(CODE);
      await page.eval(`refreshStatus()`);
      assert.deepEqual(await dot(), { fill: true, ring: false, pulse: 'none' }, `prêt : point plein (${space})`);
      await busy();
      assert.equal(await page.eval(`$('lamp').classList.contains('busy')`), true);
      assert.deepEqual(await dot(), { fill: false, ring: true, pulse: 'none' }, `calcul : anneau fixe (${space})`);
    }
  } finally {
    await page.send('Emulation.setEmulatedMedia', { features: [] });
  }
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});
