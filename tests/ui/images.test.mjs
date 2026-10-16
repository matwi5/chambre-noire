// Affichage des images (visionneuse, images d'entrée, zone de résultat), dans la vue du téléphone : jamais l'image
// d'avant le temps d'un chargement, rien de l'espace privé à l'écran ni dans la page après en être sorti, image
// voisine montrée sans attente dans la visionneuse.
//   node --test tests/ui/images.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/images.test.mjs)
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
// image de référence (data URL) dessinée dans la page, de la couleur donnée
const ref = color => `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '${color}'; x.fillRect(0, 0, 256, 256); return c.toDataURL('image/png'); })()`;
// une édition avec cette image en référence, dans l'espace affiché (privée dans l'espace privé)
const edit = (prompt, color, priv = false) => page.eval(`postJson('/api/generate', { mode: 'edit',
  prompt: ${JSON.stringify(prompt)}, width: 512, height: 512, steps: 2, cfg: 1, seed: -1, preview: false,
  ref_images: [${ref(color)}], private: ${priv} }).then(r => r.status)`);
const idle = () => page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`,
  { what: 'Mac au repos', timeout: 30000 });
// adresse d'une image privée dans la page : attribut src ou image réellement peinte (currentSrc)
const PRIVATE_IMAGES = `[...document.images].filter(i => (i.getAttribute('src') || '').includes('/api/private/')
  || i.currentSrc.includes('/api/private/')).map(i => i.id || i.parentElement.id || i.parentElement.className)`;
const loaded = id => `$('${id}').complete && $('${id}').naturalWidth > 0`;

test('espace privé : après la sortie, ni la visionneuse ni les images d\'entrée ne montrent une image privée', async () => {
  assert.equal(await edit('zq3 publique a', '#2060c0'), 202);
  assert.equal(await edit('zq3 publique b', '#20a040'), 202);
  await idle();
  assert.equal(await page.eval(`postJson('/api/private/create', { code: ${JSON.stringify(CODE)} }).then(r => r.status)`), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  assert.equal(await edit('zq3 privée', '#c02020', true), 202);
  await idle();

  // dans l'espace privé : la galerie, la visionneuse et l'image d'entrée de l'image privée, chargées
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length === 1 && histItems[0].private`, { what: 'galerie privée' });
  await page.click('#histGrid button');
  await page.waitFor(`$('viewer').classList.contains('on') && ${loaded('vImg')}`, { what: 'image privée affichée' });
  await page.click('#vInputs');
  await page.waitFor(`$('iv').classList.contains('on') && ${loaded('ivImg')}`, { what: 'image d\'entrée privée affichée' });
  assert.match(await page.eval(`$('ivImg').currentSrc`), /\/api\/private\/input/);
  await page.eval(`closeInputs(); closeViewer()`);
  await page.waitFor(`!$('vImg').getAttribute('src') && !$('ivImg').getAttribute('src')`, { what: 'visionneuse vidée' });

  // fermeture de l'espace (comme par le Mac après 15 minutes) : la page n'en garde aucune image, même cachée, et une
  // image privée encore en chargement (adresse jamais demandée) n'arrive pas à l'écran après coup
  const late = await page.eval(`srcOf(histItems[0]) + '&tard=1'`);
  const left = await page.eval(`(() => { showImage($('vImg'), ${JSON.stringify(late)});
    applyPrivate({ ...privState, unlocked: false }); return ${PRIVATE_IMAGES}; })()`);
  assert.deepEqual(left, [], 'images privées restées dans la page');
  await page.waitFor(`performance.getEntriesByName(location.origin + ${JSON.stringify(late)}).length > 0
    && new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(true))))`, { what: 'image tardive arrivée' });
  assert.deepEqual(await page.eval(PRIVATE_IMAGES), [], 'image privée arrivée après la sortie');
  await page.eval(`postJson('/api/private/lock', {})`);   // puis la session du serveur
  await page.eval(`refreshStatus()`);
  await page.waitFor(`histItems.length === 2 && histItems.every(it => !it.private)`, { what: 'galerie publique' });

  // dans l'espace public : à l'ouverture de la visionneuse et de l'image d'entrée, puis pendant leur chargement,
  // aucune image privée n'est peinte
  const seen = await page.eval(`new Promise(res => { const out = [];
    openViewer(0, histItems); openInputs(0); out.push(...${PRIVATE_IMAGES});
    let n = 0; (function frame(){ out.push(...${PRIVATE_IMAGES}); if (++n < 30) requestAnimationFrame(frame); else res(out); })(); })`);
  assert.deepEqual(seen, [], 'image privée peinte dans l\'espace public');
  await page.waitFor(`${loaded('ivImg')} && $('ivImg').currentSrc.includes('/api/input?')`, { what: 'image d\'entrée publique' });
  await page.eval(`closeInputs(); closeViewer()`);
  page.assertNoErrors();
});

test('visionneuse : l\'image voisine, déjà chargée, s\'affiche sans attente et sans l\'image d\'avant', async () => {
  await page.eval(`goTab('hist')`);
  await page.waitFor(`histItems.length === 2 && !!$('histGrid').querySelector('button')`, { what: 'galerie publique' });
  const urls = await page.eval(`histItems.map(srcOf)`);
  await page.eval(`openViewer(0, histItems)`);
  await page.waitFor(`${loaded('vImg')} && $('vImg').currentSrc.endsWith(${JSON.stringify(urls[0])})`,
    { what: 'première image en grand' });
  await page.waitFor(`ready.get(${JSON.stringify(urls[1])})?.im`, { what: 'voisine chargée en avance' });
  const now = await page.eval(`(() => { stepViewer(1); const i = $('vImg');
    return { src: i.getAttribute('src'), current: i.currentSrc, complete: i.complete }; })()`);
  assert.ok(now.src && now.src.endsWith(urls[1]), `image suivante tout de suite : ${now.src}`);
  assert.ok(now.complete && now.current.endsWith(urls[1]), 'image suivante déjà chargée, pas l\'image d\'avant');
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});
