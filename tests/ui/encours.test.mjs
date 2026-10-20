// Page En cours, dans la vue du téléphone : onglets dans l'ordre En cours, Créer, Éditer, Dessiner, Galerie (ouverture
// sur Créer), « Générer » et la pastille du haut qui y mènent, pastille de l'onglet (nombre de la file de l'espace),
// génération en cours en grand (de la page, d'un autre appareil, ou cachée dans l'autre espace : « En attente »),
// « Rien en cours », et rien qui dépasse à 367 px.
//   node --test tests/ui/encours.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/encours.test.mjs)
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
// génération lancée hors de l'interface, comme depuis un autre appareil
async function launch(prompt, extra = {}) {
  const r = await post('/api/generate', { mode: 't2i', prompt, width: 512, height: 512, steps: 20, cfg: 1, seed: -1,
    preview: false, ref_images: [], ...extra });
  assert.equal(r.status, 202);
  return r.body;
}
const type = text => page.eval(`(() => { const t = $('t2i_prompt'); t.value = ${JSON.stringify(text)};
  t.dispatchEvent(new Event('input')); })()`);
const idle = () => page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`,
  { what: 'Mac au repos', timeout: 30000 });
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

test('onglets En cours, Créer, Éditer, Dessiner, Galerie ; ouverture sur Créer', async () => {
  assert.deepEqual(await page.eval(`[...$('tabbar').querySelectorAll('button')].map(b => b.dataset.pane)`),
    ['run', 't2i', 'edit', 'mask', 'hist']);
  assert.equal(await page.eval(`mode`), 't2i');
  assert.equal(await page.eval(`document.querySelector('#tabbar button.active').dataset.pane`), 't2i');
  assert.equal(await page.eval(`$('lens').style.transform`), 'translateX(100%)', 'lentille sous Créer');
  page.assertNoErrors();
});

test('rien en cours : « Rien en cours » et un bouton vers Créer ; la pastille ouvre le panneau Moteur', async () => {
  await page.click('#tabbar [data-pane="run"]');
  await page.waitFor(`mode === 'run' && $('pane-run').classList.contains('active')`, { what: 'page En cours' });
  assert.equal(await visible('#resultEmpty'), true);
  assert.match(await page.eval(`$('resultEmpty').textContent`), /Rien en cours/);
  assert.equal(await page.eval(`$('runCount').hidden`), true, 'pastille de l\'onglet cachée à zéro');
  await page.click('#resultEmpty button');
  await page.waitFor(`mode === 't2i'`, { what: 'retour sur Créer' });
  await page.click('#island');
  await page.waitFor(`$('engineSheet').classList.contains('on')`, { what: 'panneau Moteur' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

test('« Générer » mène à En cours ; pastille de l\'onglet et pastille du haut', async () => {
  await launch('HOLD=encours zq5 d\'un autre appareil', { width: 768, height: 512 });
  await type('zq5 de cette page');
  await page.click('#go');
  await page.waitFor(`mode === 'run' && pageJobs.some(isActive)`, { what: 'page En cours après « Générer »' });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('runCount').hidden && $('runCount').textContent === '2'`,
    { what: 'pastille de l\'onglet : 2' });
  // la génération d'un autre appareil tourne : en grand, avec son texte et ses réglages, cadre aux proportions
  // demandées, annulable (génération normale) ; anneau de l'onglet en route
  await page.waitFor(`$('pane-run').classList.contains('other')
    && $('nowPrompt').textContent.includes('zq5 d\\'un autre appareil')`,
    { what: 'génération de l\'autre appareil en haut de la page' });
  assert.equal(await page.eval(`$('nowSub').textContent`), 'Texte → image · 768×512 · 20 étapes');
  assert.equal(await page.eval(`getComputedStyle($('nowFrame')).aspectRatio`), '1.5 / 1');
  assert.equal(await visible('#nowCancel'), true);
  assert.notEqual(await page.eval(`$('runRing').style.strokeDashoffset`), '100');
  assert.equal(await visible('#stage'), false, 'zone de la page cachée');
  await page.click('#tabbar [data-pane="t2i"]');
  await page.click('#island');
  await page.waitFor(`mode === 'run'`, { what: 'pastille du haut : page En cours' });
  assert.deepEqual(await overflowing(), [], 'rien ne dépasse à 367 px');
  if (process.env.SHOT_DIR) await page.screenshot(process.env.SHOT_DIR + '/encours-autre.png');
  await cancelAll();
  bench.release('encours');
  await idle();
  page.assertNoErrors();
});

test('génération cachée de l\'autre espace : « En attente » et la durée avant la première de l\'espace', async () => {
  const exists = await page.eval(`privState.exists`);
  assert.equal((await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE })).status, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  const pub = await launch('HOLD=cachee zq5public');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'publique en cours' });
  await launch('zq5secret d\'un autre appareil', { private: true });
  await page.eval(`refreshStatus()`);
  await page.click('#tabbar [data-pane="run"]');
  await page.waitFor(`$('pane-run').classList.contains('other') && $('nowTitle').textContent === 'En attente'
    && $('nowEta').textContent.startsWith('≈')`, { what: '« En attente » et sa durée' });
  assert.doesNotMatch(await page.eval(`$('pane-run').innerText`), /zq5public/);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.doesNotMatch(await page.eval(`document.body.innerHTML`), /zq5secret/, 'rien de privé dans la page');
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  bench.release('cachee');
  await idle();                                    // la privée, sans HOLD, passe ensuite
  page.assertNoErrors();
});

test('génération incognito d\'un autre appareil : « Génération incognito », sans annulation', async () => {
  await launch('HOLD=autreincog zq5 incognito ailleurs', { incognito: true });
  await page.eval(`refreshStatus()`);
  await page.click('#tabbar [data-pane="run"]');
  await page.waitFor(`$('pane-run').classList.contains('other')
    && $('nowPrompt').textContent === 'Génération incognito'`,
    { what: 'génération incognito de l\'autre appareil en haut' });
  assert.doesNotMatch(await page.eval(`$('pane-run').innerText`), /zq5 incognito ailleurs/);
  assert.equal(await visible('#nowCancel'), false, 'seule sa page peut l\'annuler');
  // sa ligne de la file ne dit ni son mode ni ses réglages (seule sa page les connaît) : cadre carré, icône incognito
  assert.equal(await page.eval(`$('nowSub').textContent`), '');
  bench.release('autreincog');
  await idle();
  await page.waitFor(`!$('pane-run').classList.contains('other') && $('nowSub').textContent === ''`,
    { what: 'haut de la page rendu à la page, réglages vidés' });
  page.assertNoErrors();
});

test('une seconde génération de la page prend le haut d\'En cours quand elle démarre', async () => {
  for (const text of ['HOLD=premiere zq5 première', 'HOLD=seconde zq5 seconde']) {
    await page.click('#tabbar [data-pane="t2i"]');
    await type(text);
    await page.click('#go');
    await page.waitFor(`mode === 'run' && pageJobs.some(p => p.prompt === ${JSON.stringify(text)})`,
      { what: 'demande acceptée, page En cours' });
  }
  await page.waitFor(`shown && shown.prompt.endsWith('première') && shown.j.status === 'running'`,
    { what: 'la première en haut' });
  bench.release('premiere');
  await page.waitFor(`shown && shown.prompt.endsWith('seconde') && shown.j.status === 'running'
    && $('loader').style.display === 'flex'`, { what: 'la seconde en haut, avec sa progression' });
  bench.release('seconde');
  await page.waitFor(`!shown && $('doneList').textContent.includes('zq5 seconde')`,
    { what: 'la seconde dans les terminées' });
  page.assertNoErrors();
});

test('grand écran : Créer et En cours sont une colonne centrée', async () => {
  await page.send('Emulation.setDeviceMetricsOverride', { ...PHONE, width: 1280, mobile: false });
  for (const pane of ['t2i', 'run']) {
    await page.click(`#tabbar [data-pane="${pane}"]`);
    // largeur de la vue sans la barre de défilement : clientWidth
    const [left, width, right] = await page.eval(`(() => {
      const r = document.querySelector('main').getBoundingClientRect();
      return [r.left, r.width, document.documentElement.clientWidth - r.right]; })()`);
    assert.ok(width <= 640, `${pane} : colonne de ${width} px`);
    assert.ok(Math.abs(left - right) < 1, `${pane} : centrée (${left} / ${right})`);
  }
  await page.send('Emulation.setDeviceMetricsOverride', PHONE);
  page.assertNoErrors();
});
