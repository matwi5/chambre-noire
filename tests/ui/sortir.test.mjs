// Pendant « Sortir » (la sortie retenue avant le Mac), rien ne part ni ne bouge, vérifié d'un coup, dans quatre vues
// de l'espace privé : le Labo (pile privée, saisie remplie, une génération privée en cours et une en file), la
// visionneuse de la pile, les Tirages privés et la visionneuse d'un tirage. Dans chacune, chaque raccourci clavier
// d'abord (la vue telle quelle : aucune feuille ouverte, rien de sélectionné), puis chaque bouton visible de la page,
// et ceux des feuilles qu'ils ouvrent, de tour en tour jusqu'à ce qu'aucun nouveau n'apparaisse (champ de création
// déplié d'abord ; ni liens, ni champs de fichier, ni « Annuler » du bandeau, qui effacerait un Jeter parti). Aucune
// requête privée ne part (domaine Network de Chrome : /api/private/* hors le verrouillage retenu, /api/job/*,
// /api/lot/*, /api/generate), aucun Jeter n'est lancé (bandeau), et la page ne lève aucune erreur. Règle de
// CODING_STANDARDS.md : une action qui attend revérifie exiting() et beforeHeld après l'attente.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/sortir.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, elapse, ARROWS } from './driver.mjs';

let bench, chrome, page;
const sent = [];                                   // requêtes de la page : chemin de chaque adresse

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  page.on('Network.requestWillBeSent', p => {
    if (/^https?:/.test(p.request.url)) sent.push(new URL(p.request.url).pathname); });
  await page.goto(bench.url + '/');
  await page.ready();
  await page.send('Page.setInterceptFileChooserDialog', { enabled: true });   // (aucun sélecteur de fichiers ouvert)
});

after(async () => {
  bench?.release('sortir');
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
// touches que la page écoute (raccourcis du PC, Entrée) : chacune appuyée, puis Ctrl et ⌘ + Z ; Échap, qui ferme la
// visionneuse ou la feuille, après les boutons
const KEYS = [ARROWS.keep, ARROWS.discard, 'z', 'Enter', ' ', 'Delete', 'Backspace'];
// requêtes qui ne doivent pas partir pendant « Sortir »
const leak = p => p.startsWith('/api/private/') && p !== '/api/private/lock' || /^\/api\/(job|lot)\//.test(p)
  || p === '/api/generate';
// un tour : les boutons visibles et actifs de la vue, pas encore appuyés, appuyés un par un ; rend les clés appuyées.
// Un bouton est reconnu par sa place dans le document, ses attributs data-* et son libellé, pas son texte (le texte
// d'un réglage ou de « Révéler » change à chaque appui) : redessiné à l'identique, c'est le même. Ceux qui ferment ou
// changent la vue (onglets, poignée et voile d'une feuille, « Fermer », « Non ») passent en dernier : appuyés avant,
// les suivants tomberaient sur une vue fermée et s'arrêteraient avant leur garde ; ceux de la feuille ou de la
// visionneuse ouverte passent en premier. Un appui qui ouvre une feuille
// finit le tour : le suivant commence par ses boutons. Un bouton d'une feuille ou d'une visionneuse qui n'est pas
// ouverte (fondu de fermeture) n'est pas appuyé.
const PRESS_ROUND = `(async () => { window.zsPressed ??= new Set();
  const closes = el => el.matches('[data-pane], .grab')
    || /\\b(closeViewer|closeSheet|closeInputs)\\(|answer\\(false\\)/.test(el.getAttribute('onclick') || '');
  const open = el => { const sh = el.closest('.sheet'), v = el.closest('.viewer');
    return (!sh || sh === openedSheet) && (!v || v.classList.contains('on')); };
  const visible = el => !el.hidden && !el.disabled && el.getClientRects().length > 0 && open(el)
    && getComputedStyle(el).visibility !== 'hidden' && !el.closest('[hidden]');
  const key = el => { const path = []; for (let e = el; e && e !== document.body; e = e.parentElement)
    path.unshift(e.id ? '#' + e.id : e.tagName + ':' + [...(e.parentElement?.children || [])].indexOf(e));
    return path.join('>') + '|' + JSON.stringify(el.dataset) + (el.getAttribute('aria-label') || ''); };
  // champ de création replié : déplié d'abord, comme au doigt (« Révéler » et la saisie n'ont pas de boîte replié)
  if ($('composer').classList.contains('folded')) $('composerLine').click();
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const all = [...document.querySelectorAll('button, [role=button], [data-pane]')];
  const done = [];
  // la feuille ouverte d'abord, puis la visionneuse ouverte, puis le reste ; ce qui ferme en dernier
  const rank = e => closes(e) ? 3 : openedSheet?.contains(e) ? 0 : e.closest('.viewer.on') ? 1 : 2;
  for (const el of all.map((e, i) => [rank(e), i, e]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(x => x[2])) {
    const k = key(el);
    if (zsPressed.has(k) || !visible(el) || el.id === 'undoBtn') continue;
    zsPressed.add(k); done.push(k);
    const sheet = openedSheet;
    try { el.click(); } catch {}
    await new Promise(r => setTimeout(r, 30));   // règle levée : laisse partir ce que l'appui lancerait
    if (openedSheet && openedSheet !== sheet) break;
  }
  return done; })()`;
// un Jeter lancé (bandeau) : son envoi n'arriverait qu'à la fin du bandeau, bien après l'attente du test
const DISCARD_STARTED = `!!discarding || !$('undoBar').hidden`;

// pendant « Sortir » : chaque touche (la vue vérifiée d'abord : sinon le gestionnaire s'arrête avant ses gardes),
// puis chaque bouton de tour en tour ; rend les requêtes parties qui ne devaient pas et les clés des boutons
// appuyés, et vérifie qu'aucun Jeter n'a été lancé
async function pressEverything(where, viewOpen) {
  const before = sent.length;
  await page.eval(`document.activeElement?.blur()`);
  assert.equal(await page.eval(viewOpen), true, `vue ouverte avant les touches (${where})`);
  for (const key of KEYS) await page.press(key);
  for (const modifiers of [['ctrl'], ['meta']]) await page.press('z', { modifiers });
  assert.equal(await page.eval(DISCARD_STARTED), false, `Jeter lancé au clavier (${where})`);
  const pressed = [];
  let rounds = 0;
  for (; rounds < 60; rounds++) {
    const done = await page.eval(PRESS_ROUND);
    if (!done.length) break;
    pressed.push(...done);
    assert.equal(await page.eval(DISCARD_STARTED), false, `Jeter lancé par un bouton (${where})`);
  }
  assert.ok(rounds < 60, `des boutons encore nouveaux après 60 tours (${where})`);
  await page.press('Escape');
  await elapse(800);                               // au-delà de l'envol d'une carte (0,22 s)
  assert.equal(await page.eval(DISCARD_STARTED), false, `Jeter lancé (${where})`);
  return { leaked: sent.slice(before).filter(leak), pressed };
}

// vue de départ de chaque passage, la page ramenée à cet état avant « Sortir » ; open : expression vraie tant que
// la vue est ouverte (vérifiée avant les touches) ; must : boutons qui doivent avoir été appuyés vue ouverte (un
// morceau de leur clé)
const VIEWS = {
  labo: { show: async () => { await page.eval(`goTab('labo')`); },
    open: `mode === 'labo' && vIndex < 0 && !openedSheet`,
    // règle levée : les boutons de tri attendus parmi les appuyés, nommés ici, pas un tri
    must: ['#pileYes', '#pileNo', '#go', '#queueChip'] },
  // la feuille de la file ouverte avant « Sortir » (pendant, la file n'est plus redessinée : sans cela, aucune carte)
  file: { show: async () => { await page.openQueue(); },
    open: `openedSheet === $('fileSheet') && !!$('queueList').querySelector('[data-post]')`, must: ['"post":'] },
  visionneuse: { show: async () => { await page.viewPile('zs1 secrete dessous'); },
    open: `vIndex >= 0 && !openedSheet`, must: ['#vSort>BUTTON:0', '#vSort>BUTTON:1'] },
  tirages: { show: async () => {
    await page.eval(`goTab('tirages')`);
    await page.waitFor(`histItems.some(it => it.prompt === 'zs1 secrete gardee')`, { what: 'tirage privé' });
  }, open: `mode === 'tirages' && vIndex < 0 && !openedSheet`, must: [] },
  tirage: { show: async () => {
    await page.eval(`goTab('tirages')`);
    await page.waitFor(`histItems.length > 0`, { what: 'Tirages privés' });
    await page.viewTirage(0);
  }, open: `vIndex >= 0 && !openedSheet`, must: ['#viewer'] },
};

test('pendant « Sortir », aucun bouton ni raccourci n\'envoie de requête privée ni ne lance un tri', async () => {
  await page.enterPrivate(CODE);
  await page.made('zs1 secrete gardee');
  await page.sort('keep');                         // un tirage privé
  await page.made('zs1 secrete dessous');
  await page.launch('HOLD=sortir zs1 secrete en cours', { private: true });
  await page.launch('HOLD=sortir zs1 secrete en file', { private: true });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!$('queueChip').hidden`, { what: 'une génération privée en file' });
  for (const [where, { show, open, must }] of Object.entries(VIEWS)) {
    await page.closeSheet();
    if (await page.eval(`$('viewer').classList.contains('on')`)) await page.closeViewer();
    await show();
    await page.typePrompt('zs1 secrete a ne pas lancer');
    const h = await page.holdRequests(['*/api/private/lock'], () => true);
    try {
      await page.eval(`$('privExit').click()`);    // (une visionneuse couvre l'en-tête : appui par la page)
      await page.waitFor(`exiting()`, { what: '« Sortir » en attente du Mac' });
      await page.eval(`window.zsPressed = new Set()`);
      const { leaked, pressed } = await pressEverything(where, open);
      assert.deepEqual(leaked, [], `requête partie pendant « Sortir » (${where})`);
      for (const part of must) assert.ok(pressed.some(k => k.includes(part)), `${part} appuyé (${where})`);
      await page.refuseExit(h);                      // la page reste dans l'espace pour la vue suivante
    } finally {
      await h.release();
    }
    // seule erreur attendue : le refus (500) de la sortie retenue
    assert.deepEqual(page.errors.filter(e => !/status of 500/.test(e)), [], `erreurs de la page (${where})`);
    page.errors.length = 0;
  }
  bench.release('sortir');
  await bench.idle({ page });
  await page.closeSheet();
  if (await page.eval(`$('viewer').classList.contains('on')`)) await page.closeViewer();
  await page.privateIdle();
  await page.eval(`$('privExit').click()`);
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  page.assertNoErrors();
});
