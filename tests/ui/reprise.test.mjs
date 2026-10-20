// Génération reprise par une page qui ne l'a pas lancée (après un rechargement, depuis un autre appareil), dans la vue
// du téléphone : la page en retrouve le prompt complet (la file n'en donne que les 80 premiers caractères).
//   node --test tests/ui/reprise.test.mjs   (ou : venv/bin/python tests/check.py --ui)
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
  await chrome?.close();
  await bench?.stop();
});

// plus de 80 caractères ; HOLD=<nom> : la génération reste en file jusqu'à bench.release(nom) (voir
// tests/fake_sdcli.py), un nom par test (une libération vaut jusqu'à la fin du banc)
const TEXT = ' zq6 un phare au crépuscule, une mer agitée, des embruns dorés, un ciel violet, '
  + 'des mouettes au loin et une petite maison blanche au pied du phare';
const LONG = 'HOLD=lot' + TEXT, LONG_PRIV = 'HOLD=privee' + TEXT;
const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
const queue = () => page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.queue.map(e => e.prompt))`);
const idle = () => page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy)`, { what: 'Mac au repos', timeout: 30000 });

test('rechargement : un lot repris montre le prompt complet et « Reprendre » rend le texte entier', async () => {
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  await page.eval(`opt.count = 2; saveOpt(); refreshChoices();
    (() => { const t = $('prompt'); t.value = ${JSON.stringify(LONG)}; t.dispatchEvent(new Event('input')); })()`);
  await page.click('#go');
  await page.waitFor(`pageJobs.length === 2`, { what: 'lot de deux images suivi par la page' });

  await page.goto(bench.url + '/');                // rechargement : la page reprend le lot depuis la file
  await page.waitFor(`pageJobs.length === 2`, { what: 'lot repris après le rechargement' });
  const excerpts = await queue();
  assert.ok(excerpts.length > 0 && excerpts.every(p => p.length < LONG.length), 'la file n\'a qu\'un extrait');
  assert.deepEqual(await page.eval(`pageJobs.map(p => p.prompt)`), [LONG, LONG]);
  bench.release('lot');
  await page.click('#tabbar [data-pane="run"]');   // la page rechargée s'ouvre sur Créer
  await page.waitFor(`$('doneList').querySelectorAll('.dlot [data-open]').length === 2`,
    { what: 'grille du lot terminé', timeout: 30000 });
  assert.equal(await page.eval(`$('doneList').querySelector('.dlot .dprompt').textContent`), LONG, 'prompt du lot');

  await page.click('#doneList .dlot [data-open]'); // visionneuse depuis les terminées, puis « Reprendre »
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  await page.eval(`$('prompt').value = ''`);
  await page.click(`#viewer button[onclick="viewerAction('prompt')"]`);
  await page.waitFor(`!$('viewer').classList.contains('on')`, { what: 'texte repris, visionneuse fermée' });
  assert.equal(await page.eval(`$('prompt').value`), LONG);
  await page.eval(`opt.count = 1; saveOpt();`);
  page.assertNoErrors();
});

test('espace privé : une génération privée lancée d\'un autre appareil est reprise avec son prompt complet', async () => {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  assert.equal(await post('/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  // demande envoyée hors de l'interface, comme depuis un autre appareil : la page ne la suit pas encore
  assert.equal(await post('/api/generate', { mode: 't2i', prompt: LONG_PRIV, width: 512, height: 512, steps: 4, cfg: 1,
    seed: -1, preview: false, ref_images: [], private: true }), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pageJobs.some(p => p.private && p.adopted)`, { what: 'génération privée reprise de la file' });
  const excerpts = await queue();
  assert.ok(excerpts.length > 0 && excerpts.every(p => p.length < LONG_PRIV.length), 'la file n\'a qu\'un extrait');
  assert.equal(await page.eval(`pageJobs.find(p => p.private).prompt`), LONG_PRIV);
  bench.release('privee');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  await idle();
  page.assertNoErrors();
});
