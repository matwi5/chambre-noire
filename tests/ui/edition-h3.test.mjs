// Édition avec MiniMax H3 depuis la page (ticket 05), dans la vue du téléphone : aide des images en <Picture N> dès
// une image jointe (celle de Qwen inchangée), mention du temps et du rendu suivie de l'estimation du moment,
// « Dessiner » grisé (et refusé depuis une image), lots, campagnes et confirmation au-delà d'une heure permis.
//   venv/bin/python tests/check.py --quick --ui tests/ui/edition-h3.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  bench.h3();
  chrome = await launchChrome();
  page = await chrome.phonePage();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const MENTION = 'Avec MiniMax H3, chaque image jointe allonge beaucoup le calcul, et le rendu sort plus dur '
  + 'qu\'avec Qwen.';
// Labo neuf, deux modèles lus, Qwen choisi
async function freshH3() {
  await page.freshLabo(bench);
  await page.modelsSeen(2);
}
// n images de plus collées dans la saisie
async function images(n) {
  const had = await page.eval(`inputImages.length`);
  for (let k = 0; k < n; k++) await page.pasteImage();
  await page.waitFor(`inputImages.length === ${had + n}`, { what: `${n} image(s) de plus jointe(s)` });
}
const hint = () => page.eval(`$('refHint').hidden ? null : $('refHint').textContent`);
const note = () => page.eval(`$('h3Note').hidden ? null : $('h3Note').textContent`);

test('aide des images : <Picture N> avec MiniMax H3 dès une image ; celle de Qwen inchangée', async () => {
  await freshH3();
  await images(1);
  assert.equal(await hint(), null, 'aide de Qwen avec une seule image');
  await images(1);
  assert.match(await hint(), /image 1 wears the jacket from image 2/, 'aide de Qwen changée');
  await page.chooseModel('h3');
  assert.match(await hint(), /<Picture 1>, <Picture 2>/);
  await page.eval(`inputImages.splice(1); renderInputs(); refreshChoices()`);
  assert.match(await hint(), /<Picture 1>/, 'aide absente avec une seule image et MiniMax H3');
  await page.eval(`inputImages.length = 0; renderInputs(); refreshChoices()`);
  assert.equal(await hint(), null, 'aide sans image jointe');
  page.assertNoErrors();
});

test('mention du temps et du rendu dès une image avec MiniMax H3, suivie de l\'estimation du moment', async () => {
  await freshH3();
  await page.chooseModel('h3');
  assert.equal(await note(), null, 'mention sans image jointe');
  await images(1);
  const one = await note();
  assert.equal(one, `${MENTION} Temps estimé : ${await page.eval(`'≈ ' + fmt(estSeconds)`)}.`);
  await page.eval(`opt.res = 'max'; saveOpt(); refreshChoices()`);
  const big = await note();
  assert.equal(big, `${MENTION} Temps estimé : ${await page.eval(`'≈ ' + fmt(estSeconds)`)}.`);
  assert.notEqual(big, one, 'estimation de la mention écrite en dur');
  await page.chooseModel('qwen');
  assert.equal(await note(), null, 'mention avec Qwen');
  page.assertNoErrors();
});

test('« Dessiner » grisé avec MiniMax H3, éteint au changement de modèle, refusé depuis une image', async () => {
  await freshH3();
  await images(1);
  await page.click('#drawBtn');
  await page.waitFor(`drawOn`, { what: 'dessin actif avec Qwen' });
  await page.chooseModel('h3');
  assert.deepEqual(await page.eval(`[drawOn, $('drawBtn').disabled, $('drawHint').textContent]`),
    [false, true, 'Dessiner se fait avec Qwen']);
  assert.equal(await page.eval(`$('composer').classList.contains('drawing')`), false, 'zone de dessin restée');
  await page.watchToasts();
  await page.eval(`drawFrom('autre.png', () => Promise.resolve(inputImages[0].dataUrl))`);
  assert.equal(await page.eval(`inputImages.length === 1 && !drawOn`), true, 'Dessiner d\'une image passé outre');
  assert.match((await page.eval(`seenToasts`)).join('|'), /Dessiner se fait avec Qwen/);
  await page.chooseModel('qwen');
  assert.deepEqual(await page.eval(`[$('drawBtn').disabled, $('drawHint').textContent]`), [false, '']);
  page.assertNoErrors();
});

test('MiniMax H3 : lot de variantes, campagne et confirmation au-delà d\'une heure', async () => {
  await freshH3();
  await page.chooseModel('h3');
  await images(1);
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices()`);
  await page.generate('zeh4 lot');
  assert.deepEqual(await page.eval(`(r => [r.model, r.mode, r.count, r.ref_images.length])(pageJobs.at(-1).req)`),
    ['h3', 'edit', 2, 1]);
  await bench.idle({ page });
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);
  await images(2);
  await page.eval(`$('campChk').click()`);
  await page.waitFor(`inCampaign()`, { what: 'campagne active' });
  await page.generate('zeh4 campagne');
  assert.deepEqual(await page.eval(`(r => [r.model, r.campaign.length])(pageJobs.at(-1).req)`), ['h3', 2]);
  await bench.idle({ page });
  // demande de plus d'une heure (estimation du moment) : confirmée avant de partir
  await page.eval(`campaignOn = false; $('campChk').checked = false; opt.res = 'max'; opt.count = 4; saveOpt();
    renderInputs(); refreshChoices()`);
  await images(2);
  assert.equal(await page.eval(`estSeconds > 3600`), true, 'demande de moins d\'une heure : cas pas atteint');
  const jobs = await page.eval(`pageJobs.length`);
  await page.typePrompt('zeh4 longue');
  await page.click('#go');
  await page.waitFor(`openedSheet === $('askSheet') && $('askTitle').textContent === 'Génération longue'`,
    { what: 'confirmation au-delà d\'une heure' });
  await page.eval(`answer(false)`);
  assert.equal(await page.eval(`pageJobs.length`), jobs, 'demande partie sans confirmation');
  page.assertNoErrors();
});
