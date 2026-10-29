// Pile du Labo, vue du téléphone : verrou court et page cachée. Aucun geste ne trie une image pas encore affichée,
// même 3 s plus tard, et une image illisible se trie une fois son chargement en échec, pas pendant ; après un tri,
// ✓, ✕ et la visionneuse ignorent un double appui jusqu'à l'image suivante affichée depuis 0,3 s, comme une carte
// arrivée sur le dessus sans tri d'ici ; ces 0,3 s ne comptent que page visible (carte ou image de la visionneuse
// arrivée page cachée, page gelée ; une carte déjà vue avant se trie dès le retour) ; carte masquée par Dessiner
// jamais triée. Découpé de pile.test.mjs.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/pile-verrou.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse, PHONE,
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
  await chrome?.close();
  await bench?.stop();
});

// carte du dessus publique : son prompt, son image posée (posed : miniature ou image, chargement fini), un Jeter en
// attente, les tris envoyés
const TOP_IMG = `$('pile').querySelector('[data-k="0"] .pimg img')`;
const topState = () => page.eval(`({ top: ${TOP}, posed: posed(${TOP_IMG}), discarding: !!discarding,
  sorts: sorts.length })`);
// une image neuve sur le dessus, ses images (miniature, image complète) retenues avant le Mac
async function heldTop(prompt) {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
  await page.made(`${prompt} dessous`);
  await page.waitFor(`${SORT_IDLE}`, { what: 'pile au repos' });
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
    for (const [what, act] of [['✓', () => page.sort('keep', { ready: false })],
      ['✕', () => page.sort('discard', { ready: false })],
      ['→', () => page.sort('keep', { by: 'key', ready: false })],
      ['←', () => page.sort('discard', { by: 'key', ready: false })],
      ['balayage', () => page.swipe('#pile .pimg', -200)]]) {
      await act();
      await elapse(400);
      assert.deepEqual(await topState(), unseen, `${what} sur une image pas affichée`);
    }
    await page.viewPile('zp31 dessus', { seen: false });   // visionneuse : son image retenue elle aussi
    await page.eval(`${VIEWER_PRESS.discard}`);   // Jeter
    await elapse(400);
    assert.deepEqual(await page.eval(`[vIndex >= 0 && vList[vIndex]?.prompt, !!discarding, sorts.length]`),
      ['zp31 dessus', false, 0], 'Jeter de la visionneuse sur une image pas affichée');
    await page.closeViewer();
  } finally {
    await h.release();
  }
  // l'image arrive : ✕ la jette (bandeau), comme d'habitude
  await page.topShown();
  await page.sort('discard', { ready: false });
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('après un tri, la suivante pas encore affichée : ✕ ne la jette pas, même 3 s plus tard',
  async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
    await page.sort('keep', { ready: false });                  // le dessus gardé : la suivante dessus, sans son image
    await page.waitFor(`${TOP} === 'zp33 suivante'`, { what: 'suivante sur le dessus' });
    await elapse(3200);                            // (l'ancien plafond du verrou, 3 s, dépassé)
    await page.sort('discard', { ready: false });
    await elapse(400);
    assert.deepEqual(await topState(), { top: 'zp33 suivante', posed: false, discarding: false, sorts: 1 },
      '✕ 3 s plus tard sur une image pas affichée (seul le Garder d\'avant envoyé)');
  } finally {
    await h.release();
  }
  await page.emptyPile(bench);
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
    await page.sort('discard', { ready: false });
    await elapse(400);
    assert.deepEqual(await topState(), { top: 'zp32 dessus', posed: false, discarding: false, sorts: 0 },
      '✕ pendant le nouvel essai');
    await waitUntil(async () => (await fail(), (await topState()).posed), { what: 'échec du chargement constaté' });
  } finally {
    await h.release();
  }
  await page.waitFor(`${SORT_IDLE}`, { what: 'pile au repos' });
  await page.sort('discard', { ready: false });
  await page.waitFor(`!$('undoBar').hidden`, { what: 'bandeau sur la carte illisible' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/ERR_FAILED|ERR_ABORTED/.test(e)));
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
  ${PRESS.discard}; await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
  return !!discarding; })()`);

test('après un tri, ✕ ignoré 0,3 s après l\'affichage de la carte suivante, même arrivée tard', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
    await page.sort('keep', { ready: false });   // le dessus gardé : la suivante dessus, son image retenue
    await page.waitFor(`${TOP} === 'zp44 suivante'`, { what: 'suivante sur le dessus' });
    await elapse(600);                             // (au-delà de SORT_GAP compté depuis le tri)
    const shown = seenThenNo('zp44 suivante');
    await h.release();                             // l'image arrive
    assert.equal(await shown, false, '✕ 0,12 s après l\'affichage de la suivante');
  } finally {
    await h.release();
  }
  await elapse(300);
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding`, { what: '✕ une fois la suivante vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('carte du dessus remplacée sans tri d\'ici (nouvelle image) : ✕ ignoré 0,3 s après son affichage', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding && ${TOP} === 'zp45 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

// la carte du dessus masquée par Dessiner (sous 1024 px) : Chrome retire le focus du ✕ qui l'avait, aucune touche
// n'atteint ✓ ni ✕ (le cas que craignait la revue du groupe E n'est pas atteignable ; si Chrome changeait, ce test
// tomberait)
test('carte du dessus masquée par Dessiner : ✕ perd le focus, Entrée ne trie rien', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('visionneuse : après Jeter, Jeter ignoré 0,3 s après l\'affichage de l\'image suivante, même arrivée tard',
  async () => {
    await page.waitFor(`!inPrivate()`, { what: 'espace public' });
    await page.emptyPile(bench);
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
      await page.eval(`sorts.length = 0; ${VIEWER_PRESS.discard}`);   // la suivante, son image retenue
      await page.waitFor(`vList.length === 1 && vList[vIndex]?.prompt === 'zp47 suivante'`,
        { what: 'visionneuse sur la suivante' });
      await elapse(600);                           // (au-delà de SORT_GAP compté depuis le Jeter)
      const again = page.eval(`(async () => { const t0 = Date.now();
        while (!posed($('vImg'))) {
          if (Date.now() - t0 > 20000) throw new Error('image suivante jamais affichée');
          await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
        await new Promise(r => setTimeout(r, 120));   // règle levée : Jeter 0,12 s après l'affichage, avant SORT_GAP
        ${VIEWER_PRESS.discard}; return [vIndex >= 0, sorts.length]; })()`);
      await h.release();                           // l'image arrive
      assert.deepEqual(await again, [true, 0], 'Jeter 0,12 s après l\'affichage de la suivante');
    } finally {
      await h.release();
    }
    await page.waitFor(`${VIEWER_SEEN}`, { what: 'image suivante vue 0,3 s' });
    await page.eval(`${VIEWER_PRESS.discard}`);  // vue 0,3 s : Jeter part (le premier Jeter envoyé)
    await page.waitFor(`vIndex < 0 && !!discarding && sorts.length === 1`, { what: 'Jeter une fois vue 0,3 s' });
    await page.closeViewer();
    await page.click('#undoBtn');
    await page.emptyPile(bench);
    page.assertNoErrors();
  });

test('carte arrivée sous la visionneuse : ✕ ignoré 0,3 s après la fin de son effacement', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
    ${PRESS.discard}; await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
    return !!discarding; })()`), false, '✕ 0,42 s après la fermeture de la visionneuse');
  await page.topShown();
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding && ${TOP} === 'zp48 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('carte arrivée hors de l\'écran (page défilée) : ✕ ignoré 0,3 s après son retour à l\'écran', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
      ${PRESS.discard}; await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
      return !!discarding; })()`), false, '✕ 0,12 s après le retour de la carte à l\'écran');
  } finally { await page.setView(PHONE); }
  await page.topShown();
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding && ${TOP} === 'zp49 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
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
  // règle levée : geste 0,12 s après le retour, avant SORT_GAP
  await new Promise(r => setTimeout(r, Math.max(0, 120 - (performance.now() - zqBack))));
  const late = Math.round(performance.now() - zqBack); ${act};
  await new Promise(r => setTimeout(r, 300));      // règle levée : au-delà de l'envol (0,22 s)
  return [late < SORT_GAP, ${state}]; })()`);

test('carte arrivée page cachée (autre onglet) : ✕ ignoré 0,3 s après le retour de la page', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
    assert.equal((await page.sortState()).topHeld, true, 'carte vue page cachée');
  });
  assert.deepEqual(await afterBack(`${PRESS.discard}`, `!!discarding`), [true, false],
    '✕ 0,12 s après le retour de la page');
  await page.topShown();
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding && ${TOP} === 'zp52 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

// page gelée ou en arrière-plan sans qu'aucun relevé du verrou ne tombe pendant l'absence (iOS gèle vite une appli
// quittée) : simulée par un fil de la page bloqué 0,6 s, minuteurs compris ; le premier relevé d'après ne compte pas
// le temps de l'absence
test('carte vue 0,1 s puis page gelée 0,6 s : ✕ ignoré dans les 0,3 s qui suivent la reprise', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
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
    ${PRESS.discard}; await new Promise(r => setTimeout(r, 300));   // règle levée : au-delà de l'envol (0,22 s)
    return !!discarding; })()`);
  await bench.idle({ page });
  await page.eval(`refreshStatus()`);
  assert.equal(await frozen, false, '✕ 0,08 s après la reprise d\'une page gelée');
  await page.topShown();
  await page.sort('discard', { ready: false });
  await page.waitFor(`!!discarding && ${TOP} === 'zp55 ancienne'`, { what: 'la nouvelle jetée une fois vue 0,3 s' });
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('carte déjà vue avant que la page passe derrière un autre onglet : ✕ la trie dès le retour', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
  await page.made('zp54 vue');
  await page.topShown();
  await behind(async () => {});
  // décision du porteur du 29/10/2026 (groupe G) : la même carte à l'écran au retour, sans nouveau verrou
  assert.deepEqual(await afterBack(`${PRESS.discard}`, `!!discarding`), [true, true],
    '✕ ignoré au retour sur une carte déjà vue');
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

test('visionneuse : image passée page cachée (autre onglet), Jeter ignoré 0,3 s après le retour', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
  await page.made('zp53 a');
  await page.made('zp53 b');
  await page.eval(`sorts.length = 0`);
  await page.viewPile('zp53 b');
  await behind(async () => {
    await page.eval(`stepViewer(1)`);              // (l'image suivante, montrée pendant que la page est cachée)
    await page.waitFor(`vList[vIndex]?.prompt === 'zp53 a' && posed($('vImg'))`,
      { what: 'image suivante posée, page cachée' });
    await elapse(2500);    // au-delà de SORT_GAP, même aux minuteurs ralentis d'une page cachée (une fois par seconde)
    assert.equal((await page.sortState()).sortHeld, true, 'image vue page cachée');
  });
  assert.deepEqual(await afterBack(`${VIEWER_PRESS.discard}`, `[vIndex >= 0, sorts.length, !!discarding]`),
    [true, [true, 0, false]], 'Jeter 0,12 s après le retour de la page');
  await page.waitFor(`${VIEWER_SEEN}`, { what: 'image vue 0,3 s' });
  await page.eval(`${VIEWER_PRESS.discard}`);
  await page.waitFor(`!!discarding`, { what: 'Jeter une fois vue 0,3 s' });
  await page.closeViewer();
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});

// Jeter dans la visionneuse 0,12 s après l'affichage de son image : renvoie [visionneuse ouverte, demandes envoyées,
// Jeter en attente]
const viewerSeenThenNo = () => page.eval(`(async () => { const t0 = Date.now();
  while (!posed($('vImg'))) {
    if (Date.now() - t0 > 20000) throw new Error('image de la visionneuse jamais affichée');
    await new Promise(r => setTimeout(r, 5)); }   // règle levée : sondage serré, l'instant de l'affichage compte
  await new Promise(r => setTimeout(r, 120));      // règle levée : Jeter 0,12 s après l'affichage, avant SORT_GAP
  ${VIEWER_PRESS.discard}; return [vIndex >= 0, sorts.length, !!discarding]; })()`);

test('visionneuse : Jeter ignoré dans les 0,3 s qui suivent l\'ouverture ou un pas (← →)', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  await page.emptyPile(bench);
  await page.made('zp50 a');
  await page.made('zp50 b');
  await page.eval(`sorts.length = 0`);
  await page.viewPile('zp50 b', { seen: false });
  assert.deepEqual(await viewerSeenThenNo(), [true, 0, false], 'Jeter 0,12 s après l\'ouverture');
  await page.waitFor(`${VIEWER_SEEN}`, { what: 'image vue 0,3 s' });
  await page.eval(`stepViewer(1)`);
  assert.deepEqual(await viewerSeenThenNo(), [true, 0, false], 'Jeter 0,12 s après un pas');
  assert.equal(await page.eval(`vList[vIndex].prompt`), 'zp50 a');
  await page.waitFor(`${VIEWER_SEEN}`, { what: 'image vue 0,3 s' });
  await page.eval(`${VIEWER_PRESS.discard}`);    // vue 0,3 s : Jeter part au bandeau
  await page.waitFor(`!!discarding`, { what: 'Jeter une fois vue 0,3 s' });
  await page.closeViewer();
  await page.click('#undoBtn');
  await page.emptyPile(bench);
  page.assertNoErrors();
});
