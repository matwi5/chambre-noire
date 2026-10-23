// Labo et génération en cours, dans la vue du téléphone : deux onglets, Labo et Tirages (ouverture sur le Labo, qui
// réunit la génération en cours, la file, les images de la page et la saisie), la pastille du haut qui mène au Labo,
// génération en cours en grand en haut du Labo (de la page, d'un autre appareil, ou cachée dans l'autre espace :
// « En attente »), anneau de l'onglet, et rien qui dépasse à 367 px.
//   venv/bin/python tests/check.py --quick --ui tests/ui/encours.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, PHONE } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
});

after(async () => {
  bench?.release('encours');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)})
  .then(async r => ({ status: r.status, body: await r.json() }))`);
const cancelAll = () => page.eval(`fetch('/api/status').then(r => r.json())
  .then(s => Promise.all(s.queue.filter(e => e.id).map(e => postJson('/api/job/' + e.id + '/cancel', {}))))`);
const visible = sel => page.eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)});
  return !!el && !el.hidden && el.getClientRects().length > 0; })()`);
// éléments visibles qui dépassent de la largeur de la vue (boîtes mesurées) ; un élément rogné par un parent qui tient
// dans la vue (overflow hidden ou défilant : reflets animés, rangées qui défilent) ne dépasse pas
const overflowing = () => page.eval(`(() => {
  const out = r => r.left < -.5 || r.right > innerWidth + .5;
  const clipped = el => { for (let a = el.parentElement; a; a = a.parentElement)
    if (getComputedStyle(a).overflowX !== 'visible') return !out(a.getBoundingClientRect());
    return false; };
  return [...document.querySelectorAll('body *')]
    .filter(el => el.getClientRects().length && !el.closest('.sheet, .viewer, .toast, .ambient'))
    .filter(el => { const r = el.getBoundingClientRect(); return r.width && out(r) && !clipped(el); })
    .map(el => el.id || el.className || el.tagName); })()`);

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
  assert.deepEqual(await page.eval(`['stage', 'runNow', 'runQueue', 'pile', 'composer', 'refs', 'prompt']
    .filter(id => !$('pane-labo').contains($(id)))`), []);
  await page.tab('tirages');
  assert.equal(await page.eval(`$('pane-tirages').contains($('histGrid')) && document.body.className`), 'm-tirages');
  assert.equal(await page.eval(`$('lens').style.transform`), 'translateX(100%)', 'lentille sous les Tirages');
  await page.tab('labo');
  page.assertNoErrors();
});

test('glisser le doigt change d\'onglet hors du champ de création, jamais sur lui', async () => {
  await page.tab('labo');
  await page.swipe('#runZone', -160);
  await page.waitFor(`mode === 'tirages'`, { what: 'Tirages après un glissement vers la gauche' });
  await page.swipe('#pane-tirages', 160);
  await page.waitFor(`mode === 'labo'`, { what: 'Labo après un glissement vers la droite' });
  for (const sel of ['#prompt', '#refs']) {
    await page.swipe(sel, -160);
    assert.equal(await page.eval(`mode`), 'labo', `glissement sur ${sel} : onglet inchangé`);
  }
  page.assertNoErrors();
});

test('rien en cours : la pastille du haut ouvre le panneau Moteur', async () => {
  await page.tab('labo');
  assert.equal(await visible('#composer'), true, 'saisie dans le Labo');
  await page.click('#island');
  await page.waitFor(`$('engineSheet').classList.contains('on')`, { what: 'panneau Moteur' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('« Générer » reste sur le Labo ; génération d\'un autre appareil ; la pastille du haut mène au Labo', async () => {
  await page.launch('HOLD=encours zq5 d\'un autre appareil', { width: 768, height: 512 });
  await page.typePrompt('zq5 de cette page');
  await page.click('#go');
  await page.waitFor(`mode === 'labo' && pageJobs.some(isActive)`, { what: 'Labo après « Générer »' });
  await page.eval(`refreshStatus()`);
  // la génération d'un autre appareil tourne : en grand, avec son texte et ses réglages, cadre aux proportions
  // demandées, annulable (génération normale) ; anneau de l'onglet en route
  await page.waitFor(`$('runZone').classList.contains('other')
    && $('nowPrompt').textContent.includes('zq5 d\\'un autre appareil')`,
    { what: 'génération de l\'autre appareil en haut de la page' });
  assert.equal(await page.eval(`$('nowSub').textContent`), 'Texte → image · 768×512 · 20 étapes');
  assert.equal(await page.eval(`getComputedStyle($('nowFrame')).aspectRatio`), '1.5 / 1');
  assert.equal(await visible('#nowCancel'), true);
  assert.notEqual(await page.eval(`$('runRing').style.strokeDashoffset`), '100');
  assert.equal(await visible('#stage'), false, 'zone de la page cachée');
  await page.tab('tirages');
  await page.click('#island');
  await page.waitFor(`mode === 'labo'`, { what: 'pastille du haut : Labo' });
  assert.deepEqual(await overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/encours-autre.png');
  await cancelAll();
  bench.release('encours');
  await bench.idle();
  page.assertNoErrors();
});

test('génération cachée de l\'autre espace : « En attente » et la durée avant la première de l\'espace', async () => {
  const exists = await page.eval(`privState.exists`);
  assert.equal((await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE })).status, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  const pub = await page.launch('HOLD=cachee zq5public');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'publique en cours' });
  await page.launch('zq5secret d\'un autre appareil', { private: true });
  await page.eval(`refreshStatus()`);
  await page.tab('labo');
  await page.waitFor(`$('runZone').classList.contains('other') && $('nowTitle').textContent === 'En attente'
    && $('nowEta').textContent.startsWith('≈')`, { what: '« En attente » et sa durée' });
  assert.doesNotMatch(await page.eval(`$('runZone').innerText`), /zq5public/);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.doesNotMatch(await page.eval(`document.body.innerHTML`), /zq5secret/, 'rien de privé dans la page');
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  bench.release('cachee');
  await bench.idle();                                    // la privée, sans HOLD, passe ensuite
  page.assertNoErrors();
});

test('une seconde génération de la page prend le haut du Labo quand elle démarre', async () => {
  for (const text of ['HOLD=premiere zq5 première', 'HOLD=seconde zq5 seconde']) await page.generate(text);
  await page.waitFor(`shown && shown.prompt.endsWith('première') && shown.j.status === 'running'`,
    { what: 'la première en haut' });
  bench.release('premiere');
  await page.waitFor(`shown && shown.prompt.endsWith('seconde') && shown.j.status === 'running'
    && $('loader').style.display === 'flex'`, { what: 'la seconde en haut, avec sa progression' });
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
