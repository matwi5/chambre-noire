// Affichage des images (visionneuse, images d'entrée, zone de résultat, galerie), dans la vue du téléphone : jamais
// l'image d'avant le temps d'un chargement, rien de l'espace privé à l'écran ni dans la page après en être sorti
// (galerie privée comprise, sortie faite depuis un autre onglet), image voisine et image d'entrée montrées sans
// attente, zoom au pincement sur les images d'entrée comme sur les images générées.
//   node --test tests/ui/images.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/images.test.mjs)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

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
const privatePost = url => page.eval(`postJson('${url}', { code: ${JSON.stringify(CODE)} }).then(r => r.status)`);
// image de référence (data URL) dessinée dans la page, de la couleur donnée
const ref = color => `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '${color}'; x.fillRect(0, 0, 256, 256);
  return c.toDataURL('image/png'); })()`;
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

test('espace privé : après la sortie, ni visionneuse ni images d\'entrée ne montrent une image privée', async () => {
  assert.equal(await edit('zq3 publique a', '#2060c0'), 202);
  assert.equal(await edit('zq3 publique b', '#20a040'), 202);
  await idle();
  assert.equal(await privatePost('/api/private/create'), 200);
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
  await page.waitFor(`$('iv').classList.contains('on') && ${loaded('ivImg')}`,
    { what: 'image d\'entrée privée affichée' });
  assert.match(await page.eval(`$('ivImg').currentSrc`), /\/api\/private\/input/);
  await page.eval(`closeInputs(); closeViewer()`);
  await page.waitFor(`!$('vImg').getAttribute('src') && !$('ivImg').getAttribute('src')`,
    { what: 'visionneuse vidée' });

  // fermeture de l'espace (comme par le Mac après 15 minutes) : la page n'en garde aucune image, même cachée, et une
  // image privée encore en chargement (adresse jamais demandée) n'arrive pas à l'écran après coup
  const late = await page.eval(`srcOf(histItems[0]) + '&tard=1'`);
  const left = await page.eval(`(() => { showImage($('vImg'), ${JSON.stringify(late)});
    applyPrivate({ ...privState, unlocked: false }); return ${PRIVATE_IMAGES}; })()`);
  assert.deepEqual(left, [], 'images privées restées dans la page');
  // ni lien vers une route privée, ni texte de l'image privée (prompt en texte de remplacement), ni liste privée
  assert.deepEqual(await page.eval(`({ links: [...document.querySelectorAll('[href*="/api/private/"]')].map(a => a.id),
    names: [...document.querySelectorAll('[download^="prive_"]')].map(a => a.id),
    prompt: document.documentElement.outerHTML.includes('zq3 privée'), list: vList.length })`),
  { links: [], names: [], prompt: false, list: 0 }, 'données privées restées dans la page');
  // la même adresse redemandée à part : sa réponse arrivée, celle de l'image abandonnée l'aurait été aussi
  await page.eval(`fetch(${JSON.stringify(late)}).then(r => r.blob())
    .then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))`);
  assert.deepEqual(await page.eval(PRIVATE_IMAGES), [], 'image privée arrivée après la sortie');
  await page.eval(`postJson('/api/private/lock', {})`);   // puis la session du serveur
  await page.eval(`refreshStatus()`);
  await page.waitFor(`histItems.length === 2 && histItems.every(it => !it.private)`, { what: 'galerie publique' });

  // dans l'espace public : à l'ouverture de la visionneuse et de l'image d'entrée, puis pendant leur chargement,
  // aucune image privée n'est peinte
  const seen = await page.eval(`new Promise(res => { const out = [];
    openViewer(0, histItems); openInputs(0); out.push(...${PRIVATE_IMAGES});
    let n = 0; (function frame(){ out.push(...${PRIVATE_IMAGES});
      if (++n < 30) requestAnimationFrame(frame); else res(out); })(); })`);
  assert.deepEqual(seen, [], 'image privée peinte dans l\'espace public');
  await page.waitFor(`${loaded('ivImg')} && $('ivImg').currentSrc.includes('/api/input?')`,
    { what: 'image d\'entrée publique' });
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

test('galerie : sortir de l\'espace privé depuis Créer puis revenir à la galerie ne montre pas la privée', async () => {
  assert.equal(await privatePost('/api/private/unlock'), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'de nouveau dans l\'espace privé' });
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length === 1 && histItems[0].private
    && [...$('histGrid').querySelectorAll('img')].every(i => i.complete && i.naturalWidth > 0)`,
  { what: 'galerie privée affichée' });
  await page.click('#tabbar [data-pane="t2i"]');
  await page.click('#privExit');                   // « Sortir », depuis Créer
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  // retour à la galerie : à chaque image peinte jusqu'à la galerie publique chargée, aucune image privée
  const seen = await page.eval(`new Promise(res => { const out = [...${PRIVATE_IMAGES}];
    goTab('hist'); out.push(...${PRIVATE_IMAGES});
    let n = 0; (function frame(){ out.push(...${PRIVATE_IMAGES});
      const done = histItems.length === 2 && histItems.every(it => !it.private);
      if (++n < 90 && !done) requestAnimationFrame(frame); else res(out); })(); })`);
  assert.deepEqual(seen, [], 'galerie privée vue dans l\'espace public');
  await page.waitFor(`histItems.length === 2 && histItems.every(it => !it.private)`, { what: 'galerie publique' });
  page.assertNoErrors();
});

test('images d\'entrée : la première, prête dès l\'ouverture de la visionneuse, s\'affiche sans attente', async () => {
  await page.waitFor(`histItems.length === 2 && histItems.every(it => it.inputs.length)`, { what: 'galerie publique' });
  const first = await page.eval(`inputUrl(histItems[1], histItems[1].inputs[0])`);
  await page.eval(`openViewer(1, histItems)`);
  await page.waitFor(`ready.get(${JSON.stringify(first)})?.im`,
    { what: 'image d\'entrée chargée en avance', timeout: 5000 });
  const now = await page.eval(`(() => { openInputs(0); const i = $('ivImg');
    return { src: i.getAttribute('src'), complete: i.complete, w: i.naturalWidth }; })()`);
  assert.equal(now.src, first, 'image d\'entrée complète tout de suite (pas sa miniature, pas un cadre vide)');
  assert.ok(now.complete && now.w > 0, 'déjà chargée');
  page.assertNoErrors();
});

test('images d\'entrée : pincer zoome, relâcher rend la taille initiale', async () => {
  await page.eval(`closeInputs(); openViewer(0, histItems); openInputs(0)`);
  await page.waitFor(`$('iv').classList.contains('on') && ${loaded('ivImg')} && !$('ivImg').src.includes('thumb=1')`,
    { what: 'image d\'entrée affichée' });
  const c = await page.eval(`(() => { const r = $('ivImg').getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  const touch = (type, d) => page.send('Input.dispatchTouchEvent', { type, touchPoints: d == null ? [] :
    [{ x: c.x - d, y: c.y, id: 1 }, { x: c.x + d, y: c.y, id: 2 }] });
  await touch('touchStart', 20);
  for (const d of [40, 60, 80]) await touch('touchMove', d);
  const during = await page.eval(`({ t: $('ivImg').style.transform, zoomed: $('iv').classList.contains('zoomed') })`);
  await touch('touchEnd');
  const scale = Number((during.t.match(/scale\(([\d.]+)\)/) || [])[1]);
  assert.ok(scale > 2 && during.zoomed, `image d'entrée zoomée pendant le pincement : ${during.t}`);
  await page.waitFor(`$('ivImg').style.transform === ''`, { what: 'taille initiale au relâcher' });
  // un doigt glissé vers le bas ferme les images d'entrée, comme la visionneuse
  for (const [type, dy] of [['touchStart', 0], ['touchMove', 60], ['touchMove', 160]])
    await page.send('Input.dispatchTouchEvent', { type, touchPoints: [{ x: c.x, y: c.y + dy, id: 1 }] });
  await page.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitFor(`!$('iv').classList.contains('on') && $('viewer').classList.contains('on')`,
    { what: 'images d\'entrée fermées' });
  // appui sur une flèche juste après une fermeture, dans le même tour (donc pendant le fondu) : rien ne se rouvre, et
  // la vue se vide une fois le fondu passé
  assert.equal(await page.eval(`(() => { openInputs(0); closeInputs(); $('iv').querySelector('.v-nav.next').click();
    return ivIndex; })()`), -1, 'images d\'entrée restées fermées');
  await page.waitFor(`!$('ivImg').getAttribute('src') && !$('ivLabel').textContent && !$('ivDl').hasAttribute('href')`,
    { what: 'images d\'entrée vidées après le fondu' });
  await page.eval(`closeViewer()`);
  await page.waitFor(`!$('vImg').hasAttribute('src') && !$('vBg').hasAttribute('src')`,
    { what: 'visionneuse vidée après le fondu, fond flouté compris' });
  page.assertNoErrors();
});

test('espace privé : la feuille « Voir le lot » d\'un lot privé se ferme et se vide à la sortie', async () => {
  await page.eval(`closeInputs(); closeViewer()`);
  assert.equal(await privatePost('/api/private/unlock'), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  // la visionneuse publique fermée au test d'avant s'est vidée après son fondu : rien d'elle, fond compris, dans
  // l'espace privé
  assert.equal(await page.eval(`$('vBg').getAttribute('src')`), null, 'fond public resté dans l\'espace privé');
  assert.equal(await page.eval(`postJson('/api/generate', { mode: 't2i', prompt: 'zq7 lot privé', width: 512,
    height: 512, steps: 2, cfg: 1, seed: -1, preview: false, ref_images: [], private: true, count: 2 })
    .then(r => r.status)`), 202);
  await idle();
  await page.eval(`goTab('t2i'); goTab('hist')`);   // galerie rechargée, lot compris
  await page.waitFor(`histItems.filter(it => it.lot).length === 2`, { what: 'lot privé dans la galerie' });
  await page.eval(`openViewer(histItems.findIndex(it => it.lot), histItems); openLot()`);
  await page.waitFor(`openedSheet === $('lotSheet') && $('lotSheetGrid').querySelectorAll('img').length === 2`,
    { what: 'feuille du lot ouverte' });
  await page.click('#privExit');                   // « Sortir », la feuille du lot ouverte
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  // la visionneuse, ouverte sur l'image privée à la sortie, est vidée sans attendre son fondu
  const after = await page.eval(`({ open: openedSheet === $('lotSheet'), cells: $('lotSheetGrid').children.length,
    images: ${PRIVATE_IMAGES}, list: vList.length, alt: $('vImg').alt, chips: $('vChips').children.length,
    prompt: document.documentElement.outerHTML.includes('zq7 lot privé') })`);
  assert.deepEqual(after, { open: false, cells: 0, images: [], list: 0, alt: '', chips: 0, prompt: false },
    'lot privé resté dans la page');
  page.assertNoErrors();
});

test('zone de résultat : son image retirée, son lien de téléchargement part avec elle', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  const kept = await page.eval(`fetch('/api/history').then(r => r.json()).then(h => {
    if (!h.length) throw new Error('aucune image publique au banc');
    showResult(h[0].name, 512, 512); show(null);   // comme une image supprimée ou effacée : zone vidée
    return { href: $('dl').hasAttribute('href'), name: $('dl').hasAttribute('download') }; })`);
  assert.deepEqual(kept, { href: false, name: false }, 'lien vers l\'image retirée resté dans la page');
  page.assertNoErrors();
});

test('images d\'entrée : la miniature, en attendant l\'image complète, a déjà sa taille à l\'écran', async () => {
  await page.waitFor(`!inPrivate()`, { what: 'espace public' });
  // photo plus grande que sa miniature (320 px) et que l'écran : la miniature doit s'afficher agrandie
  assert.equal(await page.eval(`postJson('/api/generate', { mode: 'edit', prompt: 'zq9 miniature',
    width: 512, height: 512,
    steps: 2, cfg: 1, seed: -1, preview: false, ref_images: [(() => { const c = document.createElement('canvas');
      c.width = 1200; c.height = 900; const x = c.getContext('2d');
      x.fillStyle = '#3080a0'; x.fillRect(0, 0, 1200, 900);
      return c.toDataURL('image/png'); })()] }).then(r => r.status)`), 202);
  await idle();
  await page.eval(`goTab('t2i'); goTab('hist')`);
  await page.waitFor(`histItems.some(it => it.prompt === 'zq9 miniature')`, { what: 'image dans la galerie' });
  // image complète retenue (jamais demandée : rien dans les images de la page) : seule la miniature peut s'afficher
  const held = [];
  page.on('Fetch.requestPaused', p => held.push(p.requestId));
  await page.send('Fetch.enable',
    { patterns: [{ urlPattern: '*/api/input?*file=ref_1.png', requestStage: 'Request' }] });
  await page.eval(`openViewer(histItems.findIndex(it => it.prompt === 'zq9 miniature'), histItems); openInputs(0)`);
  await page.waitFor(`$('ivImg').src.includes('thumb=1') && $('ivImg').complete && $('ivImg').naturalWidth > 0`,
    { what: 'miniature affichée' });
  const size = `[$('ivImg').offsetWidth, $('ivImg').offsetHeight]`;   // taille posée, hors animation d'ouverture
  const thumb = await page.eval(size);
  await waitUntil(() => held.length > 0, { what: 'image complète demandée' });
  for (const requestId of held) await page.send('Fetch.continueRequest', { requestId });
  await page.send('Fetch.disable');
  await page.waitFor(`!$('ivImg').src.includes('thumb=1') && $('ivImg').complete && $('ivImg').naturalWidth > 0`,
    { what: 'image complète affichée' });
  const full = await page.eval(size);
  assert.ok(Math.abs(thumb[0] - full[0]) <= 2 && Math.abs(thumb[1] - full[1]) <= 2,
    `taille de la miniature ${thumb} au lieu de ${full} : l'image saute à l'arrivée de l'image complète`);
  await page.eval(`closeInputs(); closeViewer()`);
  page.assertNoErrors();
});
