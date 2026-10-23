// En-tête, dans la vue du téléphone : cadenas de l'espace privé aussi visible que Rafraîchir, pastille du haut qui
// tient dans sa bulle.
//   venv/bin/python tests/check.py --quick --ui tests/ui/entete.test.mjs
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

// éléments de la pastille qui dépassent de sa bulle (boîtes mesurées)
const overflowing = () => page.eval(`(() => { const r = $('island').getBoundingClientRect();
  return [...$('island').querySelectorAll('*')].filter(el => el.getClientRects().length).map(el => [el, el.getBoundingClientRect()])
    .filter(([, b]) => b.left < r.left - .5 || b.right > r.right + .5 || b.top < r.top - .5 || b.bottom > r.bottom + .5)
    .map(([el]) => el.id || el.tagName); })()`);
const more = () => page.eval(`$('islMore').textContent`);

test('pastille : tout son contenu tient dans la bulle, « +N » seul quand l\'écran est trop étroit', async () => {
  // une génération lente en cours (étape et durée affichées) et une en attente derrière elle
  for (const prompt of ['SLOW=0.5 en cours', 'SLOW=0.5 en attente'])
    await page.eval(`postJson('/api/generate', { mode: 't2i', prompt: ${JSON.stringify(prompt)}, width: 512, height: 512, steps: 40,
      cfg: 1, seed: -1, preview: false, ref_images: [] }).then(r => r.ok)`).then(ok => assert.ok(ok, 'demande acceptée'));
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('island').classList.contains('run') && $('islMore').textContent.startsWith('+1')`, { what: 'pastille avec une en attente' });
  await page.waitFor(`$('islEta').textContent !== ''`, { what: 'durée affichée' });
  assert.deepEqual(await overflowing(), [], 'vue du téléphone : rien ne dépasse');
  assert.equal(await more(), '+1', 'vue du téléphone : « +N » seul');
  // textes les plus longs que la pastille affiche (étape « Préparation », attente en heures, file à deux chiffres)
  await page.eval(`$('islStep').textContent = 'Préparation'; $('islEta').textContent = '≈ 1,5 h'; $('islMore').textContent = '+12'`);
  assert.deepEqual(await overflowing(), [], 'vue du téléphone, textes les plus longs : rien ne dépasse');

  await page.send('Emulation.setDeviceMetricsOverride', { ...PHONE, width: 1000, mobile: false });
  await page.eval(`renderIsland()`);
  assert.deepEqual(await overflowing(), [], 'grand écran : rien ne dépasse');
  assert.equal(await more(), '+1 en attente', 'grand écran : texte complet');
  await page.send('Emulation.setDeviceMetricsOverride', PHONE);

  await page.eval(`fetch('/api/status').then(r => r.json()).then(s => Promise.all(s.queue.map(e => postJson('/api/job/' + e.id + '/cancel', {}))))`);
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`, { what: 'file vide' });
  page.assertNoErrors();
});
