// Estimations par modèle (ticket 06 de MiniMax H3), dans la vue du téléphone : la page calcule l'estimation du modèle
// choisi avec la même formule que le serveur (parts, refPx contre estimate.predict, ref_px), sur des demandes de chaque
// modèle lues dans la file du Mac ; devant un serveur sans coefficients par modèle, ceux de Qwen.
//   venv/bin/python tests/check.py --quick --ui tests/ui/estimations.test.mjs
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
  bench?.release('estime-ui');
  await chrome?.close();
  await bench?.stop();
});

// image de 64×48 (data URL), dessinée dans la page
const IMAGE = `(() => { const c = document.createElement('canvas'); c.width = 64; c.height = 48;
  return c.toDataURL('image/png'); })()`;
// demandes de chaque modèle : [prompt, champs, w, h, étapes, références, aperçu]
const CASES = [
  ['zet1 qwen texte', `steps: 8, preview: true`, 512, 512, 8, 0, true],
  ['zet1 qwen edition', `width: 768, height: 512, mode: 'edit', ref_images: [${IMAGE}]`, 768, 512, 8, 1, false],
  ['zet1 h3 texte', `model: 'h3', steps: 6, width: 1024, height: 1024, preview: true`, 1024, 1024, 6, 0, true],
  ['zet1 h3 edition', `model: 'h3', steps: 6, mode: 'edit', ref_images: [${IMAGE}, ${IMAGE}]`, 512, 512, 6, 2, false],
];

test('la page estime chaque modèle comme le serveur, demande par demande', async () => {
  await page.freshLabo(bench);
  await page.modelsSeen(2);
  assert.equal(await page.postGenerate(`{ prompt: 'HOLD=estime-ui zet1 tourne' }`), 202);
  for (const [prompt, fields] of CASES) {
    assert.equal(await page.postGenerate(`{ prompt: '${prompt}', ${fields} }`), 202, prompt);
  }
  const queue = (await bench.api('/api/status')).queue;
  for (const [prompt, , w, h, steps, refs, preview] of CASES) {
    const key = prompt.includes('h3') ? 'h3' : 'qwen';
    const server = queue.find(e => e.prompt === prompt).estimate;
    const mine = await page.eval(`(c => parts(${w}, ${h}, ${steps},
      { refs: Array(${refs}).fill(refPx(64, 48, ${w}, ${h}, c.rmin || 0)), init: 0 }, ${preview},
      ${key === 'h3' ? 2 : 5}, c).total)(coefsOf('${key}'))`);
    assert.ok(Math.abs(mine - server) < 0.1, `${prompt} : page ${mine}, serveur ${server}`);
  }
  assert.notDeepEqual(await page.eval(`coefsOf('h3')`), await page.eval(`coefsOf('qwen')`), 'mêmes coefficients');
  bench.release('estime-ui');
  await bench.idle({ page });
  page.assertNoErrors();
});

test('le modèle choisi donne ses coefficients à l\'estimation affichée ; ancien serveur : ceux de Qwen', async () => {
  await page.freshLabo(bench);
  await page.modelsSeen(2);
  await page.pasteImage();
  await page.waitFor(`inputImages.length === 1`, { what: 'une image jointe' });
  const shown = () => page.eval(`[estSeconds, (() => { const [w, h] = currentDims(), c = coefsOf(modelSel().key);
    return parts(w, h, chosenSteps(), { refs: [refPx(64, 64, w, h, c.rmin || 0)], init: 0 },
      $('previewChk').checked, previewEvery(), c).total; })()]`);
  const [qwen, qwenParts] = await shown();
  assert.ok(Math.abs(qwen - qwenParts) < 1e-6);
  await page.chooseModel('h3');
  const [h3, h3Parts] = await shown();
  assert.ok(Math.abs(h3 - h3Parts) < 1e-6);
  assert.ok(h3 > qwen, `MiniMax H3 (${h3} s) estimé sans sa lecture d'image (Qwen : ${qwen} s)`);
  await page.oldServer();
  assert.deepEqual(await page.eval(`[EM, coefsOf('h3') === E]`), [null, true]);
  page.assertNoErrors();
});
