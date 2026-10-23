// En-tête, dans la vue du téléphone : cadenas de l'espace privé aussi visible que Rafraîchir, état du moteur qui tient
// dans la barre sans recouvrir le nom.
//   venv/bin/python tests/check.py --quick --ui tests/ui/entete.test.mjs
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
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// apparence d'un bouton-icône : taille de l'icône, couleur et épaisseur de son trait, opacité du bouton et de l'icône
const look = selector => page.eval(`(() => { const b = document.querySelector(${JSON.stringify(selector)}), svg = b.querySelector('svg'),
  r = svg.getBoundingClientRect(), cs = getComputedStyle(svg), shape = getComputedStyle(svg.querySelector('path, rect'));
  return { width: r.width, height: r.height, color: cs.color, stroke: shape.strokeWidth,
    opacity: [getComputedStyle(b).opacity, cs.opacity] }; })()`);

test('Tirages : le cadenas de l\'espace privé est aussi visible que Rafraîchir', async () => {
  await page.tab('tirages');
  await page.waitFor(`!$('privEntry').hidden && !!$('privEntry').getClientRects().length`, { what: 'cadenas affiché' });
  const lock = await look('#privEntry'), refresh = await look('.hist-head button[onclick="loadHistory()"]');
  assert.deepEqual(lock, refresh);
  assert.deepEqual(lock.opacity, ['1', '1'], 'pleine opacité');
  await page.tab('labo');
  page.assertNoErrors();
});

// l'état du moteur dans la barre du haut, dans la vue et à droite du nom (boîtes mesurées)
test('en-tête : l\'état du moteur tient dans la barre, à côté du nom, pendant une génération', async () => {
  const held = await page.launch('HOLD=barre en cours');
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('status').textContent.startsWith('En cours')`, { what: 'moteur occupé' });
  const boxes = await page.eval(`['#statusChip', '.brand'].map(s => document.querySelector(s).getBoundingClientRect())
    .map(r => [r.left, r.right])`);
  assert.ok(boxes[0][1] <= await page.eval(`innerWidth`), 'l\'état du moteur dépasse');
  assert.ok(boxes[1][1] <= boxes[0][0] + .5, 'le nom passe sous l\'état du moteur');
  await page.eval(`postJson('/api/job/' + ${JSON.stringify(held.id)} + '/cancel', {})`);
  bench.release('barre');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`, { what: 'file vide' });
  page.assertNoErrors();
});
