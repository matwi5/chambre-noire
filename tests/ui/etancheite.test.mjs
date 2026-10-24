// Étanchéité de l'espace privé, dans la vue du téléphone : après un parcours privé complet (pile et son Jeter en
// attente, Tirages, visionneuse, images d'entrée, lot, Labo et sa file, prompts enregistrés, saisie, suppression),
// puis la sortie par « Sortir » ou par la fermeture que décide le Mac, rien de privé ne reste dans la page : ni dans
// le HTML (attributs et textes cachés compris), ni dans les champs, ni dans la mémoire de la page (toutes ses
// variables globales et leur contenu : listes d'images, générations suivies, images prêtes, prompts, file…), ni dans
// localStorage (page.leaks du pilote). La recherche porte sur des marqueurs : identifiants des images, des générations
// et des lots privés, mots des prompts privés, routes /api/private/ et noms prive_….
// Les deux premiers tests se suivent : le second rouvre l'espace et les Tirages que le premier a remplis. Le
// troisième sort de l'espace pendant qu'un aperçu privé est révélé sur le canevas de la carte en cours, que
// page.leaks ne fouille pas : il en lit les pixels. Les deux derniers simulent le retour par « Retour » sur une page
// fermée dans l'espace (pageshow persisted) : affichage et saisie privés effacés, espace reverrouillé avant tout état
// lu, même si le Mac ne répond pas d'abord.
//   venv/bin/python tests/check.py --quick --ui tests/ui/etancheite.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page, kept;                     // kept : images privées que le premier test laisse

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok')`, { what: 'moteur prêt affiché' });
});

after(async () => {
  bench?.release('etanche');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const post = (url, body) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
const ref = `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const x = c.getContext('2d'); x.fillStyle = '#a03070'; x.fillRect(0, 0, 256, 256);
  return c.toDataURL('image/png'); })()`;
const generate = extra => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 2, cfg: 1, seed: -1,
  preview: false, ref_images: [], private: true, ...${extra} }).then(r => r.status)`);
// mots des prompts privés : chacun n'apparaît que dans l'espace privé
const WORDS = ['zqE0pile', 'zqE1edition', 'zqE2lot', 'zqE3resultat', 'zqE4file', 'zqE5titre', 'zqE5texte',
  'zqE6saisie', 'zqE7supprimee', 'zqE8vignette', 'zqE9saisie'];

async function enter() {
  const exists = await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.exists)`);
  assert.equal(await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}

// parcours privé : tout ce qui affiche une donnée privée est ouvert au moins une fois ; renvoie les marqueurs
async function privateTour() {
  assert.equal(await generate(`{ mode: 'edit', prompt: 'zqE1edition', ref_images: [${ref}] }`), 202);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE2lot', count: 2 }`), 202);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE7supprimee' }`), 202);
  await bench.idle();
  // une génération de la page jusqu'à la pile du Labo ; toutes gardées par ✓ (Tirages privés), sauf une dernière,
  // ouverte en grand puis laissée dans la pile ; puis une autre gardée en file
  await page.typePrompt('zqE3resultat');
  await page.click('#go');
  await page.waitFor(`pileItems.length === 5 && (img => img && img.complete && img.naturalWidth > 0)
    ($('pile').querySelector('[data-k="0"] img'))`, { what: 'images privées dans la pile', timeout: 30000 });
  assert.equal(await page.keepPile(), 5);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'zqE0pile' }`), 202);
  await page.waitFor(`pileItems.length === 1 && (img => img && img.complete && img.naturalWidth > 0)
    ($('pile').querySelector('[data-k="0"] img'))`, { what: 'image privée dans la pile', timeout: 30000 });
  await page.click('#pile [data-k="0"] [data-open]');
  await page.waitFor(`$('vImg').complete && $('vImg').naturalWidth > 0`, { what: 'image de la pile en grand' });
  await page.eval(`closeViewer()`);
  assert.equal(await generate(`{ mode: 't2i', prompt: 'HOLD=etanche zqE4file' }`), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pageJobs.some(p => p.private && p.adopted)`, { what: 'génération privée suivie en file' });
  // une édition de la page en file derrière elle : sa carte porte la vignette de son image d'entrée (data:)
  await page.eval(`(async () => { const c = document.createElement('canvas'); c.width = c.height = 200;
    const x = c.getContext('2d'); x.fillStyle = '#5040c0'; x.fillRect(0, 0, 200, 200); x.fillStyle = '#e0b030';
    x.fillRect(40, 60, 90, 30); inputImages.push(await toEntry('zqE8.png', c.toDataURL('image/png')));
    renderInputs(); })()`);
  await page.typePrompt('zqE8vignette');
  await page.click('#go');
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('queueChip').hidden`, { what: 'pastille de la file' });
  await page.click('#queueChip');                  // la file dans sa feuille
  await page.waitFor(`!!$('queueList').querySelector('.qcard.own img[src^="data:"]')
    && $('queueList').textContent.includes('zqE8vignette')`, { what: 'carte privée avec sa vignette d\'entrée' });
  const thumb = await page.eval(`$('queueList').querySelector('.qcard.own img').getAttribute('src')`);
  await page.eval(`closeSheet()`);
  await page.typePrompt('zqE6saisie');             // saisie privée laissée en place : texte et image d'entrée
  await page.eval(`(async () => { inputImages.push(await toEntry('zqE9saisie.png', ${ref})); renderInputs(); })()`);
  // prompts enregistrés de l'espace
  assert.equal(await post('/api/private/prompts', { title: 'zqE5titre', text: 'zqE5texte', usage: 't2i' }), 200);
  await page.eval(`openPrompts()`);
  await page.waitFor(`$('promptSheet').textContent.includes('zqE5titre')`, { what: 'prompt privé affiché' });
  await page.eval(`closeSheet()`);
  // galerie, suppression d'une image, visionneuse, images d'entrée, feuille du lot
  await page.tab('tirages');
  await page.waitFor(`histItems.length === 5 && histItems.every(it => it.private)`, { what: 'galerie privée' });
  await page.eval(`(() => { openViewer(histItems.findIndex(it => it.prompt === 'zqE7supprimee'), histItems);
    viewerAction('delete'); })()`);                // sans attendre la fin : elle attend la confirmation
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de suppression' });
  await page.eval(`answer(true)`);
  await page.waitFor(`histItems.length === 4`, { what: 'image privée supprimée' });
  const markers = await page.eval(`[...histItems.map(it => it.id), ...pageJobs.filter(p => p.private).map(p => p.id),
    ...histItems.filter(it => it.lot).map(it => it.lot.id), ...pileItems.map(it => it.id)]`);
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0)`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  await page.eval(`closeInputs(); openViewer(histItems.findIndex(it => it.lot), histItems); openLot()`);
  await page.waitFor(`openedSheet === $('lotSheet')`, { what: 'feuille du lot privé' });
  await page.tab('labo');                          // (visionneuse et feuille du lot toujours ouvertes)
  await page.click('#pileNo');                     // un Jeter privé qui attend la fin de son bandeau à la sortie
  await page.waitFor(`!!discarding && !$('undoBar').hidden`, { what: 'Jeter privé en attente' });
  return [...new Set([...markers, ...WORDS, '/api/private/', 'prive_', thumb.slice(-120, -40)])];
}

// marqueurs trouvés dans la page (aside : la saisie privée mise de côté, asideInput, compte)
const scan = (markers, aside) => page.leaks(markers, { skip: aside ? [] : ['asideInput'] });

test('« Sortir » : plus rien de l\'espace privé dans la page', async () => {
  await enter();
  const markers = await privateTour();
  kept = await page.eval(`histItems.length`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await scan(markers, true), [], 'données privées restées dans la page');
  assert.equal(await page.eval(`$('undoBar').hidden`), true, 'bandeau du Jeter privé resté');
  page.assertNoErrors();
});

test('fermeture par le Mac : plus rien de l\'espace privé dans la page (hors saisie mise de côté)', async () => {
  await enter();
  await page.tab('tirages');
  await page.waitFor(`histItems.length === ${kept} && histItems.every(it => it.private)`, { what: 'galerie privée' });
  const markers = [...new Set([...await page.eval(`histItems.map(it => it.id)`), ...WORDS, '/api/private/', 'prive_'])];
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0); openPrompts()`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  // session close par le serveur, sans « Sortir » : la page l'apprend à son interrogation suivante
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé' });
  // visionneuse et images d'entrée ouvertes sur une image privée : fermer les images d'entrée recalcule la barre d'état
  // pendant que la visionneuse montre encore l'image privée ; le cache tints ne doit pas garder son adresse
  assert.deepEqual(await scan(markers, false), [], 'données privées restées dans la page');
  bench.release('etanche');
  await bench.idle();
  page.assertNoErrors();
});

test('« Sortir » pendant la révélation d\'une génération privée : son canevas est vidé', async () => {
  await enter();
  await page.tab('labo');
  await page.eval(`$('previewChk').checked = true; opt.steps = 'high'; saveOpt(); refreshChoices()`);
  await page.typePrompt('SLOW=0.4 zqE10revelee');
  await page.click('#go');
  await page.waitFor(`shown && shown.private && !!reveal.img`, { what: 'aperçu privé en mosaïque', timeout: 30000 });
  assert.ok((await page.canvasInk('#revealCanvas')).ink > 0, 'mosaïque dessinée');
  // /api/status retenu : une réponse demandée dans l'espace (qui le dit encore ouvert) n'arrive qu'après « Sortir »,
  // et les suivantes pas avant la fin des vérifications : la page ne montre que ce qu'elle sait de l'espace public
  await page.holdFetch(`u => u === '/api/status'`);
  await page.eval(`void (window.lateStatus = refreshStatus())`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await page.canvasInk('#revealCanvas'), { width: 0, height: 0, ink: 0 }, 'aperçu privé resté');
  assert.deepEqual(await page.eval(`[reveal.img, $('runCard').hidden, $('queueChip').hidden, queueState.length]`),
    [null, true, true, 0], 'génération ou file privée à l\'écran');
  assert.deepEqual(await scan(['zqE10revelee'], true), [], 'données privées restées dans la page');
  await page.releaseFetch();
  await page.eval(`lateStatus`);   // la réponse d'avant la sortie, puis une nouvelle
  assert.equal(await page.eval(`inPrivate()`), false, 'réponse d\'avant la sortie : l\'espace rouvert dans la page');
  assert.deepEqual(await scan(['zqE10revelee'], true), [], 'données privées revenues dans la page');
  await bench.idle();
  page.assertNoErrors();
});

// page restaurée depuis la mémoire du navigateur (« Retour », bfcache) : Chrome sans écran ne la rejoue pas de façon
// fiable, l'événement pageshow (persisted) est simulé ; le verrouillage de la fermeture (pagehide) n'a pas eu lieu,
// comme quand il se perd : c'est le reverrouillage du retour qui ferme l'espace
const restored = `dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))`;
// espace ouvert, une image privée dans la pile affichée et une saisie privée ; renvoie les marqueurs privés
async function privateScreen(word) {
  await enter();
  await page.tab('labo');
  assert.equal(await generate(`{ mode: 't2i', prompt: '${word}pile' }`), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pileItems.some(it => it.prompt === '${word}pile') && (img => img && img.complete
    && img.naturalWidth > 0)($('pile').querySelector('[data-k="0"] img'))`, { what: 'image privée dans la pile',
    timeout: 30000 });
  await page.typePrompt(`${word}saisie`);
  const ids = await page.eval(`pileItems.map(it => it.id)`);
  return [...ids, `${word}pile`, `${word}saisie`, '/api/private/', 'prive_'];
}

test('« Retour » vers une page de l\'espace privé : affichage et saisie privés effacés, espace reverrouillé',
  async () => {
  const markers = await privateScreen('zqE11');
  // dès l'événement, avant toute réponse du Mac : plus rien de l'espace à l'écran, et le champ (qui avait le curseur)
  // l'a perdu : les touches suivantes n'iraient pas dans la saisie publique sans qu'on le voie
  await page.eval(`openComposer(); $('prompt').focus()`);
  await page.waitFor(`document.activeElement === $('prompt')`, { what: 'curseur dans le champ privé' });
  assert.deepEqual(await page.eval(`(() => { ${restored}; return [inPrivate(),
    document.documentElement.classList.contains('priv'), pileItems.length, $('prompt').value,
    document.activeElement === $('prompt')]; })()`), [false, false, 0, '', false]);
  assert.equal(await page.eval(`$('toastBox').textContent`), 'Espace privé verrouillé à la fermeture de la page');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.private.unlocked)`,
    { what: 'espace reverrouillé sur le Mac' });
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`inPrivate()`), false);
  assert.deepEqual(await scan(markers, true), [], 'données privées restées dans la page (saisie comprise)');
  page.assertNoErrors();
});

test('« Retour », Mac injoignable au reverrouillage : la page ne rentre pas dans l\'espace resté ouvert', async () => {
  await privateScreen('zqE12');
  // le verrouillage n'arrive pas au Mac : sa session reste ouverte tant que la page ne l'a pas fermée
  await page.eval(`(() => { const f = window.zqFetch = window.fetch; window.zqLocks = 0;
    window.fetch = (u, ...a) => String(u) === '/api/private/lock' ? (zqLocks++, Promise.reject(new TypeError('coupé')))
      : f(u, ...a); })()`);
  await page.eval(restored);
  await page.eval(`refreshStatus()`);
  assert.equal(await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.unlocked)`), true,
    'session du Mac encore ouverte');
  assert.deepEqual(await page.eval(`[inPrivate(), pileItems.length, $('lamp').classList.contains('err')]`),
    [false, 0, true], 'page rentrée dans l\'espace sans code');
  // refermée avant que le Mac ait accepté le verrouillage : elle le renvoie, comme une page fermée dans l'espace
  const sent = await page.eval(`zqLocks`);
  await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))`);
  assert.equal(await page.eval(`zqLocks`), sent + 1, 'verrouillage renvoyé à la fermeture');
  // le Mac répond de nouveau et le code privé est retapé : l'espace s'ouvre, sans être refermé par le reverrouillage
  await page.eval(`window.fetch = zqFetch`);
  await page.eval(`($('puCode').value = ${JSON.stringify(CODE)}, privUnlock())`);
  assert.equal(await page.eval(`inPrivate()`), true, 'espace rouvert par le code');
  assert.equal(await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.unlocked)`), true);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  await bench.idle();
  page.assertNoErrors();
});

test('« Retour » vers une page fermée hors de l\'espace : la saisie privée mise de côté est oubliée', async () => {
  await enter();
  await page.typePrompt('zqE13aside');
  // fermeture par le Mac (15 minutes) : la saisie privée reste en mémoire de la page pour le retour dans l'espace
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé par le Mac' });
  assert.notDeepEqual(await scan(['zqE13aside'], true), [], 'saisie privée mise de côté (prémisse)');
  await page.eval(`${restored}; refreshStatus()`);
  assert.deepEqual(await scan(['zqE13aside'], true), [], 'saisie privée restée en mémoire après le retour');
  page.assertNoErrors();
});
