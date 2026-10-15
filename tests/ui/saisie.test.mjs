// Saisie, dans la vue du téléphone : photos choisies d'un coup en Éditer, champs vidés après « Générer ».
//   node --test tests/ui/saisie.test.mjs   (ou : venv/bin/python tests/check.py --ui)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { startBench, launchChrome } from './driver.mjs';

// PNG gris de w×h pixels (assez grand pour qu'on puisse peindre dessus en Dessiner)
function png(w, h) {
  const chunk = (type, data) => { const len = Buffer.alloc(4), crc = Buffer.alloc(4), td = Buffer.concat([Buffer.from(type), data]);
    len.writeUInt32BE(data.length); crc.writeUInt32BE(zlib.crc32(td)); return Buffer.concat([len, td, crc]); };
  const head = Buffer.alloc(13); head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 0;   // 8 bits, gris
  const rows = Buffer.alloc((w + 1) * h, 128); for (let y = 0; y < h; y++) rows[y * (w + 1)] = 0;                // filtre 0 par ligne
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', head), chunk('IDAT', zlib.deflateSync(rows)), chunk('IEND', Buffer.alloc(0))]);
}
const PNG = png(320, 320);
let bench, chrome, page, dir, refusal = null;

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-photos-'));
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // demandes de génération interceptées (Fetch.enable, voir generate) : le Mac répond par une erreur, ou est injoignable
  page.on('Fetch.requestPaused', p => refusal === 'unreachable'
    ? page.send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'ConnectionRefused' })
    : page.send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 503,
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }], body: Buffer.from('{"error":"moteur non prêt"}').toString('base64') }));
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
  if (dir) fs.rmSync(dir, { recursive: true, force: true });
});

// page neuve (brouillons effacés) sur un onglet
async function fresh(pane) {
  await page.goto(bench.url + '/');
  await page.eval(`localStorage.clear()`);
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
  if (pane !== 't2i') await page.click(`#tabbar [data-pane="${pane}"]`);
  await page.waitFor(`$('pane-${pane}').classList.contains('active')`);
}
const freshEdit = () => fresh('edit');

function photos(n) {
  return Array.from({ length: n }, (_, i) => {
    const file = path.join(dir, `photo-${String(i + 1).padStart(2, '0')}.png`);
    fs.writeFileSync(file, PNG);
    return file;
  });
}

test('Éditer : trois photos choisies d\'un coup sont toutes ajoutées, dans l\'ordre', async () => {
  await freshEdit();
  await page.setFiles('#edit_files', photos(3));
  await page.waitFor(`$('edit_thumbs').children.length === 3`, { what: 'trois vignettes', timeout: 5000 });
  assert.deepEqual(await page.eval(`editImages.map(x => x.name)`), ['photo-01.png', 'photo-02.png', 'photo-03.png']);
  page.assertNoErrors();
});

test('Éditer : sur douze photos choisies, dix sont ajoutées et le surplus est annoncé', async () => {
  await freshEdit();
  const files = photos(12);
  await page.setFiles('#edit_files', files);
  await page.waitFor(`$('toast').classList.contains('on') && $('toast').textContent.includes('2 non ajoutées')`,
    { what: 'message du surplus', timeout: 5000 });
  assert.deepEqual(await page.eval(`editImages.map(x => x.name)`), files.slice(0, 10).map(f => path.basename(f)));
  assert.equal(await page.eval(`$('edit_thumbs').children.length`), 10);
  page.assertNoErrors();
});

// texte tapé dans le champ d'un onglet, comme au clavier (le brouillon est écrit)
const type = (tab, text) => page.eval(`(() => { const t = $('${tab}_prompt'); t.value = ${JSON.stringify(text)}; t.dispatchEvent(new Event('input')); })()`);
const draft = tab => page.eval(`localStorage.getItem('qwen-${tab}_prompt')`);
const settings = () => page.eval(`JSON.stringify({ opt, incogOn, campaignOn, preview: $('previewChk').checked })`);

// un trait de pinceau dans le quart haut gauche de l'image à retoucher (le bouton « Changer » en couvre le milieu) ;
// souris : événements pointeur réels
async function paint() {
  const box = await page.eval(`(() => { const c = $('paintCanvas'); c.scrollIntoView({ block: 'center' });
    const r = c.getBoundingClientRect(); return { x: r.left + r.width / 4, y: r.top + r.height / 4 }; })()`);
  for (const [kind, dx] of [['mousePressed', 0], ['mouseMoved', 4], ['mouseReleased', 4]])
    await page.send('Input.dispatchMouseEvent', { type: kind, x: box.x + dx, y: box.y, button: 'left', buttons: kind === 'mouseReleased' ? 0 : 1, clickCount: 1 });
  await page.waitFor(`paintedPixels() > 0`, { what: 'zone peinte' });
}

// « Générer » ; refuse : 'error' (le Mac répond par une erreur) ou 'unreachable' (Mac injoignable), simulés au niveau
// du réseau de Chrome
async function generate({ refuse = null } = {}) {
  refusal = refuse;
  if (refuse) await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Request' }] });
  const jobsBefore = await page.eval(`pageJobs.length`);
  await page.click('#go');
  if (refuse) {
    const shown = refuse === 'unreachable' ? 'Serveur injoignable' : 'Erreur : moteur non prêt';
    await page.waitFor(`$('toast').textContent.startsWith(${JSON.stringify(shown)})`, { what: 'refus affiché' });
    await page.send('Fetch.disable');
  } else await page.waitFor(`pageJobs.length > ${jobsBefore}`, { what: 'génération suivie par la page' });
}

test('Créer : texte et brouillon vidés quand la demande est acceptée, Réglages inchangés', async () => {
  await fresh('t2i');
  await type('t2i', 'un phare au crépuscule');
  assert.equal(await draft('t2i'), 'un phare au crépuscule');
  const opts = await settings();
  await generate();
  assert.equal(await page.eval(`$('t2i_prompt').value`), '');
  assert.equal(await draft('t2i'), null);
  assert.equal(await settings(), opts);
  assert.equal(await page.eval(`pageJobs.at(-1).prompt`), 'un phare au crépuscule', 'la génération garde son prompt');
  page.assertNoErrors();
});

test('Éditer : texte et images vidés quand la demande est acceptée', async () => {
  await freshEdit();
  await page.setFiles('#edit_files', photos(2));
  await page.waitFor(`editImages.length === 2`, { what: 'deux images' });
  await type('edit', 'mettre un chapeau');
  const opts = await settings();
  await generate();
  assert.equal(await settings(), opts);
  assert.equal(await page.eval(`$('edit_prompt').value`), '');
  assert.equal(await page.eval(`editImages.length + $('edit_thumbs').children.length`), 0);
  assert.equal(await draft('edit'), null);
  assert.equal(await page.eval(`!!pageJobs.at(-1).thumb`), true, 'la génération garde sa vignette d\'entrée');
  page.assertNoErrors();
});

test('Dessiner : texte, image à retoucher et masque vidés quand la demande est acceptée', async () => {
  await fresh('mask');
  await page.setFiles('#mask_file', photos(1));
  await page.waitFor(`!!maskImage && $('pane-mask').classList.contains('has-img')`, { what: 'image à retoucher chargée' });
  await paint();
  await type('mask', 'une fenêtre ouverte');
  const opts = JSON.parse(await settings());
  await generate();
  // le format « Image » suit l'image à retoucher : il part avec elle, comme quand on la retire à la main ; le reste des
  // Réglages ne bouge pas
  assert.equal(opts.opt.ratio, 'image');
  assert.deepEqual(JSON.parse(await settings()), { ...opts, opt: { ...opts.opt, ratio: '1:1' } });
  assert.equal(await page.eval(`$('mask_prompt').value`), '');
  assert.equal(await page.eval(`maskImage === null && !$('pane-mask').classList.contains('has-img') && $('paintWrap').style.display === 'none'`), true);
  assert.equal(await page.eval(`paintedPixels()`), 0, 'masque effacé');
  page.assertNoErrors();
});

test('Éditer en campagne : photos vidées, interrupteur Campagne inchangé', async () => {
  await freshEdit();
  await page.click('#campChk');
  await page.waitFor(`campaignOn`, { what: 'campagne activée' });
  await page.setFiles('#edit_files', photos(2));
  await page.waitFor(`editImages.length === 2`, { what: 'deux photos' });
  await type('edit', 'voiture bleue');
  await generate();
  assert.equal(await page.eval(`editImages.length + $('edit_thumbs').children.length`), 0);
  assert.equal(await page.eval(`campaignOn && $('campChk').checked`), true);
  await page.click('#campChk');                    // réglage retenu par le navigateur : remis comme avant
  page.assertNoErrors();
});

test('Éditer : rien n\'est vidé quand le Mac refuse la demande ou est injoignable', async () => {
  await freshEdit();
  await page.setFiles('#edit_files', photos(2));
  await page.waitFor(`editImages.length === 2`, { what: 'deux images' });
  await type('edit', 'mettre un chapeau');
  for (const refuse of ['error', 'unreachable']) {
    await generate({ refuse });
    assert.equal(await page.eval(`$('edit_prompt').value`), 'mettre un chapeau', refuse);
    assert.equal(await page.eval(`editImages.length`), 2, refuse);
    assert.equal(await draft('edit'), 'mettre un chapeau', refuse);
  }
  // Chrome note dans sa console la réponse 503 et la connexion refusée : seules erreurs attendues ici
  assert.deepEqual(page.errors.filter(e => !/503|ERR_CONNECTION_REFUSED/.test(e)), []);
  page.errors.length = 0;
});
