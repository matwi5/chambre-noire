// « Vidéo » dans la ligne « Modèle » (ticket 10), dans la vue du téléphone : lignes Durée, Taille et Format à la place
// du format, de la résolution, des étapes, des images et de l'aperçu ; une seule image jointe, image de départ ;
// Dessiner grisé, pas de campagne ; la vidéo finie dans la pile et la visionneuse (WebP animé), sans Éditer, Dessiner
// ni Avant, Copier grisé, téléchargée sous son nom en .webp ; « Relancer » et « Reprendre » avec sa durée.
//   venv/bin/python tests/check.py --quick --ui tests/ui/video.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  bench.video();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const CELLS = `[...$('setGrid').querySelectorAll('[data-set]')].map(c => c.dataset.set)`;
const displayed = id => page.eval(`getComputedStyle($('${id}')).display !== 'none'`);
const labels = id => page.eval(`[...$('${id}').querySelectorAll('[data-k]')].map(b => b.textContent)`);
// page neuve, la vidéo installée et choisie
async function freshVideo() {
  await page.freshLabo(bench);
  await page.modelsSeen(2);                        // Qwen et la vidéo (MiniMax H3 retiré par serve.py)
  await page.chooseModel('video');
}
// fichier image dessiné dans la page, ajouté aux images d'entrée comme un choix de fichiers
const addImages = n => page.eval(`(async () => { const files = [];
  for (let k = 0; k < ${n}; k++) { const c = document.createElement('canvas'); c.width = c.height = 128;
    c.getContext('2d').fillRect(0, 0, 64, 64);
    files.push(new File([await new Promise(r => c.toBlob(r))], 'depart-' + k + '.png', { type: 'image/png' })); }
  await addInputFiles(files); })()`);

test('Vidéo : Durée, Taille et Format à la place des réglages d\'image, sans aperçu', async () => {
  await freshVideo();
  assert.deepEqual(await labels('modelOpts'), ['Qwen', 'Vidéo']);
  assert.deepEqual(await labels('durOpts'), ['2 s', '3 s', '5 s']);
  assert.deepEqual(await labels('vsizeOpts'), ['Petite', 'Normale']);
  assert.deepEqual(await labels('vfmtOpts'), ['Paysage', 'Portrait']);
  assert.equal(await displayed('videoRows'), true, 'lignes de la vidéo cachées');
  for (const id of ['ratioOpts', 'resOpts', 'resHead', 'stepRow', 'countRow', 'previewRow'])
    assert.equal(await displayed(id), false, `${id} montré avec la vidéo`);
  assert.deepEqual(await page.eval(CELLS), ['modele', 'duree', 'vtaille', 'vformat']);
  assert.match(await page.eval(`$('setGrid').textContent`), /ModèleVidéoDurée2 sTaillePetiteFormatPaysage/);
  const req = await page.sentRequest('zvi1 petite');
  assert.deepEqual([req.model, req.frames, req.width, req.height, req.steps, req.preview, req.mode, 'count' in req],
    ['video', 56, 480, 288, 4, false, 't2i', false]);
  await page.eval(`openSheet('setSheet')`);
  for (const [id, k] of [['durOpts', 124], ['vsizeOpts', 'normal'], ['vfmtOpts', 'port']])
    await page.click(`#${id} [data-k="${k}"]`);
  await page.eval(`closeSheet()`);
  const big = await page.sentRequest('zvi1 normale portrait');
  assert.deepEqual([big.frames, big.width, big.height], [124, 480, 864]);
  // retenus par la page, sous video seulement (les clés d'avant inchangées)
  await page.goto(bench.url + '/');
  await page.modelsSeen(2);
  assert.deepEqual(await page.eval(`[videoFrames(videoModel()), ...currentDims()]`), [124, 480, 864]);
  assert.deepEqual(await page.eval(`JSON.parse(localStorage.getItem('qwen-opt')).video`),
    { frames: 124, size: 'normal', orient: 'port' });
  await page.chooseModel('qwen');                  // Qwen retrouve ses réglages
  assert.equal(await displayed('stepRow'), true, 'Étapes cachées avec Qwen');
  assert.equal(await displayed('videoRows'), false, 'lignes de la vidéo montrées avec Qwen');
  await bench.idle();
  page.assertNoErrors();
});

test('Vidéo : une seule image jointe, image de départ ; Dessiner grisé, pas de campagne', async () => {
  await freshVideo();
  await addImages(2);
  await page.waitFor(`$('toastBox').textContent.includes('une seule image de départ')`, { what: 'surplus annoncé' });
  assert.equal(await page.eval(`inputImages.length`), 1);
  assert.equal(await page.eval(`$('refs').classList.contains('full')`), true, 'ajout encore proposé');
  assert.equal(await page.eval(`$('drawBtn').disabled`), true, 'Dessiner permis avec la vidéo');
  assert.equal(await page.eval(`$('campSwitch').hidden`), true, 'campagne proposée avec la vidéo');
  // « Éditer » (visionneuse, images d'entrée) : refusé de même, la saisie a déjà son image de départ
  await page.eval(`$('toastBox').textContent = ''`);
  await page.eval(`(() => { const c = document.createElement('canvas'); c.width = c.height = 64;
    return useAsEditInput('autre.png', c.toDataURL()); })()`);
  await page.waitFor(`$('toastBox').textContent.includes('une seule image de départ')`, { what: 'Éditer refusé' });
  assert.equal(await page.eval(`inputImages.length`), 1, 'Éditer ajoute une deuxième image à la vidéo');
  const req = await page.sentRequest('zvi2 depart');
  assert.deepEqual([req.mode, req.ref_images.length, typeof req.init_image, req.frames],
    ['t2i', 0, 'string', 56]);
  assert.match(req.init_image, /^data:image\/png/);
  await bench.idle();
  page.assertNoErrors();
});

test('Vidéo finie : pile et visionneuse, sans Éditer, Dessiner ni Avant, Copier grisé, en .webp', async () => {
  await freshVideo();
  await page.generate('zvi3 finie');
  await page.viewPile('zvi3 finie');
  const it = await page.eval(`vList[vIndex]`);
  assert.match(it.name, /\.webp$/);
  assert.equal(it.frames, 56);
  assert.match(await page.eval(`$('vImg').src`), /\.webp/);
  assert.deepEqual(await page.eval(`[$('vEdit').hidden, $('vDraw').hidden, $('vCopy').disabled, $('vBefore').hidden]`),
    [true, true, true, true]);
  assert.match(await page.eval(`$('vDl').download`), /\.webp$/);
  assert.match(await page.eval(`$('vChips').textContent`), /H3-VIDEO/);
  await page.eval(`closeViewer()`);
  await page.keepPile();
  await page.tab('tirages');
  await page.waitFor(`histItems.some(it => it.prompt === 'zvi3 finie')`, { what: 'vidéo dans les Tirages' });
  // vignette fixe : la miniature JPEG du serveur (sa première image)
  const thumb = await page.eval(`thumbOf(histItems.find(it => it.prompt === 'zvi3 finie'))`);
  const r = await page.eval(`fetch(${JSON.stringify(thumb)}).then(r => r.headers.get('Content-Type'))`);
  assert.equal(r, 'image/jpeg');
  await page.eval(`openViewer(histItems.findIndex(it => it.prompt === 'zvi3 finie'), histItems)`);
  assert.deepEqual(await page.eval(`[$('vEdit').hidden, $('vDraw').hidden, $('vCopy').disabled]`), [true, true, true]);
  await page.eval(`openViewer(histItems.findIndex(it => it.prompt !== 'zvi3 finie'), histItems)`).catch(() => {});
  await page.eval(`closeViewer()`);
  page.assertNoErrors();
});

test('Vidéo : Relancer et Reprendre gardent sa durée ; une durée hors forme prend celle des Réglages', async () => {
  await freshVideo();
  await page.eval(`opt.video = { frames: 73, size: 'small', orient: 'land' }; saveOpt(); refreshChoices()`);
  await page.generate('zvi4 trois');
  await page.waitFor(`pileItems.some(it => it.prompt === 'zvi4 trois')`, { what: 'vidéo dans la pile' });
  await page.keepPile();
  await waitUntil(() => bench.kept('zvi4 trois'), { what: 'vidéo gardée' });
  await bench.idle();
  await page.eval(`window.sentBodies = []; const f = window.fetch; window.fetch = (u, o) => {
    if (String(u).endsWith('/api/generate')) sentBodies.push(JSON.parse(o.body)); return f(u, o); }`);
  // une image reconstruite du journal (sans la demande gardée par la page)
  const item = `(await (await fetch('/api/history')).json()).find(it => it.prompt === 'zvi4 trois')`;
  await page.eval(`opt.video = { frames: 124, size: 'normal', orient: 'port' }; saveOpt(); refreshChoices()`);
  await page.eval(`(async () => { await againFrom(${item}); })()`);
  await page.waitFor(`sentBodies.length === 1`, { what: 'relance envoyée' });
  const again = await page.eval(`sentBodies[0]`);
  assert.deepEqual([again.model, again.frames, again.width, again.height, again.steps, again.preview],
    ['video', 73, 480, 288, 4, false]);
  await page.eval(`(async () => { await againFrom({ ...${item}, frames: 'x' }); })()`);
  await page.waitFor(`sentBodies.length === 2`, { what: 'relance hors forme envoyée' });
  assert.equal(await page.eval(`sentBodies[1].frames`), 124, 'durée hors forme : pas celle des Réglages');
  // Reprendre : le modèle, la durée, la taille et le format de la vidéo dans les Réglages
  await page.chooseModel('qwen');
  await page.eval(`(async () => { await resumeFrom(${item}); })()`);
  await page.waitFor(`videoModel() !== null`, { what: 'vidéo reprise' });
  assert.deepEqual(await page.eval(`[videoFrames(videoModel()), ...currentDims()]`), [73, 480, 288]);
  await bench.idle();
  page.assertNoErrors();
});

test('Vidéo en cours : l\'étape et la fin prévue s\'affichent, sans aperçu', async () => {
  await freshVideo();
  await page.generate('HOLD=video-carte@2 zvi5 en cours');
  await page.waitFor(`!$('runCard').hidden && $('runStep').textContent === 'Étape 2 / 4'
    && /^fin vers \\d+ h \\d\\d$/.test($('runEta').textContent)`, { what: 'étape 2 / 4 et sa fin prévue' });
  assert.equal(await page.eval(`pageJobs.at(-1).req.preview`), false);
  bench.release('video-carte');
  await page.waitFor(`pileItems.some(it => it.prompt === 'HOLD=video-carte@2 zvi5 en cours')`,
    { what: 'vidéo finie dans la pile' });
  await bench.idle();
  page.assertNoErrors();
});

test('Vidéo dans l\'espace privé : la demande part en privé, nommée en .webp dans la pile privée', async () => {
  await freshVideo();
  await page.enterPrivate('code-video-1');
  await page.modelsSeen(2);
  const req = await page.sentRequest('zvi6 privee');
  assert.deepEqual([req.private, req.model, req.frames], [true, 'video', 56]);
  await page.waitFor(`pileItems.some(it => it.prompt === 'zvi6 privee')`, { what: 'vidéo dans la pile privée' });
  assert.match(await page.eval(`pileItems.find(it => it.prompt === 'zvi6 privee').name`), /^prive_[0-9a-f]{8}\.webp$/);
  await bench.idle();
  page.assertNoErrors();
});
