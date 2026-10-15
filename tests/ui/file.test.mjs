// File d'attente cloisonnée par espace, dans la vue du téléphone : la file et la pastille ne montrent que les générations
// de l'espace où l'on est.
//   node --test tests/ui/file.test.mjs   (ou : venv/bin/python tests/check.py --ui)
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

const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(async r => ({ status: r.status, body: await r.json() }))`);
async function enterPrivate() {
  const exists = await page.eval(`privState.exists`);
  assert.equal((await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE })).status, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
// génération lancée hors de l'interface, comme depuis un autre appareil (private : génération privée)
async function launch(prompt, extra = {}) {
  const r = await post('/api/generate', { mode: 't2i', prompt, width: 512, height: 512, steps: 20, cfg: 1, seed: -1,
    preview: false, ref_images: [], ...extra });
  assert.equal(r.status, 202);
  return r.body;
}
const type = text => page.eval(`(() => { const t = $('t2i_prompt'); t.value = ${JSON.stringify(text)}; t.dispatchEvent(new Event('input')); })()`);
const rows = () => page.eval(`[...$('queueList').querySelectorAll('.qrow')].map(r => r.textContent)`);

test('espace privé : la file ne montre que les générations privées, avec leur prompt, derrière le travail caché', async () => {
  await enterPrivate();
  const pub = await launch('SLOW=1 zq9public en cours');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération publique en cours' });
  await launch('zq9secret d\'un autre appareil', { private: true });
  await type('zq9secret de cette page');
  await page.click('#go');
  await page.waitFor(`pageJobs.some(p => p.private && isActive(p))`, { what: 'génération privée suivie par la page' });
  await page.eval(`refreshStatus()`);
  // pastille : rien de l'espace ne tourne : « En attente », durée jusqu'au début (travail caché compris), « +2 »
  await page.waitFor(`$('island').classList.contains('run') && $('islStep').textContent === 'En attente' && $('islEta').textContent.startsWith('≈')`,
    { what: 'pastille en attente avec sa durée' });
  assert.match(await page.eval(`$('islMore').textContent`), /^\+2/);
  await page.click('#island');
  await page.waitFor(`$('queueSheet').classList.contains('on') && $('queueList').querySelectorAll('.qrow').length === 2`,
    { what: 'feuille de la file avec les deux générations privées' });
  const [other, mine] = await rows();
  assert.match(other, /zq9secret d'un autre appareil/);
  assert.match(other, /1re en attente/);
  assert.match(mine, /zq9secret de cette page/);
  assert.match(mine, /2e en attente.*cet appareil/);
  const all = (await rows()).join(' ');
  assert.doesNotMatch(all, /zq9public|incognito|Génération privée/);
  // lot privé d'un autre appareil : son en-tête et « Annuler le lot », depuis la file
  await launch('zq9secret lot', { private: true, count: 2 });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('queueList').querySelectorAll('.qrow').length === 4 && !!$('queueList').querySelector('[data-cancel-lot]')`,
    { what: 'lot privé dans la file, avec son en-tête' });
  await page.click('#queueList [data-cancel-lot]');
  await page.waitFor(`$('queueList').querySelectorAll('.qrow').length === 2`, { what: 'lot privé annulé' });
  // annulation d'une génération privée lancée par un autre appareil, depuis la file
  assert.equal(await page.eval(`$('queueList').querySelectorAll('.qrow [data-cancel]').length`), 2);
  await page.click('#queueList .qrow:not(.own) [data-cancel]');
  await page.waitFor(`$('queueList').querySelectorAll('.qrow').length === 1`, { what: 'génération de l\'autre appareil annulée' });
  await page.click('#queueList .qrow.own [data-cancel]');
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération de cette page annulée' });
  await page.eval(`closeSheet()`);
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy)`, { what: 'Mac au repos' });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('espace public : une génération privée en cours n\'allume pas la pastille et n\'est pas dans la file', async () => {
  await enterPrivate();
  const priv = await launch('SLOW=1 zq9secret en cours', { private: true });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération privée en cours' });
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`$('island').classList.contains('run')`), false, 'pastille éteinte');
  await page.click('#island');
  await page.waitFor(`$('engineSheet').classList.contains('on')`, { what: 'panneau Moteur, pas la file' });
  await page.eval(`closeSheet()`);
  // une génération publique derrière elle : « En attente », sans ligne pour la privée
  await type('zq9public derrière');
  await page.click('#go');
  await page.waitFor(`pageJobs.some(p => !p.private && isActive(p))`, { what: 'génération publique suivie' });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('islStep').textContent === 'En attente' && $('islEta').textContent.startsWith('≈')`, { what: 'pastille en attente' });
  await page.click('#island');
  await page.waitFor(`$('queueSheet').classList.contains('on') && $('queueList').querySelectorAll('.qrow').length === 1`, { what: 'une seule ligne' });
  const [row] = await rows();
  assert.match(row, /zq9public derrière/);
  assert.match(row, /1re en attente/);
  assert.doesNotMatch(row, /zq9secret/);
  await page.click('#queueList .qrow.own [data-cancel]');
  await page.waitFor(`!pageJobs.some(p => !p.private && isActive(p))`, { what: 'génération publique annulée' });
  await page.eval(`closeSheet()`);
  await enterPrivate();
  assert.equal((await post(`/api/job/${priv.id}/cancel`)).status, 200);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});
