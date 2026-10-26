// Test de fumée de l'interface, dans la vue du téléphone : chaque écran principal s'ouvre sans erreur de console
// (Labo, avec la génération en cours, et Tirages), et le panneau Moteur dit quelle version du code est servie. Code
// d'accès redemandé (cookie effacé, réponse 401 de /api/status) : la page se recharge une fois sur la page du code.
// Entrée par le jeton (launch.py --enter) : la page de redirection, ouverte comme un fichier, ouvre l'interface.
//   venv/bin/python tests/check.py --ui   (tous les fichiers ; --quick --ui tests/ui/smoke.test.mjs pour celui-ci)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.ready();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

test('vue du téléphone : mode allégé', async () => {
  assert.equal(await page.eval(`document.documentElement.classList.contains('lite')`), true);
});

test('onglets Labo et Tirages', async () => {
  for (const pane of ['tirages', 'labo']) {
    await page.tab(pane);
    assert.equal(await page.eval(`document.body.className`), `m-${pane}`);
    if (pane === 'tirages') await page.waitFor(`$('histGrid').children.length > 0`, { what: 'Tirages affichés' });
  }
  // feuille de la file, rangée « #1 #2… » et annulation du compositeur d'avant : remplacées par le haut du Labo
  assert.deepEqual(await page.eval(`['queueSheet', 'strip', 'cancel'].filter(id => $(id))`), []);
  page.assertNoErrors();
});

test('feuille des prompts', async () => {
  await page.click('#promptsBtn');
  await page.waitFor(`$('promptSheet').classList.contains('on') && $('typeList').children.length > 0`,
    { what: 'feuille des prompts ouverte, prompts types listés' });
  await page.eval(`closeSheet()`);
  page.assertNoErrors();
});

// (titre attendu tel quel par tests/test_check.py, UiNameTest)
test('« Révéler » suit la génération sur le Labo, puis annulation depuis la carte en cours', async () => {
  // une génération lente lancée depuis l'interface (le faux moteur ralentit sur SLOW=…)
  await page.typePrompt('SLOW=0.3 essai de la file');
  await page.click('#go');
  await page.waitFor(`pageJobs.some(isActive) && mode === 'labo'`, { what: 'génération suivie, Labo' });
  await page.waitFor(`shown && shown.j.status === 'running' && !$('runCard').hidden`,
    { what: 'génération sur la carte en cours' });
  await page.cancelRun();
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération annulée' });
  const status = await bench.api('/api/status');
  assert.equal(status.queue.length, 0);
  page.assertNoErrors();
});

test('panneau Moteur : version du code servi, et serveur à relancer quand launch.py a changé', async () => {
  const shown = await page.eval(`({ v: fmtVersion({ commit: 'abc1234', branch: 'main', date: '2026-10-16' }),
    none: fmtVersion(undefined),
    same: staleServer({ version: { commit: 'b2', server: 'f1' }, server_version: { commit: 'a1', server: 'f1' } }),
    stale: staleServer({ version: { commit: 'abc1234', server: 'f2' },
      server_version: { commit: 'def5678', server: 'f1' } }) })`);
  assert.deepEqual(shown, { v: 'abc1234 · main · 16/10/2026', none: '', same: '',
    stale: 'à relancer : son code a changé depuis son lancement' });
  page.assertNoErrors();
});

const UNAUTHORIZED = { responseCode: 401, responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
  body: Buffer.from(JSON.stringify({ error: 'code d\'accès requis' })).toString('base64') };
// page du code d'accès affichée (évaluation pendant un rechargement : pas encore)
const loginShown = () => waitUntil(() => page.eval(`!!document.getElementById('c') && location.search`)
  .then(v => v === '?reauth').catch(() => false), { what: 'page du code, après un seul rechargement' });

test('code d\'accès redemandé : la page se recharge une fois sur la page du code, sans boucle', async () => {
  await page.send('Network.clearBrowserCookies');   // cookie effacé, ou code changé sur le Mac
  await page.eval(`void refreshStatus()`);
  await loginShown();
  // interface rechargée sur /?reauth, dont l'état répond encore 401 avant toute réponse : elle ne se recharge plus
  await bench.login(page);
  const h = await page.holdRequests(['*/api/status'], () => true);
  try {
    await page.goto(bench.url + '/?reauth');
    await page.eval(`window.zqSameDocument = true`);
    await waitUntil(() => h.held.length > 0, { what: 'état demandé' });
    for (const r of h.take()) await page.send('Fetch.fulfillRequest', { requestId: r.requestId, ...UNAUTHORIZED });
    await page.waitFor(`$('lamp').classList.contains('err')`, { what: 'réponse 401 lue' });
    // (reauthing est posé avant tout rechargement : faux, aucun n'est parti)
    assert.deepEqual(await page.eval(`[window.zqSameDocument === true, reauthing, location.search]`),
      [true, false, '?reauth'], 'page rechargée une seconde fois');
  } finally {
    await h.release();
  }
  await bench.login(page);
  await page.ready('interface rouverte');
  // (les réponses 401, et elles seules, sont notées en erreur par Chrome)
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/status of 401 \(Unauthorized\)/.test(e)));
  page.assertNoErrors();
});

test('code d\'accès redemandé de nouveau après une réponse du Mac : la page se recharge encore une fois', async () => {
  await page.goto(bench.url + '/?reauth');         // interface rechargée après un premier 401, code saisi depuis
  await page.eval(`window.zqSameDocument = true; void goTab('tirages')`);
  await page.waitFor(`$('lamp').classList.contains('ok') && location.search === ''`,
    { what: 'état lu, « ?reauth » retiré de l\'adresse' });
  assert.deepEqual(await page.eval(`[window.zqSameDocument === true, mode, location.pathname]`), [true, 'tirages', '/'],
    'page rechargée ou état perdu en retirant « ?reauth »');
  await page.send('Network.clearBrowserCookies');   // le code est redemandé plus tard : rechargement une fois
  await page.eval(`void refreshStatus()`);
  await loginShown();
  await bench.login(page);
  await page.ready('interface rouverte');
  page.errors.splice(0, page.errors.length, ...page.errors.filter(e => !/status of 401 \(Unauthorized\)/.test(e)));
  page.assertNoErrors();
});

test('entrée par le jeton : la page d\'entrée ouvre l\'interface sans le code, une seule fois', async () => {
  const alone = await launchChrome();              // profil à part, sans cookie d'accès
  try {
    const p = await alone.phonePage();
    await p.send('Network.clearBrowserCookies');
    const file = await bench.enter();              // comme launch.py --enter : un fichier, pas l'adresse
    const target = fs.readFileSync(file, 'utf8').match(/content="0;url=([^"]+)"/)[1];
    await p.goto(pathToFileURL(file).href);
    await waitUntil(() => p.eval(`location.pathname === '/' && $('lamp').classList.contains('ok')`).catch(() => false),
      { what: 'interface ouverte par la page d\'entrée' });
    assert.equal(fs.existsSync(file), false, 'page d\'entrée restée après usage');
    await p.send('Network.clearBrowserCookies');
    await p.goto(target);                          // jeton déjà servi : page du code
    await p.waitFor(`!!document.getElementById('c')`, { what: 'page du code d\'accès' });
  } finally {
    await alone.close();
  }
});
