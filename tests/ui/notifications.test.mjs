// Toucher une notification de fin de génération mène au Labo, sur la pile : application fermée, le service worker
// (tools/ui/sw.js) l'ouvre à l'adresse de la notification ; déjà ouverte, il ramène sa fenêtre et la page passe au
// Labo, sans recharger. Le service worker est chargé seul dans Node (un toucher de notification ne se rejoue pas dans
// Chrome sans écran), la page dans la vue du téléphone ; le vrai toucher se valide sur le téléphone.
//   venv/bin/python tests/check.py --quick --ui tests/ui/notifications.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { startBench, launchChrome } from './driver.mjs';

const SW = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..', 'tools', 'ui', 'sw.js');

// sw.js exécuté avec un faux « self » : fenêtres ouvertes données, appels du service worker notés
function worker(wins) {
  const handlers = {}, calls = [];
  const self = {
    addEventListener: (type, f) => { handlers[type] = f; },
    clients: { matchAll: async () => wins, openWindow: async url => { calls.push(['openWindow', url]); } },
  };
  vm.runInNewContext(fs.readFileSync(SW, 'utf8'), { self, Response, fetch });
  return {
    calls,
    // notification touchée : renvoie ce que le service worker a fait, une fois son travail fini
    async click(url = '/') {
      let work = null, closed = false;
      handlers.notificationclick({ notification: { close: () => { closed = true; }, data: { url } },
        waitUntil: p => { work = p; } });
      await work;
      return { closed, calls };
    },
  };
}

const win = (calls, { focused = false, refuse = false } = {}) => ({
  focused,
  postMessage: m => calls.push(['postMessage', JSON.parse(JSON.stringify(m))]),   // objet du contexte de sw.js
  focus: () => { calls.push(['focus']); return refuse ? Promise.reject(new TypeError('refusé')) : Promise.resolve(); },
});

test('service worker : application fermée, la notification l\'ouvre à son adresse (le Labo)', async () => {
  const sw = worker([]);
  assert.deepEqual(await sw.click('/'), { closed: true, calls: [['openWindow', '/']] });
});

test('service worker : application ouverte, sa fenêtre revient et passe au Labo, sans nouvelle fenêtre', async () => {
  const other = [], front = [];                    // la fenêtre au premier plan est celle qui revient
  assert.deepEqual(await worker([win(other), win(front, { focused: true })]).click('/'), { closed: true, calls: [] });
  assert.deepEqual(front, [['postMessage', { go: 'labo' }], ['focus']]);
  assert.deepEqual(other, []);
  // fenêtre au premier plan refusée par le navigateur : le message est parti quand même, rien n'échoue
  const refused = [];
  assert.deepEqual((await worker([win(refused, { refuse: true })]).click()).calls, []);
  assert.deepEqual(refused, [['postMessage', { go: 'labo' }], ['focus']]);
});

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok')`, { what: 'moteur prêt affiché' });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// message du service worker reçu par la page, comme après un toucher de notification
const fromWorker = () => page.eval(`navigator.serviceWorker.dispatchEvent(new MessageEvent('message',
  { data: { go: 'labo' } }))`);

test('page : le message du service worker mène des Tirages au Labo, feuille et visionneuse fermées', async () => {
  await page.made('zqN tirage');
  assert.equal(await page.keepPile(), 1);
  await page.tab('tirages');
  await page.click('#lamp');
  await page.waitFor(`openedSheet === $('engineSheet')`, { what: 'feuille de la lampe' });
  await fromWorker();
  await page.waitFor(`mode === 'labo' && !openedSheet`, { what: 'Labo, feuille fermée' });
  await page.tab('tirages');
  await page.waitFor(`!!$('histGrid').querySelector('button')`, { what: 'tirage affiché' });
  await page.click('#histGrid button');
  await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
  await fromWorker();
  await page.waitFor(`mode === 'labo' && vIndex < 0`, { what: 'Labo, visionneuse fermée' });
  assert.equal(await page.eval(`$('pane-labo').classList.contains('active')`), true);
  page.assertNoErrors();
});
