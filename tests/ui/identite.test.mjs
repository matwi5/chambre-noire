// Identité visuelle « lumière inactinique », dans la vue du téléphone : l'interface reste sombre même quand le
// téléphone est en mode clair (noir chaud, aucune surface en verre flouté), l'espace privé passe en lumière verte, la
// barre d'état prend la couleur du fond de l'espace, et la page du code d'accès et la page « Ordinateur injoignable »
// ont les mêmes couleurs que l'application. Les teintes exactes se règlent sur captures : les tests vérifient le
// caractère des couleurs (sombre, chaud, vert), pas leurs valeurs. Le nom et les titres sont en police pixel (Pixelify
// Sans, servie par le Mac), qui a tous les signes du français ; le texte courant reste en police du téléphone.
//   venv/bin/python tests/check.py --quick --ui tests/ui/identite.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench({ relay: true });
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// couleur CSS « rgb(r, g, b) » → [r, g, b] (source évaluée dans la page)
const RGB = `s => (s.match(/\\d+(\\.\\d+)?/g) || []).slice(0, 3).map(Number)`;
// couleurs de la page affichée : fond de body, barres d'état demandées (theme-color), éléments en verre flouté
const looks = () => page.eval(`(() => {
  const rgb = ${RGB};
  const hex = s => s.length === 7 ? [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16)) : null;
  return { bg: rgb(getComputedStyle(document.body).backgroundColor),
    themes: [...document.querySelectorAll('meta[name=theme-color]')].map(m => hex(m.content)),
    glass: [...document.querySelectorAll('*')].filter(el => getComputedStyle(el).backdropFilter !== 'none')
      .map(el => el.id || el.className || el.tagName) }; })()`);
const dark = c => Math.max(...c) < 40;
// barre d'état demandée (theme-color) : celle du fond de l'espace affiché (jeton --void)
const barOfVoid = `[...document.querySelectorAll('meta[name=theme-color]')].map(m => m.content).join()
  === getComputedStyle(document.documentElement).getPropertyValue('--void').trim()`;
// police de chaque élément désigné : true s'il est en police pixel (Pixelify Sans chargée et demandée en premier)
const pixel = selectors => page.eval(`document.fonts.ready.then(() => Object.fromEntries(${JSON.stringify(selectors)}
  .map(s => [s, getComputedStyle(document.querySelector(s)).fontFamily.startsWith('"Pixelify Sans"')
    && document.fonts.check('16px "Pixelify Sans"')])))`);
const allAs = (selectors, value) => Object.fromEntries(selectors.map(s => [s, value]));

test('page du code d\'accès, téléphone en mode clair : noir chaud, sans verre, barre d\'état du fond', async () => {
  await page.goto(bench.url + '/');               // sans le cookie : le relais montre la page du code
  await page.waitFor(`!!document.getElementById('c')`, { what: 'champ du code d\'accès' });
  const l = await looks();
  assert.ok(dark(l.bg) && l.bg[0] > l.bg[2], `fond noir chaud : ${l.bg}`);
  assert.deepEqual(l.themes, [l.bg], 'une seule couleur de barre d\'état, celle du fond');
  assert.deepEqual(l.glass, [], 'aucune surface en verre flouté');
  assert.deepEqual(await pixel(['h1', 'p', 'input']), { h1: true, p: false, input: false }, 'nom en police pixel');
  page.assertNoErrors();
});

test('interface, téléphone en mode clair : noir chaud, sans verre ; espace privé en lumière verte', async () => {
  await bench.login(page);
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  let l = await looks();
  assert.ok(dark(l.bg) && l.bg[0] > l.bg[2], `fond noir chaud : ${l.bg}`);
  await page.waitFor(barOfVoid, { what: 'barre d\'état du fond' });
  assert.equal(l.themes.length, 1, 'une seule couleur de barre d\'état');
  assert.deepEqual(l.glass, [], 'aucune surface en verre flouté');
  const titles = ['.topbar h1', '.hist-head h2', '#setTitle', '#engineTitle', '#tabbar button span:last-child',
    '#pileEmpty p'], text = ['#prompt', '#go', '.note', '#status', 'label', '#stepBig'];
  assert.deepEqual(await pixel([...titles, ...text]), { ...allAs(titles, true), ...allAs(text, false) },
    'nom, titres, onglets et états vides en police pixel, le reste en police du téléphone');
  const created = `postJson('/api/private/create', { code: 'code-identite-1' }).then(r => r.status)`;
  assert.equal(await page.eval(created), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  await page.waitFor(barOfVoid, { what: 'barre d\'état du fond privé' });
  l = await looks();
  assert.ok(dark(l.bg) && l.bg[1] > l.bg[0] && l.bg[1] > l.bg[2], `fond vert-noir : ${l.bg}`);
  assert.deepEqual(l.themes, [l.bg], 'barre d\'état du fond de l\'espace privé');
  const halo = await page.eval(`(${RGB})(getComputedStyle(document.documentElement).getPropertyValue('--halo'))`);
  assert.ok(halo[1] > halo[0], `halo vert dans l'espace privé : ${halo}`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  await page.waitFor(barOfVoid, { what: 'barre d\'état revenue au fond public' });
  l = await looks();
  assert.ok(l.themes.length === 1 && l.themes[0][0] > l.themes[0][1],
    `barre d'état noir chaud après la sortie : ${l.themes}`);
  page.assertNoErrors();
});

test('police pixel : tous les signes du français, dessinés par elle', async () => {
  const signs = 'éèêàâçôûùïëœ«»’ÉÈÀÇŒ';
  // un signe absent de la police serait dessiné par la police de repli : sa largeur changerait avec elle
  const missing = await page.eval(`document.fonts.load('32px "Pixelify Sans"', ${JSON.stringify(signs)}).then(() => {
    const x = document.createElement('canvas').getContext('2d');
    const width = (c, f) => { x.font = '32px ' + f; return x.measureText(c).width; };
    return [...${JSON.stringify(signs)}].filter(c => width(c, '"Pixelify Sans", monospace')
      !== width(c, '"Pixelify Sans", serif') || width(c, '"Pixelify Sans", serif') === width(c, 'serif')); })`);
  assert.deepEqual(missing, [], 'signes que la police pixel ne dessine pas');
  page.assertNoErrors();
});

// en dernier : le banc est arrêté pour que l'ordinateur ne réponde plus
test('page « Ordinateur injoignable » : mêmes couleurs que l\'application', async () => {
  await page.waitFor(`navigator.serviceWorker.getRegistration().then(r => !!(r && r.active))`,
    { what: 'service worker actif' });
  await page.goto(bench.url + '/');               // page contrôlée par le service worker
  await page.waitFor(`!!navigator.serviceWorker.controller`, { what: 'page contrôlée par le service worker' });
  const app = await looks(), url = bench.url, stopped = bench;
  bench = null;
  await stopped.stop();
  await page.goto(url + '/');
  await page.waitFor(`document.querySelector('h1')?.textContent === 'Ordinateur injoignable'`,
    { what: 'page hors ligne' });
  const off = await page.eval(`(() => { const rgb = ${RGB};
    return { bg: rgb(getComputedStyle(document.body).backgroundColor),
      button: rgb(getComputedStyle(document.querySelector('button')).backgroundColor) }; })()`);
  assert.deepEqual(off.bg, app.bg, 'fond de l\'application');
  assert.ok(off.button[0] > off.button[1] && off.button[1] > off.button[2], `bouton ambre : ${off.button}`);
});
