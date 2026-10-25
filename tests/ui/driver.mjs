// Pilote des tests d'interface : Chrome sans écran piloté par le protocole DevTools (WebSocket natif de Node, sans
// Playwright), branché sur le banc du serveur (tests/ui/serve.py → bench.start()). En local seulement (pas en CI).
//
//   const bench = await startBench();            // serveur du banc sur un port libre, dossier temporaire
//   const chrome = await launchChrome();         // profil temporaire, supprimé par chrome.close()
//   const page = await chrome.phonePage();       // vue du téléphone du porteur : 367×760, densité 2,5, tactile ;
//                                                // connectée au banc direct en cours (cookie du code d'accès)
//   await page.goto(bench.url + '/'); await page.ready();   // ready : interface ouverte, moteur prêt (lampe)
//   …; page.assertNoErrors(); await chrome.close(); await bench.stop();
//                                                // assertNoErrors : erreurs de console du seul test en cours
//                                                // (remises à zéro à chaque test, chacune nommée par son test)
//   await page.click('#go')                      // toucher : échoue si l'élément n'est pas sous le doigt (recouvert,
//                                                // hors de l'écran : l'échec nomme ce qui le recouvre)
//   await elapse(5500)                           // délai voulu (dépasser un minuteur de l'interface) : seule attente
//                                                // fixe permise dans un test, toute autre suit une condition
//   bench.release('nom')                         // libère les générations HOLD=nom du faux moteur
//   bench.dir                                    // dossier temporaire du banc (outputs/, jobs/…) : ce qu'il écrit
//   await bench.idle()                           // rien en cours ni en file (avant un rechargement de la page)
//   const disk = bench.disk(); …; disk.written() // fichiers écrits ou changés par le serveur depuis l'instantané
//   await page.tab('tirages')                    // appui sur l'onglet Labo ou Tirages : la page affichée a changé
//   await page.swipe('#pileEmpty', -150)         // doigt glissé de dx px (dy) depuis le centre d'un élément
//   await page.swipe('#pile .pimg', 200, 0, { mouse: true, hold: true })   // à la souris ; hold : sans relâcher ;
//                                                // pause : ms immobile avant de relâcher (geste lent)
//   await page.release(300)                      // relâche le geste tenu (après 300 ms immobile : geste lent)
//   await page.typePrompt('texte')               // texte tapé dans le champ du Labo (événement input)
//   await page.generate('texte')                 // tapé dans le Labo puis « Révéler » : demande acceptée
//   await page.overflowing()                     // éléments visibles qui dépassent de la largeur de la vue
//   await page.visible('#prompt')                // élément affiché (ni absent, ni masqué, ni sans boîte)
//   await page.pasteImage()                      // une image de 64×64 collée dans le champ du Labo (Cmd+V)
//   await page.made('texte')                     // « Révéler » puis l'image attendue dans la pile affichée
//   await page.holdFetch(`u => u === '/api/status'`); …; await page.releaseFetch()   // réponses retenues
//   const h = await page.holdRequests(['*/api/private/lock'], p => true); …; await h.release()   // requêtes retenues
//                                                // avant le Mac (Fetch.enable) ; h.held, h.free(match), h.take(match)
//   await page.enterPrivate('code')              // dans l'espace privé (créé la première fois), vu par la page,
//                                                // puis au repos ; await page.privateIdle() : espace au repos
//   await page.keepPile()                        // toutes les images de la pile affichée gardées par ✓ (Tirages)
//   await page.viewPile('texte')                 // visionneuse ouverte sur l'image de la pile à ce prompt
//   await page.openQueue()                       // feuille de la file ouverte par la pastille « +N en attente »
//   await page.cancelRun()                       // « Annuler » de la carte en cours, confirmé
//   await page.canvasInk('#revealCanvas')        // { width, height, ink } : pixels non transparents d'un canevas
//   await bench.api('/api/pile')                 // réponse JSON d'une route du banc (le Mac, avec le cookie d'accès)
//   await bench.enter()                          // page d'entrée (jeton à usage unique), comme launch.py --enter
//   await page.launch('texte', { private: true })   // génération demandée hors de l'interface (autre appareil)
//   await page.leaks(['mot', 'id'])              // marqueurs restés dans la page (texte, attributs, champs, mémoire)
//   const bench = await startBench({ relay: true }); await bench.login(page);   // comme le téléphone par Tailscale :
//                                                // bench.url passe par tests/ui/relay.py (adresse HTTPS relayée) ;
//                                                // login : cookie d'accès posé, puis l'interface ouverte (sans
//                                                // relais, chrome.phonePage() pose ce cookie d'office)
//
// Délais : une attente (waitFor, waitUntil) échoue après WAIT ms, une évaluation dans la page (page.eval, goto) après
// EVAL_TIMEOUT ms, le démarrage du banc ou de Chrome après START_TIMEOUT ms : un test bloqué échoue, il n'attend pas
// sans fin (check.py ajoute un délai par test et arrête Chrome et le banc à la fin de chaque fichier).
//
// Variables d'environnement : CHROME (chemin de Chrome), PYTHON (Python du banc ; défaut : venv/ du dépôt, sinon
// celui du dossier principal quand on est dans un worktree, sinon python3), QWEN_UI_WAIT (délai par défaut des
// attentes, en ms : check.py le double quand le banc ou plusieurs Chrome tournent en même temps).
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.resolve(HERE, '..', '..');
const VENV_PY = process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python');
const CHROMES = { darwin: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  win32: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', linux: 'google-chrome' };
export const PHONE = { width: 367, height: 760, deviceScaleFactor: 2.5, mobile: true };
export const WAIT = Number(process.env.QWEN_UI_WAIT) || 15000;
export const EVAL_TIMEOUT = 30000;
export const START_TIMEOUT = 60000;
// dossiers que le serveur du banc écrit (tools/ui y est un lien vers le dépôt : les liens ne sont pas parcourus)
const WRITTEN = ['outputs', 'jobs', 'logs', 'private', 'tools'];

const pause = ms => new Promise(r => setTimeout(r, ms));
// délai voulu d'un test (un minuteur de l'interface à dépasser : « rien n'est parti au bout de 5 s ») : la seule
// attente fixe permise dans un test (tests/rules.py refuse un setTimeout nu) ; toute autre attente suit une condition
export const elapse = ms => pause(ms);

// erreurs de console attribuées au test en cours (node --test : le processus d'un fichier porte NODE_TEST_CONTEXT ;
// pas la sonde) : au début de chaque test, celles des tests d'avant sont oubliées (une erreur ne fait pas échouer le
// test suivant) ; celles d'avant le premier test (before) passent au premier ; chacune est précédée du test où elle
// est apparue
const BEFORE_TESTS = 'avant les tests';
const livePages = new Set();
let testLabel = BEFORE_TESTS;
if (process.env.NODE_TEST_CONTEXT) {
  const { beforeEach, afterEach } = await import('node:test');
  beforeEach(t => {
    for (const p of livePages) {
      if (testLabel === BEFORE_TESTS) continue;
      // arrivées après la fin du test d'avant (une réponse en retard) : écrites dans la sortie, pas perdues en silence
      const late = p.errors.filter(e => e.startsWith('après '));
      if (late.length) console.error(`erreurs de console après la fin d'un test :\n  ${late.join('\n  ')}`);
      p.errors.length = 0;
    }
    testLabel = `« ${t.name} »`;
  });
  afterEach(t => { testLabel = `après « ${t.name} »`; });
}

// banc direct en cours (startBench sans relais) : { url, cookie } ; chaque page de chrome.phonePage() y est connectée
// (cookie du code d'accès, que le serveur demande aussi au Mac). Un banc relayé n'y est pas : bench.login(page)
let directBench = null;

// promesse qui échoue si elle n'est pas tenue dans les ms millisecondes
function within(promise, ms, what) {
  let timer;
  const late = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${what} : pas de réponse après ${ms / 1000} s`)), ms);
  });
  return Promise.race([promise, late]).finally(() => clearTimeout(timer));
}

// attend que cond() (synchrone ou promesse) soit vraie, interrogée toutes les 50 ms ; échoue après timeout ms
export async function waitUntil(cond, { timeout = WAIT, what = 'la condition' } = {}) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await cond()) return;
    if (Date.now() > end) throw new Error(`${what} : toujours fausse après ${timeout / 1000} s`);
    await pause(50);
  }
}

// fichiers sous dir (liens non suivis) : { chemin : taille et date de modification }
function files(dir, out = {}) {
  for (const e of fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : []) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) files(p, out);
    else if (e.isFile()) { const s = fs.statSync(p); out[p] = `${s.size} ${s.mtimeMs}`; }
  }
  return out;
}

function python() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const bases = [ROOT];
  try {                                                     // worktree : le venv du dossier principal
    const common = execFileSync('git', ['rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd: ROOT }).toString().trim();
    bases.push(path.dirname(common));
  } catch { /* hors git */ }
  const found = bases.map(b => path.join(b, 'venv', VENV_PY)).find(p => fs.existsSync(p));
  return found || 'python3';
}

// processus Python à part, qui écrit une ligne au démarrage et s'arrête à la fermeture de son entrée standard ;
// ask(texte) lui envoie une ligne et rend la ligne qu'il répond (réponses dans l'ordre des demandes : deux demandes
// simultanées reçoivent chacune la leur ; un processus arrêté fait échouer les demandes en attente)
async function startPython(script, args, what) {
  const proc = spawn(python(), [path.join(HERE, script), ...args], { cwd: ROOT, stdio: ['pipe', 'pipe', 'inherit'] });
  const killer = () => proc.kill();
  process.on('exit', killer);
  const rl = readline.createInterface({ input: proc.stdout });
  const waiting = [];                                // { resolve, reject } par ligne attendue, la première d'abord
  rl.on('line', line => waiting.shift()?.resolve(line));
  const fail = e => { while (waiting.length) waiting.shift().reject(e); };
  proc.stdin.on('error', e => fail(new Error(`${what} : écriture impossible (${e.message})`)));
  proc.once('exit', code => fail(new Error(`${what} arrêté (code ${code})`)));
  const nextLine = () => new Promise((resolve, reject) => waiting.push({ resolve, reject }));
  const first = await within(nextLine(), START_TIMEOUT, `${what} : démarrage`)
    .catch(e => { killer(); process.off('exit', killer); throw e; });
  async function stop() {
    process.off('exit', killer);
    if (proc.exitCode !== null) return;
    const gone = new Promise(r => proc.once('exit', r));
    proc.stdin.end();
    await Promise.race([gone, pause(10000).then(() => proc.kill())]);
  }
  function ask(text) {
    if (proc.exitCode !== null || proc.stdin.destroyed) return Promise.reject(new Error(`${what} arrêté`));
    const reply = nextLine();
    proc.stdin.write(text + '\n');
    return within(reply, EVAL_TIMEOUT, `${what} : réponse à « ${text} »`);
  }
  return { first, stop, ask, pid: proc.pid };
}

// serveur du banc ; sans relais, les pages de chrome.phonePage() y sont connectées (cookie du code d'accès) ; relay :
// l'interface passe par tests/ui/relay.py, comme le téléphone par « tailscale serve » (nom HTTPS, en-têtes de relais),
// et la page se connecte par bench.login(page) (les cookies ne distinguent pas les ports : un banc relayé ne connecte
// pas les pages d'office, pour que la page du code reste visible). stop() arrête tout.
export async function startBench({ relay = false } = {}) {
  const server = await startPython('serve.py', [], 'serveur du banc');
  const { url: direct, hold, https, cookie } = JSON.parse(server.first);
  const relayed = relay ? await startPython('relay.py', [direct, https], 'relais du banc')
    .catch(async e => { await server.stop(); throw e; }) : null;
  const url = relayed ? `http://127.0.0.1:${relayed.first.trim()}` : direct;
  const dir = path.dirname(hold);                   // dossier temporaire du banc (hold/ en est un sous-dossier)
  const written = () => Object.assign({}, ...WRITTEN.map(d => files(path.join(dir, d))));
  // requête du test au Mac lui-même (hors de la page), avec le cookie du code d'accès
  const macFetch = route => fetch(direct + route, { headers: { Cookie: `${cookie.name}=${cookie.value}` } });
  const entry = relayed ? null : { url, cookie };
  if (entry) directBench = entry;
  return {
    url, direct, dir, pids: [server.pid, ...relayed ? [relayed.pid] : []],   // processus du banc (et du relais)
    // attend que le Mac soit au repos : rien en cours ni en file, toutes origines et tous espaces confondus (à faire
    // avant de recharger la page : une génération encore en file serait reprise par la page rechargée) ; page : puis
    // plus aucune génération active suivie par cette page (son dernier suivi rendu)
    async idle({ timeout = 2 * WAIT, page = null } = {}) {
      await waitUntil(async () => { const s = await (await macFetch('/api/status')).json();
        return !s.busy && !s.queue.length; }, { timeout, what: 'Mac au repos (rien en cours ni en file)' });
      if (page) await page.waitFor(`!pageJobs.some(isActive)`, { timeout, what: 'page au repos' });
    },
    // instantané des fichiers des dossiers que le serveur écrit ; written() : ceux créés ou changés depuis
    disk() {
      // sans ces dossiers, written() rendrait toujours [] et un test « rien d'écrit » passerait sans rien vérifier
      const missing = ['outputs', 'jobs'].filter(d => !fs.existsSync(path.join(dir, d)));
      if (missing.length) throw new Error(`bench.disk : dossier du banc absent (${missing.join(', ')})`);
      const before = written();
      return { written: () => Object.entries(written()).filter(([p, v]) => before[p] !== v)
        .map(([p]) => path.relative(dir, p)).sort() };
    },
    // par le relais : le cookie du code d'accès (celui que pose la saisie du code), puis l'interface ouverte
    async login(page) {
      await setAccessCookie(page, { url, cookie });
      await page.goto(url + '/');
    },
    // libère les générations dont le prompt porte HOLD=<name> (HOLD seul : 'hold') ; voir tests/fake_sdcli.py
    release(name = 'hold') { fs.writeFileSync(path.join(hold, name), ''); },
    async api(route) { return (await macFetch(route)).json(); },
    // jeton et page d'entrée du banc, comme launch.py --enter : chemin de la page de redirection vers /entrer
    async enter() { return JSON.parse(await server.ask('entrer')).entry; },
    async stop() { if (directBench === entry) directBench = null; await relayed?.stop(); await server.stop(); },
  };
}

// Chrome sans écran avec un profil temporaire ; close() l'arrête et supprime le profil (aussi si le test plante)
export async function launchChrome() {
  const exe = process.env.CHROME || CHROMES[process.platform];
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-chrome-'));
  const proc = spawn(exe, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--disable-gpu', '--disable-extensions', '--mute-audio', 'about:blank'], { stdio: 'ignore' });
  const cleanup = () => { try { proc.kill(); } catch { /* déjà arrêté */ }
    fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }); };
  process.on('exit', cleanup);
  const portFile = path.join(profile, 'DevToolsActivePort');
  await waitUntil(() => fs.existsSync(portFile) && fs.readFileSync(portFile, 'utf8').includes('\n'),
    { timeout: START_TIMEOUT, what: `Chrome démarré (${exe})` })
    .catch(e => { process.off('exit', cleanup); cleanup(); throw e; });
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const pages = [];
  return {
    pid: proc.pid,
    async phonePage() {
      const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
      const page = await connect(target.webSocketDebuggerUrl);
      pages.push(page);
      await page.send('Emulation.setDeviceMetricsOverride', PHONE);
      await page.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
      if (directBench) await setAccessCookie(page, directBench);
      return page;
    },
    async close() {
      pages.forEach(p => p.close());
      const gone = new Promise(r => proc.once('exit', r));
      proc.kill();
      await Promise.race([gone, pause(5000)]);
      process.off('exit', cleanup);
      cleanup();
    },
  };
}

// cookie du code d'accès d'un banc posé dans le navigateur de la page (même cookie que la saisie du code)
function setAccessCookie(page, { url, cookie }) {
  return page.send('Network.setCookie', { ...cookie, url, httpOnly: true, sameSite: 'Lax' });
}

// une page : commandes du protocole, évaluation de JavaScript, attente d'une condition, erreurs de la console
async function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }); });
  let id = 0;
  const pending = new Map(), handlers = new Map(), errors = [];
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject, method } = pending.get(m.id); pending.delete(m.id);
      if (m.error) reject(new Error(`${method} : ${m.error.message}`)); else resolve(m.result);
    } else if (m.method) (handlers.get(m.method) || []).forEach(f => f(m.params));
  });
  const on = (method, f) => handlers.set(method, [...(handlers.get(method) || []), f]);
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const i = ++id; pending.set(i, { resolve, reject, method }); ws.send(JSON.stringify({ id: i, method, params }));
  });
  const text = args => args.map(a => a.value ?? a.description ?? a.type).join(' ');
  const record = what => errors.push(`${testLabel} : ${what}`);       // le test où l'erreur apparaît, devant
  on('Runtime.consoleAPICalled', p => {
    if (p.type === 'error' || p.type === 'assert') record(`console.${p.type} : ${text(p.args)}`); });
  on('Runtime.exceptionThrown', p =>
    record(`exception : ${p.exceptionDetails.exception?.description || p.exceptionDetails.text}`));
  on('Log.entryAdded', p => {
    if (p.entry.level === 'error')
      record(`${p.entry.source} : ${p.entry.text}${p.entry.url ? ` (${p.entry.url})` : ''}`); });
  await Promise.all([send('Runtime.enable'), send('Log.enable'), send('Page.enable')]);

  let held = null;                                   // fin du balayage tenu (page.release)
  let holding = null, holdHook = false;              // requêtes retenues en cours (page.holdRequests), écouteur posé
  const page = {
    send, on, errors,
    // évalue une expression dans la page (promesse attendue) et renvoie sa valeur (JSON) ; échoue après timeout ms
    // (une promesse jamais tenue, comme une confirmation qui attend sa réponse, ne bloque pas le test)
    async eval(expression, { timeout = EVAL_TIMEOUT } = {}) {
      const r = await within(send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true,
        userGesture: true }), timeout, `dans la page : ${expression}`);
      if (r.exceptionDetails) throw new Error(`dans la page : ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}\n  ${expression}`);
      return r.result.value;
    },
    // requêtes retenues avant d'atteindre le Mac (Fetch.enable sur les adresses patterns, motifs de Fetch) : keep(p)
    // dit pour chacune (p.request.url) si elle est retenue (vrai : dans held, { requestId, url }) ou part tout de
    // suite. free(match) laisse partir les retenues dont l'adresse vérifie match, take(match) les retire de held
    // (le test y répond lui-même : Fetch.fulfillRequest, failRequest) ; release() laisse partir les autres et coupe
    // l'interception. Une seule retenue à la fois ; sans retenue en cours, l'écouteur ne fait rien (un test peut
    // poser le sien)
    async holdRequests(patterns, keep) {
      if (!holdHook) {
        holdHook = true;
        on('Fetch.requestPaused', p => { if (!holding) return;
          if (!holding.closing && holding.keep(p)) holding.held.push({ requestId: p.requestId, url: p.request.url });
          else send('Fetch.continueRequest', { requestId: p.requestId }).catch(() => {}); });
      }
      const h = holding = { held: [], keep,
        take(match = () => true) { const out = h.held.filter(r => match(r.url));
          h.held = h.held.filter(r => !out.includes(r)); return out; },
        async free(match) { for (const r of h.take(match))
          await send('Fetch.continueRequest', { requestId: r.requestId }).catch(() => {}); },
        // (pendant la libération, une requête interceptée part aussitôt ; l'écouteur reste branché jusqu'à la fin)
        async release() { h.closing = true; await h.free(); await send('Fetch.disable');
          if (holding === h) holding = null; } };
      await send('Fetch.enable', { patterns: patterns.map(urlPattern => ({ urlPattern })) });
      return h;
    },
    // entrée dans l'espace privé avec ce code (l'espace est créé s'il n'existe pas) ; la page la voit à son
    // interrogation suivante de /api/status, demandée tout de suite. settle : attendre ensuite l'espace au repos
    // (privateIdle) ; false pour un test qui retient lui-même les lectures de l'entrée
    async enterPrivate(code, { settle = true } = {}) {
      await page.countPrivate();
      const exists = await page.eval(`fetch('/api/status').then(r => r.json()).then(s => s.private.exists)`);
      const route = exists ? '/api/private/unlock' : '/api/private/create';
      const status = await page.eval(`postJson('${route}', { code: ${JSON.stringify(code)} }).then(r => r.status)`);
      if (status !== 200) throw new Error(`entrée dans l'espace privé refusée : ${status}`);
      await page.eval(`refreshStatus()`);
      await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
      if (settle) await page.privateIdle();
    },
    // requêtes privées de la page en route (fetch vers /api/private/), comptées dans __privInflight à partir de
    // l'appel (une fois par page)
    countPrivate() {
      return page.eval(`(() => { if (window.__privFetch) return; const f = window.__privFetch = window.fetch;
        window.__privInflight = 0;
        window.fetch = (u, ...a) => { if (!String(u).startsWith('/api/private/')) return f(u, ...a);
          __privInflight++; return f(u, ...a).finally(() => { __privInflight--; }); }; })()`);
    },
    // espace privé au repos : pile privée lue, aucune requête privée en route (comptées depuis countPrivate, que
    // enterPrivate pose), aucune image privée en chargement. À attendre avant de fermer l'espace sans « Sortir »
    // (le Mac, une fermeture de la page) : une requête servie après la fermeture répondrait 403, ce que la page ne peut
    // pas savoir
    async privateIdle() {
      await page.countPrivate();
      await page.waitFor(`!__privInflight && pileRead && !secretLoads.size && ![...document.querySelectorAll('img')]
        .some(i => secretUrl(i.getAttribute('src')) && !i.complete)`, { what: 'espace privé au repos' });
    },
    async goto(url) {
      const loaded = new Promise(r => on('Page.loadEventFired', r));
      await send('Page.navigate', { url });
      await within(loaded, EVAL_TIMEOUT, `chargement de ${url}`);
    },
    // attend qu'une expression de la page soit vraie
    waitFor(expression, opts = {}) { return waitUntil(() => page.eval(expression), { what: expression, ...opts }); },
    // interface ouverte et moteur prêt (lampe d'état allumée) : l'attente qui suit chaque ouverture de la page
    ready(what = 'moteur prêt affiché') { return page.waitFor(`$('lamp').classList.contains('ok')`, { what }); },
    // appui sur l'onglet de la page name (labo, tirages), comme au doigt ; attend la page affichée
    async tab(name, { force = false } = {}) {          // force : comme page.click
      await page.click(`#tabbar [data-pane="${name}"]`, { force });
      await page.waitFor(`mode === ${JSON.stringify(name)} && $('pane-' + mode).classList.contains('active')`,
        { what: `onglet ${name} affiché` });
    },
    // doigt posé au centre de l'élément selector (amené à l'écran), glissé de dx, dy px en quelques pas, puis relevé
    // (événements tactiles de Chrome : touch et pointer) ; mouse : la souris, bouton gauche enfoncé ; pause : le doigt
    // reste immobile pause ms avant d'être relevé (un geste lent) ; hold : il reste posé à la fin (page.release() le
    // relève). Un geste tenu d'avant est d'abord relevé
    async swipe(selector, dx, dy = 0, { mouse = false, hold = false, pause = 0 } = {}) {
      await page.release();
      const c = await page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return null; el.scrollIntoView({ block: 'center' }); const r = el.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
      if (!c) throw new Error(`élément absent : ${selector}`);
      const x = k => c.x + dx * k, y = k => c.y + dy * k;
      const input = mouse
        ? { down: 'mousePressed', move: 'mouseMoved', up: 'mouseReleased',
          send: (type, k) => page.send('Input.dispatchMouseEvent', { type, x: x(k), y: y(k), button: 'left',
            buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1 }) }
        : { down: 'touchStart', move: 'touchMove', up: 'touchEnd',
          send: (type, k) => page.send('Input.dispatchTouchEvent', { type,
            touchPoints: type === 'touchEnd' ? [] : [{ x: x(k), y: y(k), id: 1 }] }) };
      await input.send(input.down, 0);
      for (const k of [0.25, 0.5, 0.75, 1]) await input.send(input.move, k);
      held = () => input.send(input.up, 1);
      if (!hold) await page.release(pause);
    },
    // relève le doigt ou la souris d'un balayage tenu (swipe … { hold: true }), après pause ms immobile (geste lent)
    async release(pause = 0) { const up = held; held = null; if (!up) return;
      if (pause) await new Promise(r => setTimeout(r, pause));
      await up(); },
    // garde par ✓ toutes les images de la pile affichée (celle de l'espace où est la page) : elles passent dans ses
    // Tirages ; chacune attendue hors de la pile du Mac avant la suivante. Une carte d'échec en tête l'empêche
    // (erreur). Renvoie le nombre d'images gardées
    keepPile() {
      return page.eval(`(async () => {
        const onMac = async k => (await (await fetch(pileApi('pile', inPrivate()))).json()).some(x => pileKey(x) === k);
        await loadPile(); let n = 0;
        for (let it; (it = pileView()[0]); n++) {
          if (pileFails().length) throw new Error('carte d\\'échec en tête de la pile');
          while (sortBusy()) await new Promise(r => setTimeout(r, 25));   // ✓ ignoré pendant un tri et SORT_GAP
          if (!(it = pileView()[0])) break;               // la pile a pu changer pendant l'attente
          const k = pileKey(it); $('pileYes').click();
          for (let t = 0; await onMac(k); t++) {
            if (t > 400) throw new Error('image non gardée : ' + k);
            await new Promise(r => setTimeout(r, 25)); }
          await loadPile(); }
        return n; })()`);
    },
    // visionneuse ouverte sur l'image de la pile affichée dont le prompt est prompt (attendue dans la pile)
    async viewPile(prompt) {
      const at = `pileView().findIndex(it => it.prompt === ${JSON.stringify(prompt)})`;
      await page.waitFor(`${at} >= 0`, { what: `« ${prompt} » dans la pile`, timeout: 30000 });
      await page.eval(`openViewer(${at}, pileView())`);
      await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'visionneuse ouverte' });
    },
    // feuille ouverte refermée, comme d'un toucher sur le voile hors d'elle (closeSheet de la page) : avant de toucher
    // ce que le voile recouvre (en-tête, Labo)
    async closeSheet() {
      await page.eval(`openedSheet && closeSheet()`);
      await page.waitFor(`!openedSheet && !$('scrim').classList.contains('on')`, { what: 'feuille refermée' });
    },
    // feuille de la file de l'espace, ouverte par la pastille « +N en attente » du Labo (attendue) ; une autre feuille
    // ouverte est d'abord refermée
    async openQueue() {
      await page.closeSheet();
      if (await page.eval(`mode`) !== 'labo') await page.tab('labo');
      await page.eval(`refreshStatus()`);
      await page.waitFor(`!$('queueChip').hidden`, { what: 'pastille « +N en attente »' });
      await page.click('#queueChip');
      await page.waitFor(`openedSheet === $('fileSheet')`, { what: 'feuille de la file' });
    },
    // « Annuler » de la carte en cours, puis la confirmation acceptée (yes = false : refusée)
    async cancelRun(yes = true) {
      await page.click('#runCancel');
      await page.waitFor(`openedSheet === $('askSheet')`, { what: 'confirmation de l\'annulation' });
      await page.eval(`answer(${yes})`);
    },
    // élément affiché : présent, ni masqué (hidden, display:none) ni sans boîte
    visible(selector) {
      return page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
        return !!el && !el.hidden && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0; })()`);
    },
    // une image de 64×64 pixels collée dans le champ du Labo (Cmd+V : événement paste avec un fichier image)
    pasteImage() {
      return page.eval(`(async () => { const dt = new DataTransfer(), c = document.createElement('canvas');
        c.width = c.height = 64; const b = await new Promise(r => c.toBlob(r, 'image/png'));
        dt.items.add(new File([b], 'image.png', { type: 'image/png' }));
        const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
        $('prompt').dispatchEvent(ev); })()`);
    },
    // génération demandée par la page (page.generate), finie : son image est dans la pile affichée
    async made(prompt) {
      await page.generate(prompt);
      await page.waitFor(`pileItems.some(it => it.prompt === ${JSON.stringify(prompt)})`,
        { what: `« ${prompt} » dans la pile`, timeout: 30000 });
    },
    // réponses de fetch retenues dans la page : celles dont l'adresse vérifie match (source d'une fonction
    // (adresse) => booléen, évaluée dans la page) n'arrivent qu'à page.releaseFetch() ; la requête, elle, part tout de
    // suite (le Mac la traite). Une seule enveloppe de fetch, posée au premier appel
    holdFetch(match) {
      return page.eval(`(() => { if (!window.fetchHold) { const f = window.fetch; window.fetchHold = { match: null };
        window.fetch = (u, ...a) => { const m = fetchHold.match; if (!m || !m(String(u))) return f(u, ...a);
          const sent = f(u, ...a);
          return new Promise(r => { const t = setInterval(() => { if (fetchHold.match !== m) { clearInterval(t);
            r(sent); } }, 30); }); }; }
        fetchHold.match = ${match}; })()`);
    },
    releaseFetch() { return page.eval(`window.fetchHold && (fetchHold.match = null)`); },
    // éléments visibles qui dépassent de la largeur de la vue (boîtes mesurées), hors feuilles, visionneuses et
    // messages ; un élément rogné par un parent qui tient dans la vue (overflow hidden ou défilant : reflets animés,
    // rangées qui défilent) ne dépasse pas. Renvoie l'identifiant (ou la classe) de chacun
    overflowing() {
      return page.eval(`(() => {
        const out = r => r.left < -.5 || r.right > innerWidth + .5;
        const clipped = el => { for (let a = el.parentElement; a; a = a.parentElement)
          if (getComputedStyle(a).overflowX !== 'visible') return !out(a.getBoundingClientRect());
          return false; };
        return [...document.querySelectorAll('body *')]
          .filter(el => el.getClientRects().length && !el.closest('.sheet, .viewer, .toast, .ambient'))
          .filter(el => { const r = el.getBoundingClientRect(); return r.width && out(r) && !clipped(el); })
          .map(el => el.id || el.className || el.tagName); })()`);
    },
    // taille d'un canevas et nombre de ses pixels non transparents (ce qui y est dessiné)
    canvasInk(selector) {
      return page.eval(`(c => { const out = { width: c.width, height: c.height, ink: 0 }; if (!c.width) return out;
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        for (let i = 3; i < d.length; i += 4) if (d[i]) out.ink++;
        return out; })(document.querySelector(${JSON.stringify(selector)}))`);
    },
    // texte tapé dans le champ du Labo, comme au clavier (événement input : le brouillon est écrit)
    typePrompt(text) {
      return page.eval(`(() => { const t = $('prompt'); t.value = ${JSON.stringify(text)};
        t.dispatchEvent(new Event('input')); })()`);
    },
    // texte tapé dans le Labo puis « Révéler » : attend la demande acceptée (une génération de plus suivie par la
    // page), le Labo affiché ; une feuille ouverte est d'abord refermée
    async generate(text) {
      await page.closeSheet();
      if (await page.eval(`mode`) !== 'labo') await page.tab('labo');
      await page.typePrompt(text);
      const before = await page.eval(`pageJobs.length`);
      await page.click('#go');
      await page.waitFor(`mode === 'labo' && pageJobs.length > ${before}`,
        { what: `« ${text} » acceptée, Labo affiché` });
    },
    // génération demandée hors de l'interface, comme depuis un autre appareil (texte → image 512×512, 20 étapes ;
    // extra : champs changés ou ajoutés, private: true pour une génération privée) ; échoue si le Mac la refuse,
    // renvoie sa réponse ({ id, … })
    async launch(prompt, extra = {}) {
      const r = await page.eval(`postJson('/api/generate', { mode: 't2i', prompt: ${JSON.stringify(prompt)},
        width: 512, height: 512, steps: 20, cfg: 1, seed: -1, preview: false, ref_images: [],
        ...${JSON.stringify(extra)} }).then(async r => ({ status: r.status, body: await r.json() }))`);
      if (r.status !== 202) throw new Error(`génération « ${prompt} » refusée : ${r.status} ${JSON.stringify(r.body)}`);
      return r.body;
    },
    // marqueurs (mots de prompts, identifiants, réglages) restés dans la page : texte et attributs du document (caché
    // compris, scripts exceptés), valeurs des champs, localStorage et sessionStorage, et tout l'état global de la page
    // (variables let, const, var et fonctions de premier niveau, avec le contenu de leurs objets, tableaux, Map et Set,
    // éléments détachés compris) ; skip : variables à ne pas fouiller. Renvoie « endroit : marqueur » par trouvaille.
    async leaks(markers, { skip = [] } = {}) {
      const { names } = await send('Runtime.globalLexicalScopeNames');
      return page.eval(`(${scanPage})(${JSON.stringify(markers)}, ${JSON.stringify(names)}, ${JSON.stringify(skip)})`);
    },
    // appui sur un élément (événement click du DOM, comme un toucher) ; échoue tout de suite s'il est absent, masqué
    // ou désactivé, et après timeout ms s'il n'est toujours pas sous le doigt : amené au centre de l'écran, le point au
    // centre de sa boîte doit être lui ou un de ses descendants (une feuille qui s'ouvre ou se ferme, un message qui
    // passe : on attend ; sinon l'échec nomme l'élément qui le recouvre, ou dit qu'il est hors de l'écran). Dans le
    // champ de création replié, un toucher sur sa ligne le déplie d'abord, comme au doigt. Une case dessinée par son
    // étiquette (interrupteur) est sous le doigt quand l'étiquette l'est. force : appui sans ce contrôle, pour un état
    // que le test monte exprès et que le doigt n'atteindrait pas (le dire en commentaire)
    async click(selector, { timeout = WAIT, force = false } = {}) {
      const end = Date.now() + timeout;
      for (;;) {
        const why = await page.tryClick(selector, force);
        if (!why) return;
        if (why.startsWith('absent') || Date.now() > end) throw new Error(`élément ${why} : ${selector}`);
        await pause(50);
      }
    },
    // un essai d'appui de page.click : '' s'il a eu lieu, sinon pourquoi
    tryClick(selector, force = false) {
      return page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
        if (el && el.closest('#composer.folded') && el.id !== 'composerLine') $('composerLine').click();
        if (!el || el.hidden || el.disabled || !el.getClientRects().length) return 'absent, masqué ou désactivé';
        if (${force}) { el.click(); return ''; }
        el.scrollIntoView({ block: 'center', inline: 'center' });
        const r = el.getBoundingClientRect();
        const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        if (!top) return 'hors de l\\'écran';
        const under = top === el || el.contains(top) || top.closest('label')?.control === el;
        const name = e => e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string'
          && e.className.trim() ? '.' + e.className.trim().split(/\\s+/).join('.') : '');
        const holder = top.id ? null : top.parentElement?.closest('[id]');   // l'élément nommé qui le contient
        if (!under) return 'recouvert par ' + name(top) + (holder ? ' (dans #' + holder.id + ')' : '');
        el.click(); return ''; })()`);
    },
    // fichiers choisis d'un coup dans un champ <input type=file> (comme le sélecteur du téléphone) : événements input et
    // change envoyés par Chrome
    async setFiles(selector, files) {
      const r = await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(selector)})` });
      if (!r.result.objectId) throw new Error(`champ de fichiers absent : ${selector}`);
      await send('DOM.enable');
      await send('DOM.setFileInputFiles', { objectId: r.result.objectId, files });
    },
    async screenshot(file) {
      const r = await send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
    },
    // échoue sur les erreurs de console du test en cours (chacune précédée du test où elle est apparue)
    assertNoErrors() {
      if (errors.length) throw new Error(`erreurs dans la console :\n  ${errors.join('\n  ')}`);
    },
    close() { livePages.delete(page); try { ws.close(); } catch { /* déjà fermée */ } },
  };
  livePages.add(page);
  return page;
}

// fouille de page.leaks, exécutée dans la page (sa source y est envoyée : rien d'extérieur) ; lexical : noms des
// variables let et const de premier niveau (Runtime.globalLexicalScopeNames)
function scanPage(markers, lexical, skip) {
  const found = new Set();
  const look = (where, text) => markers.forEach(m => { if (text.includes(m)) found.add(`${where} : ${m}`); });
  const doc = document.documentElement.cloneNode(true);   // le code de la page nomme des routes : écarté
  doc.querySelectorAll('script').forEach(s => s.remove());
  look('page', doc.outerHTML);
  look('champs', [...document.querySelectorAll('input, textarea, select')].map(e => e.value).join('\n'));
  for (const name of ['localStorage', 'sessionStorage']) {
    try { look(name, JSON.stringify({ ...window[name] })); } catch { /* stockage refusé */ }
  }
  // variables globales de la page : celles que n'a pas une fenêtre vide, et les let/const de premier niveau
  const frame = document.createElement('iframe');
  frame.hidden = true;
  document.documentElement.append(frame);
  const native = new Set(Object.getOwnPropertyNames(frame.contentWindow));
  frame.remove();
  const names = [...Object.keys(window).filter(n => !native.has(n)), ...lexical].filter(n => !skip.includes(n));
  const seen = new Set();
  let budget = 500000;                                       // valeurs visitées au plus
  const walk = (v, where, depth) => {
    if (v === null || v === undefined || --budget < 0) return;
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'bigint') return look(where, String(v));
    if (typeof v !== 'object' || seen.has(v) || depth > 12) return;   // fonctions : pas de données lisibles
    seen.add(v);
    if (v === window || v === document || ArrayBuffer.isView(v) || v instanceof ArrayBuffer
      || v instanceof Blob) return;
    if (v instanceof Node) {                                 // un élément de la page est déjà fouillé par son texte
      if (!document.contains(v)) look(where, v.outerHTML ?? v.textContent ?? '');
      return;
    }
    if (v instanceof Map) {
      for (const [k, x] of v) {
        walk(k, `${where}.clé`, depth + 1);
        walk(x, `${where}.get(${String(k).slice(0, 40)})`, depth + 1);
      }
    } else if (v instanceof Set || Array.isArray(v)) {
      let i = 0;
      for (const x of v) walk(x, `${where}[${i++}]`, depth + 1);
    } else {
      for (const k of Object.keys(v)) {
        look(where, k);
        let x;
        try { x = v[k]; } catch { continue; }
        walk(x, `${where}.${k}`, depth + 1);
      }
    }
  };
  for (const name of names) {
    let v;
    try { v = (0, eval)(name); } catch (e) {                // eval indirect : portée globale, let/const compris
      if (!(e instanceof ReferenceError)) found.add(`mémoire ${name} : illisible (${e})`);   // pas de fouille muette
      continue;
    }
    walk(v, `mémoire ${name}`, 0);
  }
  return [...found];
}
