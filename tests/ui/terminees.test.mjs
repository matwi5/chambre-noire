// Terminées de la page En cours, dans la vue du téléphone : sous la file, les générations finies de la page, la plus
// récente en premier (lot en grille, échec avec son message, annulée absente), leurs actions (visionneuse, Télécharger,
// Éditer, Dessiner, Supprimer), « × » et « Tout retirer » (sans confirmation : les images restent sur le Mac),
// plafond de 12, liste vide au rechargement, vrai mode et images d'entrée de chaque image, et le
// message « Image prête » ou « Lot prêt » quand on est ailleurs dans l'application.
//   venv/bin/python tests/check.py --quick --ui tests/ui/terminees.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.eval(`opt.steps = 'low'; opt.res = 'low'; saveOpt(); refreshChoices()`);   // générations courtes
});

after(async () => {
  bench?.release('termine');
  await chrome?.close();
  await bench?.stop();
});

const cards = () => page.eval(`[...$('doneList').children].map(c => c.textContent)`);
const watchToasts = () => page.eval(`(() => { window.seenToasts = []; window.toastWatch?.disconnect();
  window.toastWatch = new MutationObserver(() => seenToasts.push($('toastBox').textContent));
  toastWatch.observe($('toastBox'), { childList: true, characterData: true, subtree: true }); })()`);
const visible = sel => page.eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)});
  return !!el && !el.hidden && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0; })()`);
// éléments visibles qui dépassent de la largeur de la vue, hors éléments rognés par un parent qui tient dans la vue
const overflowing = () => page.eval(`(() => {
  const out = r => r.left < -.5 || r.right > innerWidth + .5;
  const clipped = el => { for (let a = el.parentElement; a; a = a.parentElement)
    if (getComputedStyle(a).overflowX !== 'visible') return !out(a.getBoundingClientRect());
    return false; };
  return [...document.querySelectorAll('body *')]
    .filter(el => el.getClientRects().length && !el.closest('.sheet, .viewer, .toast, .ambient'))
    .filter(el => { const r = el.getBoundingClientRect(); return r.width && out(r) && !clipped(el); })
    .map(el => el.id || el.className || el.tagName); })()`);
async function clearAll() {
  if (await page.eval(`!$('doneClear') || $('doneClear').closest('[hidden]')`)) return;
  await page.click('#doneClear');
  await page.waitFor(`$('doneList').children.length === 0`, { what: 'liste vidée' });
}

test('une image finie : carte sous la file, visionneuse d\'un appui, « × » la retire sans la supprimer', async () => {
  await page.generate('zq4 un phare');
  await page.waitFor(`$('doneList').children.length === 1 && $('doneList').querySelector('img').naturalWidth > 0`,
    { what: 'carte de l\'image finie' });
  assert.match((await cards())[0], /zq4 un phare/);
  assert.equal(await visible('#resultEmpty'), false, 'pas « Rien en cours » avec une terminée');
  assert.equal(await visible('#stage'), false, 'rien ne tourne : le haut de la page est vide');
  const name = await page.eval(`pageJobs[0].result.name`);
  assert.equal(await page.eval(`$('doneList').querySelector('a[download]').getAttribute('download')`), name);
  await page.click('#doneList [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && vList.length === 1`, { what: 'visionneuse' });
  assert.equal(await page.eval(`vList[0].mode`), 't2i');
  await page.eval(`closeViewer()`);
  await page.click('#doneList [data-remove]');
  await page.waitFor(`$('doneList').children.length === 0 && pageJobs.length === 0`, { what: 'carte retirée' });
  assert.equal(await visible('#resultEmpty'), true, '« Rien en cours » de nouveau');
  assert.ok(await page.eval(`fetch('/api/pile').then(r => r.json())
    .then(h => h.some(it => it.name === ${JSON.stringify(name)}))`),
    'toujours dans la pile');
  await page.waitFor(`!document.querySelector('[href*="${name}"]')`,
    { what: 'plus de lien vers elle (visionneuse vidée)' });
  page.assertNoErrors();
});

test('échec : carte avec le message du Mac ; annulée : absente', async () => {
  await page.generate('FAIL zq4 échec');
  await page.waitFor(`$('doneList').querySelector('.fail')`, { what: 'carte de l\'échec' });
  assert.match(await page.eval(`$('doneList').querySelector('.fail').textContent`), /zq4 échec/);
  assert.match(await page.eval(`$('doneList').querySelector('.fail .dmeta.err').textContent`), /^Échec : /);
  await page.generate('HOLD=termine zq4 annulée');
  await page.waitFor(`shown && shown.j.status === 'running'`, { what: 'génération en cours' });
  await page.click('#cancelLoader');
  bench.release('termine');
  await bench.idle({ page });
  assert.equal(await page.eval(`$('doneList').children.length`), 1, 'seul l\'échec');
  assert.doesNotMatch((await cards()).join(), /annulée/);
  await clearAll();
  page.assertNoErrors();
});

test('ailleurs : « Image prête » mène à En cours ; lot en grille, « Lot prêt » avec ses échecs', async () => {
  await watchToasts();
  await page.generate('HOLD=pret zq4 depuis Créer');
  await page.click('#tabbar [data-pane="create"]');
  bench.release('pret');                           // elle finit pendant qu'on est sur Créer
  await page.waitFor(`seenToasts.includes('Image prête')`, { what: 'message « Image prête »' });
  await page.click('#toastBox');
  await page.waitFor(`mode === 'run'`, { what: 'page En cours après le message' });
  // lot de 3 variantes dont la deuxième échoue (graines 20, 21, 22 ; le faux moteur échoue sur la graine 21)
  await page.eval(`opt.count = 3; saveOpt(); refreshChoices();
    window.realBuild = window.realBuild || buildRequest; window.buildRequest = () => ({ ...realBuild(), seed: 20 })`);
  await page.generate('HOLD=lotpret FAILSEED=21 zq4 lot');
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices(); window.buildRequest = realBuild`);
  await page.click('#tabbar [data-pane="create"]');
  bench.release('lotpret');
  await page.waitFor(`seenToasts.some(t => t.startsWith('Lot prêt'))`, { what: 'message du lot', timeout: 30000 });
  assert.deepEqual(await page.eval(`seenToasts.filter(t => /prêt|Échec/.test(t))`),
    ['Image prête', 'Lot prêt · 2 images, 1 en échec']);
  await page.click('#tabbar [data-pane="run"]');
  const lot = `$('doneList').querySelector('.dlot')`;
  assert.equal(await page.eval(`${lot}.querySelectorAll('[data-open]').length`), 2, 'deux images dans la grille');
  assert.equal(await page.eval(`${lot}.querySelectorAll('.cell.fail').length`), 1, 'une case pour l\'échec');
  assert.match(await page.eval(`${lot}.textContent`), /3 variantes/);
  assert.equal(await page.eval(`$('doneList').children[0] === ${lot}`), true, 'la plus récente en premier');
  await page.click('#doneList .dlot [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on') && vList[vIndex].lot`, { what: 'image du lot en grand' });
  assert.equal(await visible('#vKeep'), true, '« Garder celle-ci » pour des variantes');
  await page.eval(`closeViewer()`);
  assert.deepEqual(await overflowing(), [], 'rien ne dépasse à 367 px');
  await clearAll();
  page.assertNoErrors();
});

test('« Tout retirer » : la liste se vide sans confirmation, l\'image reste dans la pile', async () => {
  await page.generate('zq4 retiree');
  await page.waitFor(`$('doneList').children.length === 1 && !pageJobs.some(isActive)`, { what: 'image finie' });
  await page.click('#doneClear');
  await page.waitFor(`$('doneList').children.length === 0 && !pageJobs.length`, { what: 'liste vidée' });
  assert.equal(await page.eval(`openedSheet`), null, 'aucune confirmation');
  assert.ok(await page.eval(`fetch('/api/pile').then(r => r.json())
    .then(h => h.some(it => it.prompt === 'zq4 retiree'))`), 'image dans la pile');
  page.assertNoErrors();
});

test('plafond : 12 terminées, la plus ancienne sort d\'elle-même', async () => {
  for (let k = 1; k <= 13; k++) { await page.generate(`zq4 image ${k}`); await bench.idle({ page }); }
  const prompts = () => page.eval(`[...$('doneList').querySelectorAll('.dprompt')].map(x => x.textContent)`);
  await page.waitFor(`$('doneList').children.length === 12`, { what: 'douze images' });
  assert.deepEqual((await prompts()).filter(t => t.startsWith('zq4 image')),
    Array.from({ length: 12 }, (_, i) => `zq4 image ${13 - i}`), 'la plus récente en premier, l\'image 1 sortie');
  await clearAll();
  page.assertNoErrors();
});

test('vrai mode et images d\'entrée : une édition à deux références les montre toutes', async () => {
  await page.click('#tabbar [data-pane="create"]');
  await page.eval(`(async () => { for (const c of ['#a03070', '#30a070']) {
    const cv = document.createElement('canvas'); cv.width = cv.height = 256; const x = cv.getContext('2d');
    x.fillStyle = c; x.fillRect(0, 0, 256, 256);
    inputImages.push(await toEntry(c + '.png', cv.toDataURL('image/png'))); }
    renderInputs(); })()`);
  await page.generate('zq4 édition');
  await page.waitFor(`$('doneList').children.length === 1 && !pageJobs.some(isActive)`, { what: 'édition finie' });
  await page.click('#doneList [data-open]');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse' });
  assert.equal(await page.eval(`vList[0].mode`), 'edit');
  assert.deepEqual(await page.eval(`vList[0].inputs`), ['ref_1.png', 'ref_2.png']);
  assert.match(await page.eval(`$('vInputs').textContent`), /2 images d'entrée/);
  await page.eval(`closeViewer()`);
  await clearAll();
  page.assertNoErrors();
});

test('rechargement : la liste repart vide', async () => {
  await page.generate('zq4 avant rechargement');
  await page.waitFor(`$('doneList').children.length === 1`, { what: 'une terminée' });
  await bench.idle();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.click('#tabbar [data-pane="run"]');
  assert.equal(await page.eval(`$('doneList').children.length`), 0);
  assert.equal(await visible('#resultEmpty'), true);
  page.assertNoErrors();
});
