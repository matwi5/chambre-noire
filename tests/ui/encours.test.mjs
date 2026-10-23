// Labo et carte en cours, dans la vue du téléphone : deux onglets, Labo et Tirages (ouverture sur le Labo, qui réunit
// la génération en cours, la pile et la saisie) ; la carte en cours (de la page, d'un autre appareil sans aperçu, ou
// cachée dans l'autre espace : « En attente ») sur le dessus quand la pile est vide, juste derrière sinon, non
// balayable, « Annuler » confirmé (« Déjà terminée » pour une génération finie pendant la question, « Mac
// injoignable » sans réponse) ; révélation en pixels (carrés au hasard, puis mosaïque des aperçus, immobile si le
// système réduit les animations, canevas vidé à la sortie de l'espace) ; « +N en attente » ; anneau de l'onglet ; rien
// qui dépasse à 367 px.
//   venv/bin/python tests/check.py --quick --ui tests/ui/encours.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, PHONE, waitUntil } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
});

after(async () => {
  for (const name of ['dessus', 'balaye', 'derriere', 'fin', 'sansmac']) bench?.release(name);
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)})
  .then(async r => ({ status: r.status, body: await r.json() }))`);
const cancelAll = () => page.eval(`fetch('/api/status').then(r => r.json())
  .then(s => Promise.all(s.queue.filter(e => e.id).map(e => postJson('/api/job/' + e.id + '/cancel', {}))))`);

test('deux onglets, Labo et Tirages ; ouverture sur le Labo ; plus de page En cours, Créer ni Galerie', async () => {
  assert.deepEqual(await page.eval(`[...$('tabbar').querySelectorAll('button')].map(b => b.dataset.pane)`),
    ['labo', 'tirages']);
  assert.deepEqual(await page.eval(`[...$('tabbar').querySelectorAll('button')].map(b => b.textContent.trim())`),
    ['Labo', 'Tirages']);
  assert.equal(await page.eval(`mode`), 'labo');
  assert.equal(await page.eval(`document.querySelector('#tabbar button.active').dataset.pane`), 'labo');
  assert.equal(await page.eval(`$('lens').style.transform`), 'translateX(0%)', 'lentille sous le Labo');
  assert.deepEqual(await page.eval(`['pane-run', 'pane-create', 'pane-hist'].filter(id => $(id))`), []);
  // icônes en pixels : dessinées sans lissage, sur une grille
  assert.deepEqual(await page.eval(`[...$('tabbar').querySelectorAll('svg.pix')]
    .map(s => s.getAttribute('shape-rendering'))`), ['crispEdges', 'crispEdges']);
  // la génération, la file, les images de la page et la saisie sont toutes dans le Labo
  assert.deepEqual(await page.eval(`['runCard', 'queueChip', 'pile', 'composer', 'refs', 'prompt']
    .filter(id => !$('pane-labo').contains($(id)))`), []);
  await page.tab('tirages');
  assert.equal(await page.eval(`$('pane-tirages').contains($('histGrid')) && document.body.className`), 'm-tirages');
  assert.equal(await page.eval(`$('lens').style.transform`), 'translateX(100%)', 'lentille sous les Tirages');
  await page.tab('labo');
  page.assertNoErrors();
});

test('glisser le doigt change d\'onglet hors du champ de création, jamais sur lui', async () => {
  await page.tab('labo');
  await page.swipe('#pileEmpty', -160);
  await page.waitFor(`mode === 'tirages'`, { what: 'Tirages après un glissement vers la gauche' });
  await page.swipe('#pane-tirages', 160);
  await page.waitFor(`mode === 'labo'`, { what: 'Labo après un glissement vers la droite' });
  for (const sel of ['#prompt', '#refs']) {
    await page.swipe(sel, -160);
    assert.equal(await page.eval(`mode`), 'labo', `glissement sur ${sel} : onglet inchangé`);
  }
  page.assertNoErrors();
});

test('rien en cours : pas de carte en cours ; l\'état du moteur ouvre son panneau', async () => {
  await page.tab('labo');
  assert.deepEqual(await page.eval(`[$('runCard').hidden, $('queueChip').hidden]`), [true, true]);
  assert.equal(await page.visible('#pileEmpty'), true, 'pile vide : l\'état vide');
  await page.click('#statusChip');
  await page.waitFor(`$('engineSheet').classList.contains('on')`, { what: 'panneau Moteur' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('carte d\'un autre appareil : texte, réglages, sans aperçu ; « +N en attente » ouvre la file', async () => {
  // lente, avec des aperçus, lancée ailleurs : la page n'en montre aucun
  const away = await page.launch('SLOW=0.3 zq5 d\'un autre appareil', { width: 768, height: 512, preview: true,
    preview_interval: 5 });
  await page.generate('zq5 de cette page');
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('runCard').hidden && $('runPrompt').textContent.includes('zq5 d\\'un autre appareil')`,
    { what: 'génération de l\'autre appareil sur la carte' });
  assert.equal(await page.eval(`shown`), null, 'pas une génération de la page');
  assert.equal(await page.eval(`$('runPhase').textContent`), 'Texte → image · 768×512 · 20 étapes');
  assert.match(await page.eval(`$('runEta').textContent`), /^fin vers \d+ h \d\d$/);
  assert.equal(await page.eval(`getComputedStyle($('runFrame')).aspectRatio`), '1.5 / 1');
  assert.equal(await page.visible('#runCancel'), true);
  assert.equal(await page.eval(`$('runCard').classList.contains('behind')`), false, 'pile vide : sur le dessus');
  assert.notEqual(await page.eval(`$('runRing').style.strokeDashoffset`), '100', 'anneau de l\'onglet en route');
  await page.waitFor(`fetch('/api/job/${away.id}').then(r => r.json()).then(j => j.preview_version > 0)`,
    { what: 'aperçus produits par le Mac' });
  await page.eval(`refreshStatus()`);
  assert.deepEqual(await page.eval(`[reveal.pv, !!reveal.img]`), [0, false], 'aperçu d\'un autre appareil montré');
  assert.equal(await page.eval(`$('queueChip').textContent`), '+1 en attente');
  assert.deepEqual(await page.overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/encours-autre.png');
  await page.click('#queueChip');
  await page.waitFor(`openedSheet === $('fileSheet') && $('queueList').textContent.includes('zq5 de cette page')`,
    { what: 'la file dans sa feuille' });
  await page.eval(`closeSheet()`);
  await cancelAll();
  await bench.idle({ page });
  page.assertNoErrors();
});

test('carte en cours : non balayable ; « Annuler » demande confirmation', async () => {
  await page.generate('HOLD=balaye zq5 à annuler');
  await page.waitFor(`shown && shown.j.status === 'running' && !$('runCard').hidden`, { what: 'carte en cours' });
  await page.swipe('#runFrame', 220);
  await page.swipe('#runFrame', -220);
  assert.deepEqual(await page.eval(`[mode, shown && shown.j.status]`), ['labo', 'running'], 'balayée ou onglet changé');
  await page.cancelRun(false);                      // refusée : elle continue
  await page.eval(`window.seenJob = shown.j`);      // un suivi de plus (pollJobs, chaque seconde) : toujours en cours
  await page.waitFor(`shown && shown.j !== seenJob`, { what: 'suivi suivant' });
  assert.equal(await page.eval(`shown.j.status`), 'running', 'annulée malgré le refus');
  await page.cancelRun();
  await page.waitFor(`!pageJobs.some(isActive) && $('runCard').hidden`, { what: 'génération annulée, carte partie' });
  bench.release('balaye');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('« Annuler » d\'une génération finie pendant la question : « Déjà terminée », rien d\'annulé', async () => {
  await page.generate('HOLD=fin zq5 finie pendant la question');
  await page.waitFor(`shown && shown.j.status === 'running' && !$('runCard').hidden`, { what: 'carte en cours' });
  const id = await page.eval(`$('runCancel').dataset.id`);
  // le suivi de la page est retenu : la carte montre encore la génération quand la réponse part
  await page.holdFetch(`u => u === '/api/status' || u.startsWith('/api/job/') && !u.endsWith('/cancel')`);
  try {
    await page.click('#runCancel');
    await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation' });
    bench.release('fin');
    await waitUntil(async () => (await bench.api('/api/job/' + id)).status === 'done', { what: 'finie sur le Mac' });
    assert.equal(await page.eval(`$('runCancel').dataset.id`), id, 'la carte a changé : le test ne vérifie rien');
    await page.eval(`$('toastBox').textContent = ''; answer(true)`);
    await page.waitFor(`$('toastBox').textContent === 'Déjà terminée'`, { what: 'message « Déjà terminée »' });
  } finally { bench.release('fin'); await page.releaseFetch(); }
  await bench.idle({ page });
  assert.equal((await bench.api('/api/job/' + id)).status, 'done', 'annulée après coup');
  await page.keepPile();
  page.assertNoErrors();
});

test('« Annuler » sans réponse du Mac : « Mac injoignable », la génération continue', async () => {
  await page.generate('HOLD=sansmac zq5 à annuler sans Mac');
  await page.waitFor(`shown && shown.j.status === 'running' && !$('runCard').hidden`, { what: 'carte en cours' });
  const id = await page.eval(`$('runCancel').dataset.id`);
  await page.eval(`(() => { const f = window.fetch; window.fetch = (u, ...a) => String(u).endsWith('/cancel')
    ? (window.fetch = f, Promise.reject(new TypeError('Failed to fetch'))) : f(u, ...a); })()`);
  await page.eval(`$('toastBox').textContent = ''`);
  await page.cancelRun();
  await page.waitFor(`$('toastBox').textContent === 'Mac injoignable'`, { what: 'message « Mac injoignable »' });
  assert.equal((await bench.api('/api/job/' + id)).status, 'running', 'annulée sans réponse');
  await page.cancelRun();                          // le Mac répond de nouveau : annulée
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'annulée' });
  bench.release('sansmac');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('révélation : carrés au hasard, puis chaque aperçu en mosaïque de plus en plus fine', async () => {
  await page.eval(`opt.steps = 'high'; opt.res = 'low'; $('previewChk').checked = true; saveOpt(); refreshChoices()`);
  await page.generate('SLOW=0.3 zq5 révélée');
  await page.waitFor(`shown && !$('runCard').hidden && reveal.key && !!reveal.timer`, { what: 'carrés au hasard' });
  assert.ok((await page.canvasInk('#revealCanvas')).ink > 0, 'aucun carré allumé');
  await page.waitFor(`!!reveal.img`, { what: 'premier aperçu', timeout: 30000 });
  const first = await page.eval(`reveal.frac`);
  await page.waitFor(`reveal.frac > ${first}`, { what: 'aperçu suivant, plus fin', timeout: 30000 });
  const ink = await page.canvasInk('#revealCanvas');
  assert.ok(ink.width > 0 && ink.ink === ink.width * ink.height, `mosaïque pleine : ${JSON.stringify(ink)}`);
  await bench.idle({ page });
  await page.waitFor(`$('runCard').hidden && pileItems.some(it => it.prompt === 'SLOW=0.3 zq5 révélée')`,
    { what: 'image nette dans la pile' });
  assert.equal(await page.eval(`$('revealCanvas').width`), 0, 'canevas vidé');
  // système qui réduit les animations : les carrés ne bougent plus
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  await page.eval(`opt.steps = 'low'; saveOpt(); refreshChoices()`);
  await page.generate('HOLD=dessus zq5 immobile');
  await page.waitFor(`shown && !$('runCard').hidden`, { what: 'carte en cours' });
  assert.equal(await page.eval(`reveal.timer`), null, 'carrés animés malgré la réduction des animations');
  await page.send('Emulation.setEmulatedMedia', { features: [] });
  bench.release('dessus');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('pile non vide : la carte en cours passe juste derrière, au bord de la pile', async () => {
  await page.waitFor(`pileSize() > 0`, { what: 'images dans la pile' });
  await page.generate('HOLD=derriere zq5 derrière');
  await page.waitFor(`!$('runCard').hidden && $('runCard').classList.contains('behind')`, { what: 'carte derrière' });
  const [pile, card] = await page.eval(`[$('pile').getBoundingClientRect().bottom,
    $('runCard').getBoundingClientRect().top]`);
  assert.ok(card >= pile - 30 && card <= pile + 30, `au bord de la pile (${pile} / ${card})`);
  assert.equal(await page.visible('#runEta'), true, 'fin prévue');
  assert.deepEqual(await page.overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/encours-derriere.png');
  bench.release('derriere');
  await bench.idle({ page });
  await page.keepPile();
  page.assertNoErrors();
});

test('derrière une génération cachée de l\'autre espace : « En attente » ; rien de privé à la sortie', async () => {
  const exists = await page.eval(`privState.exists`);
  assert.equal((await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE })).status, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  const pub = await page.launch('HOLD=cachee zq5public');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'publique en cours' });
  await page.launch('zq5secret d\'un autre appareil', { private: true });
  await page.eval(`refreshStatus()`);
  await page.tab('labo');
  // la privée (suivie par la page, qui adopte les générations privées) attend derrière la publique, cachée
  await page.waitFor(`!$('runCard').hidden && $('runStep').textContent === 'En attente'
    && /^fin vers \\d+ h \\d\\d$/.test($('runEta').textContent)`, { what: '« En attente » et son heure' });
  assert.doesNotMatch(await page.eval(`$('runCard').innerText`), /zq5public/);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.doesNotMatch(await page.eval(`document.body.innerHTML`), /zq5secret/, 'rien de privé dans la page');
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  bench.release('cachee');
  await bench.idle();                                    // la privée, sans HOLD, passe ensuite
  page.assertNoErrors();
});

test('une seconde génération de la page passe sur la carte en cours quand elle démarre', async () => {
  for (const text of ['HOLD=premiere zq5 première', 'HOLD=seconde zq5 seconde']) await page.generate(text);
  await page.waitFor(`shown && shown.prompt.endsWith('première') && shown.j.status === 'running'`,
    { what: 'la première sur la carte' });
  bench.release('premiere');
  await page.waitFor(`shown && shown.prompt.endsWith('seconde') && shown.j.status === 'running'
    && !$('runCard').hidden`, { what: 'la seconde sur la carte en cours' });
  bench.release('seconde');
  await page.waitFor(`!shown && pileItems.some(it => it.prompt.endsWith('zq5 seconde'))`,
    { what: 'la seconde dans la pile' });
  page.assertNoErrors();
});

test('grand écran : le Labo est une colonne centrée, les Tirages prennent la largeur', async () => {
  await page.send('Emulation.setDeviceMetricsOverride', { ...PHONE, width: 1280, mobile: false });
  // largeur de la vue sans la barre de défilement : clientWidth
  const column = () => page.eval(`(() => { const r = document.querySelector('main').getBoundingClientRect();
    return [r.left, r.width, document.documentElement.clientWidth - r.right]; })()`);
  await page.tab('labo');
  const [left, width, right] = await column();
  assert.ok(width <= 640, `Labo : colonne de ${width} px`);
  assert.ok(Math.abs(left - right) < 1, `Labo : centré (${left} / ${right})`);
  await page.tab('tirages');
  assert.ok((await column())[1] > 640, 'Tirages : toute la largeur');
  await page.tab('labo');
  await page.send('Emulation.setDeviceMetricsOverride', PHONE);
  page.assertNoErrors();
});
