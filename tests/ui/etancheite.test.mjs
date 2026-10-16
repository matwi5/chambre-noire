// Étanchéité de l'espace privé, dans la vue du téléphone : après un parcours privé complet (galerie, visionneuse,
// images d'entrée, lot, zone de résultat, file, prompts enregistrés, saisie, suppression), puis la sortie par
// « Sortir » ou par la fermeture que décide le Mac, rien de privé ne reste dans la page : ni dans le HTML (attributs et
// textes cachés compris), ni dans les champs, ni dans la mémoire de la page (listes d'images, générations suivies,
// images prêtes, prompts, file), ni dans localStorage. La recherche porte sur des marqueurs : identifiants des images
// et des générations privées, mots des prompts privés, routes /api/private/ et noms prive_….
// Les deux tests se suivent : le second rouvre l'espace et la galerie que le premier a remplis.
//   node --test tests/ui/etancheite.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/etancheite.test.mjs)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page, kept;                     // kept : images privées que le premier test laisse

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
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
// texte tapé dans Créer (événement input, comme au clavier)
const type = text => page.eval(`(() => { const t = $('t2i_prompt'); t.value = ${JSON.stringify(text)};
  t.dispatchEvent(new Event('input')); })()`);
const idle = () => page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`,
  { what: 'Mac au repos', timeout: 30000 });
// mots des prompts privés : chacun n'apparaît que dans l'espace privé
const WORDS = ['zqE1edition', 'zqE2lot', 'zqE3resultat', 'zqE4file', 'zqE5titre', 'zqE5texte', 'zqE6saisie',
  'zqE7supprimee'];

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
  await idle();
  // une génération de la page jusqu'à la zone de résultat, puis une autre gardée en file
  await page.click('#tabbar [data-pane="t2i"]');
  await type('zqE3resultat');
  await page.click('#go');
  await page.waitFor(`shown && shown.result && $('stageImg').complete && $('stageImg').naturalWidth > 0`,
    { what: 'image privée dans la zone de résultat', timeout: 30000 });
  assert.equal(await generate(`{ mode: 't2i', prompt: 'HOLD=etanche zqE4file' }`), 202);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`pageJobs.some(p => p.private && p.adopted)`, { what: 'génération privée suivie en file' });
  await type('zqE6saisie');
  // prompts enregistrés de l'espace
  assert.equal(await post('/api/private/prompts', { title: 'zqE5titre', text: 'zqE5texte', usage: 't2i' }), 200);
  await page.eval(`openPrompts()`);
  await page.waitFor(`$('promptSheet').textContent.includes('zqE5titre')`, { what: 'prompt privé affiché' });
  await page.eval(`closeSheet()`);
  // galerie, suppression d'une image, visionneuse, images d'entrée, feuille du lot
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length === 5 && histItems.every(it => it.private)`, { what: 'galerie privée' });
  await page.eval(`(() => { openViewer(histItems.findIndex(it => it.prompt === 'zqE7supprimee'), histItems);
    viewerAction('delete'); })()`);                // sans attendre la fin : elle attend la confirmation
  await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de suppression' });
  await page.eval(`answer(true)`);
  await page.waitFor(`histItems.length === 4`, { what: 'image privée supprimée' });
  const markers = await page.eval(`[...histItems.map(it => it.id), ...pageJobs.filter(p => p.private).map(p => p.id),
    ...histItems.filter(it => it.lot).map(it => it.lot.id)]`);
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0)`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  await page.eval(`closeInputs(); openViewer(histItems.findIndex(it => it.lot), histItems); openLot()`);
  await page.waitFor(`openedSheet === $('lotSheet')`, { what: 'feuille du lot privé' });
  return [...new Set([...markers, ...WORDS, '/api/private/', 'prive_'])];
}

// marqueurs trouvés dans la page : HTML, champs, mémoire de la page (aside : la saisie privée mise de côté compte)
const scan = (markers, aside) => page.eval(`((m) => {
  const text = v => { try { return JSON.stringify(v) || ''; } catch (e) { return String(v); } };
  let store = ''; try { store = text({ ...localStorage }); } catch (e) {}
  const doc = document.documentElement.cloneNode(true);   // le code de la page nomme les routes privées : écarté
  doc.querySelectorAll('script').forEach(s => s.remove());
  const places = { page: doc.outerHTML,
    champs: [...document.querySelectorAll('input, textarea')].map(e => e.value).join('\\n'),
    mémoire: text({ vList, histItems, pageJobs, ready: [...ready.keys()], prompts, queueState, lastResult, shown,
      ivOwner, editImages: editImages.map(x => x.name)${aside ? ', asideInput' : ''} }),
    localStorage: store };
  return Object.entries(places).flatMap(([where, t]) => m.filter(k => t.includes(k)).map(k => where + ' : ' + k));
})(${JSON.stringify(markers)})`);

test('« Sortir » : plus rien de l\'espace privé dans la page', async () => {
  await enter();
  const markers = await privateTour();
  kept = await page.eval(`histItems.length`);
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await scan(markers, true), [], 'données privées restées dans la page');
  page.assertNoErrors();
});

test('fermeture par le Mac : plus rien de l\'espace privé dans la page (hors saisie mise de côté)', async () => {
  await enter();
  await page.click('#tabbar [data-pane="hist"]');
  await page.waitFor(`histItems.length === ${kept} && histItems.every(it => it.private)`, { what: 'galerie privée' });
  const markers = [...new Set([...await page.eval(`histItems.map(it => it.id)`), ...WORDS, '/api/private/', 'prive_'])];
  await page.eval(`openViewer(histItems.findIndex(it => it.inputs.length), histItems); openInputs(0); openPrompts()`);
  await page.waitFor(`$('ivImg').complete && $('ivImg').naturalWidth > 0`, { what: 'image d\'entrée privée' });
  // session close par le serveur, sans « Sortir » : la page l'apprend à son interrogation suivante
  assert.equal(await post('/api/private/lock', {}), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'espace fermé' });
  assert.deepEqual(await scan(markers, false), [], 'données privées restées dans la page');
  bench.release('etanche');
  await idle();
  page.assertNoErrors();
});
