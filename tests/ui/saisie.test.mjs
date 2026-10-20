// Saisie, dans la vue du téléphone : photos choisies d'un coup en Éditer, champs vidés après « Générer », saisie propre
// à chaque espace (public, privé), variantes en Éditer et en Dessiner hors campagne.
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
let bench, chrome, page, dir, refusal = null, held = null;

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-photos-'));
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  // demandes de génération interceptées (Fetch.enable, voir generate) : le Mac répond par une erreur, ou est injoignable ;
  // 'hold' : la demande attend que le test la laisse partir (held)
  page.on('Fetch.requestPaused', p => refusal === 'hold' ? held.resolve(p.requestId)
    : refusal === 'unreachable' ? page.send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'ConnectionRefused' })
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
// du réseau de Chrome. Demande acceptée : la page passe à En cours, puis le test revient à l'onglet de saisie ;
// refusée : elle reste sur l'onglet
async function generate({ refuse = null } = {}) {
  refusal = refuse;
  if (refuse) await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Request' }] });
  const jobsBefore = await page.eval(`pageJobs.length`), tab = await page.eval(`mode`);
  await page.click('#go');
  if (refuse) {
    const shown = refuse === 'unreachable' ? 'Serveur injoignable' : 'Erreur : moteur non prêt';
    await page.waitFor(`$('toast').textContent.startsWith(${JSON.stringify(shown)})`, { what: 'refus affiché' });
    await page.send('Fetch.disable');
    assert.equal(await page.eval(`mode`), tab, 'demande refusée : la page reste sur l\'onglet');
  } else {
    await page.waitFor(`pageJobs.length > ${jobsBefore} && mode === 'run'`,
      { what: 'génération suivie, page En cours' });
    await page.click(`#tabbar [data-pane="${tab}"]`);
  }
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

test('Variantes : proposées en Éditer et en Dessiner hors campagne, la demande part en lot', async () => {
  const countShown = () => page.eval(`getComputedStyle($('countRow')).display !== 'none'`);
  const pick = k => page.eval(`$('countOpts').querySelector('[data-k="${k}"]').click()`);
  // lot de la dernière demande : sa taille et son marqueur de campagne
  const lastLot = () => page.eval(`(({ size, campaign }) => ({ size, campaign }))(pageJobs.at(-1).lot)`);
  // générations des tests précédents finies d'abord : sinon la page neuve les reprend (lancées par ce navigateur),
  // ce qui ajoute des générations et des messages de fin à ceux comptés plus bas (banc chargé : --ui complet)
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queued)`,
    { what: 'file du banc vide', timeout: 60000 });
  await freshEdit();
  await watchToasts();
  await page.setFiles('#edit_files', photos(1));
  await page.waitFor(`editImages.length === 1`, { what: 'une image' });
  assert.equal(await countShown(), true, 'rangée des images en Éditer');
  await pick(2);
  await type('edit', 'deux essais d\'un chapeau');
  await generate();
  assert.deepEqual(await lastLot(), { size: 2, campaign: false });
  // campagne : la rangée disparaît et le nombre choisi est ignoré (une image par photo)
  await page.click('#campChk');
  await page.waitFor(`campaignOn`, { what: 'campagne activée' });
  assert.equal(await countShown(), false, 'pas de variantes en campagne');
  await page.setFiles('#edit_files', photos(3));
  await page.waitFor(`editImages.length === 3`, { what: 'trois photos' });
  await type('edit', 'voiture bleue');
  await generate();
  assert.deepEqual(await lastLot(), { size: 3, campaign: true });
  // fin de chaque image avant la dernière : « Image » pour des variantes d'édition, « Photo » pour une campagne
  // derrière les générations des tests précédents, toutes les pages d'interface et le banc tournant en même temps
  await page.waitFor(`pageJobs.length === 5 && pageJobs.every(p => p.result)`,
    { what: 'deux lots terminés', timeout: 60000 });
  const ends = await page.eval(`seenToasts.filter(t => / sur \\d prête$/.test(t))`);
  assert.deepEqual(ends, ['Image 1 sur 2 prête', 'Photo 1 sur 3 prête', 'Photo 2 sur 3 prête']);
  await fresh('mask');
  await page.setFiles('#mask_file', photos(1));
  await page.waitFor(`!!maskImage`, { what: 'image à retoucher chargée' });
  assert.equal(await countShown(), true, 'rangée des images en Dessiner');
  await pick(3);
  await paint();
  await type('mask', 'une fenêtre ouverte');
  await generate();
  assert.deepEqual(await lastLot(), { size: 3, campaign: false });
  const masks = `pageJobs.slice(-3)`;
  assert.equal(await page.eval(`${masks}.length === 3 && ${masks}.every(p => p.tab === 'mask' && p.lot.size === 3)`),
    true);
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

// ------------------------------------------------------------ saisie propre à chaque espace
const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
// entrée dans l'espace privé (créé la première fois) ; la page le voit à son interrogation suivante de /api/status
async function enterPrivate() {
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
// fermeture de l'espace par le Mac (15 minutes sans requête privée) : la session est fermée sans passer par « Sortir »
async function closedByMac() {
  assert.equal(await post('/api/private/lock'), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
}
const goTab = pane => page.click(`#tabbar [data-pane="${pane}"]`);
const value = tab => page.eval(`$('${tab}_prompt').value`);
// onglets marqués (supprimés) : une pastille dessinée sur le bouton (pseudo-élément ::after) ou une infobulle
const marked = () => page.eval(`[...document.querySelectorAll('#tabbar button')]
  .filter(b => getComputedStyle(b, '::after').content !== 'none' || b.title).length`);

test('espaces : la saisie privée disparaît à « Sortir », la saisie publique revient intacte', async () => {
  await fresh('t2i');
  await type('t2i', 'un phare public');
  await goTab('edit');
  await page.setFiles('#edit_files', photos(1));
  await page.waitFor(`editImages.length === 1`, { what: 'une image publique' });
  await type('edit', 'chapeau public');
  await goTab('mask');
  await page.setFiles('#mask_file', photos(1));
  await page.waitFor(`!!maskImage`, { what: 'image à retoucher publique' });
  await paint();
  await type('mask', 'fenêtre publique');

  await enterPrivate();                            // première entrée : saisie privée vide
  assert.deepEqual(await page.eval(`[$('t2i_prompt').value, $('edit_prompt').value, $('mask_prompt').value, editImages.length, !!maskImage]`),
    ['', '', '', 0, false]);
  assert.equal(await page.eval(`$('paintWrap').style.display === 'none' && !$('pane-mask').classList.contains('has-img')`), true);
  await type('mask', 'fenêtre secrète');
  await goTab('t2i');
  await type('t2i', 'un phare secret');
  await goTab('edit');
  await page.setFiles('#edit_files', photos(2));
  await page.waitFor(`editImages.length === 2`, { what: 'deux images privées' });
  await type('edit', 'chapeau secret');
  await generate();                                // génération privée : la saisie privée de l'onglet est vidée
  assert.equal(await page.eval(`pageJobs.at(-1).private`), true);
  assert.deepEqual(await page.eval(`[$('edit_prompt').value, editImages.length]`), ['', 0]);
  await page.setFiles('#edit_files', photos(1));
  await page.waitFor(`editImages.length === 1`, { what: 'une image privée' });
  assert.deepEqual([await draft('t2i'), await draft('edit'), await draft('mask')], ['un phare public', 'chapeau public', 'fenêtre publique'],
    'la saisie privée n\'est jamais écrite dans le navigateur, les brouillons publics restent');

  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual([await value('t2i'), await value('edit'), await value('mask')], ['un phare public', 'chapeau public', 'fenêtre publique']);
  assert.equal(await page.eval(`editImages.length`), 1);
  assert.equal(await page.eval(`!!maskImage && $('pane-mask').classList.contains('has-img') && paintedPixels() > 0`), true, 'image à retoucher et masque publics');
  assert.equal(await marked(), 0, 'aucun onglet marqué');

  await enterPrivate();                            // « Sortir » a effacé la saisie privée
  assert.deepEqual(await page.eval(`[$('t2i_prompt').value, $('edit_prompt').value, $('mask_prompt').value, editImages.length, !!maskImage]`),
    ['', '', '', 0, false]);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('espaces : fermée par le Mac, la saisie privée attend le retour dans la page ; supprimée avec l\'espace', async () => {
  await fresh('t2i');
  await type('t2i', 'texte public');
  await enterPrivate();
  await type('t2i', 'un long texte privé');
  await closedByMac();
  assert.equal(await value('t2i'), 'texte public');
  assert.equal(await marked(), 0, 'aucun onglet marqué');
  await enterPrivate();
  assert.equal(await value('t2i'), 'un long texte privé', 'retrouvé au retour');
  await closedByMac();

  assert.equal(await post('/api/private/reset', { confirm: 'SUPPRIMER' }), 200);   // espace supprimé (sur le Mac)
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!privState.exists`, { what: 'espace supprimé vu par la page' });
  await enterPrivate();                            // recréé : rien de l'ancien espace
  assert.equal(await value('t2i'), '');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.equal(await value('t2i'), 'texte public');
  page.assertNoErrors();
});

// messages affichés depuis l'appel (chaque texte posé dans #toast, même remplacé aussitôt par un autre)
const watchToasts = () => page.eval(`(() => { window.seenToasts = []; window.toastWatch?.disconnect();
  window.toastWatch = new MutationObserver(() => seenToasts.push($('toast').textContent));
  toastWatch.observe($('toast'), { childList: true, characterData: true, subtree: true }); })()`);
const CLOSED = 'Espace privé fermé : retour dans l\'espace public';

test('espaces : fermé sans « Sortir », le champ perd le curseur et un message dit le retour dans l\'espace public', async () => {
  await fresh('t2i');
  await enterPrivate();
  await page.eval(`$('t2i_prompt').focus()`);
  assert.equal(await page.eval(`document.activeElement === $('t2i_prompt')`), true);
  await watchToasts();
  await closedByMac();                             // 15 minutes sans requête privée
  assert.equal(await page.eval(`document.activeElement === $('t2i_prompt')`), false, 'le champ a perdu le curseur');
  assert.deepEqual(await page.eval(`seenToasts`), [CLOSED]);
  assert.equal(await page.eval(`$('toast').classList.contains('on')`), true);

  await enterPrivate();                            // espace supprimé depuis le Mac pendant qu'on tape
  await page.eval(`$('edit_prompt').focus()`);
  await watchToasts();
  assert.equal(await post('/api/private/reset', { confirm: 'SUPPRIMER' }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
  assert.equal(await page.eval(`document.activeElement === $('edit_prompt')`), false, 'le champ a perdu le curseur');
  assert.deepEqual(await page.eval(`seenToasts`), [CLOSED]);

  await enterPrivate();                            // « Sortir » : la sortie est demandée, pas de message de fermeture
  await page.eval(`$('t2i_prompt').focus()`);
  await watchToasts();
  await page.click('#privExit');
  await page.waitFor(`!inPrivate() && seenToasts.length > 0`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.eval(`seenToasts`), ['Sorti de l\'espace privé']);
  page.assertNoErrors();
});

test('espaces : une demande privée acceptée après la fermeture par le Mac ne vide pas la saisie publique', async () => {
  await fresh('t2i');
  await type('t2i', 'texte public');
  await enterPrivate();
  await type('t2i', 'demande privée');
  refusal = 'hold'; held = Promise.withResolvers();
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Response' }] });
  await page.click('#go');
  const requestId = await held.promise;            // le Mac a accepté la demande privée, la page n'a pas encore sa réponse
  await closedByMac();                             // pendant l'attente : la saisie publique revient à l'écran
  await page.send('Fetch.continueRequest', { requestId });
  await page.send('Fetch.disable');
  refusal = null;
  // demande acceptée : sa saisie privée, mise de côté par la fermeture, est vidée de ce qui est parti (le journal n'en
  // dit rien : une ligne privée finie hors de l'espace n'y entre pas)
  await page.waitFor(`asideInput && asideInput.text.t2i === ''`, { what: 'demande acceptée' });
  assert.equal(await page.eval(`pageJobs.some(p => p.private)`), false, 'hors de l\'espace, la page ne suit pas la génération privée');
  assert.equal(await value('t2i'), 'texte public', 'la saisie publique reste');
  assert.equal(await draft('t2i'), 'texte public', 'son brouillon aussi');
  await enterPrivate();
  assert.equal(await value('t2i'), '', 'c\'est la saisie privée de la demande qui est vidée');
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

test('Créer : un texte tapé pendant l\'envoi reste quand la demande est acceptée', async () => {
  await fresh('t2i');
  await type('t2i', 'premier texte');
  refusal = 'hold'; held = Promise.withResolvers();
  await page.send('Fetch.enable', { patterns: [{ urlPattern: '*/api/generate', requestStage: 'Response' }] });
  const jobsBefore = await page.eval(`pageJobs.length`);
  await page.click('#go');
  const requestId = await held.promise;            // le Mac a accepté, la page n'a pas encore sa réponse
  await type('t2i', 'texte suivant');
  await page.send('Fetch.continueRequest', { requestId });
  await page.send('Fetch.disable');
  refusal = null;
  await page.waitFor(`pageJobs.length > ${jobsBefore}`, { what: 'demande acceptée' });
  assert.equal(await value('t2i'), 'texte suivant');
  assert.equal(await draft('t2i'), 'texte suivant');
  page.assertNoErrors();
});
