// Pilote des tests d'interface : Chrome sans écran piloté par le protocole DevTools (WebSocket natif de Node, sans
// Playwright), branché sur le banc du serveur (tests/ui/serve.py → bench.start()). En local seulement (pas en CI).
//
//   const bench = await startBench();            // serveur du banc sur un port libre, dossier temporaire
//   const chrome = await launchChrome();         // profil temporaire, supprimé par chrome.close()
//   const page = await chrome.phonePage();       // vue du téléphone du porteur : 367×760, densité 2,5, tactile
//   await page.goto(bench.url + '/'); await page.waitFor(`$('status').className==='ok'`);
//   …; page.assertNoErrors(); await chrome.close(); await bench.stop();
//   bench.release('nom')                         // libère les générations HOLD=nom du faux moteur
//   const bench = await startBench({ relay: true }); await bench.login(page);   // comme le téléphone par Tailscale :
//                                                // bench.url passe par tests/ui/relay.py (adresse HTTPS relayée)
//
// Variables d'environnement : CHROME (chemin de Chrome), PYTHON (Python du banc ; défaut : venv/ du dépôt, sinon
// celui du dossier principal quand on est dans un worktree, sinon python3).
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

const pause = ms => new Promise(r => setTimeout(r, ms));

// attend que cond() (synchrone ou promesse) soit vraie, interrogée toutes les 50 ms ; échoue après timeout ms
export async function waitUntil(cond, { timeout = 15000, what = 'la condition' } = {}) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await cond()) return;
    if (Date.now() > end) throw new Error(`${what} : toujours fausse après ${timeout / 1000} s`);
    await pause(50);
  }
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

// processus Python à part, qui écrit une ligne au démarrage et s'arrête à la fermeture de son entrée standard
async function startPython(script, args, what) {
  const proc = spawn(python(), [path.join(HERE, script), ...args], { cwd: ROOT, stdio: ['pipe', 'pipe', 'inherit'] });
  const killer = () => proc.kill();
  process.on('exit', killer);
  const first = await new Promise((resolve, reject) => {
    const rl = readline.createInterface({ input: proc.stdout });
    rl.once('line', line => resolve(line));
    proc.once('exit', code => reject(new Error(`${what} arrêté au démarrage (code ${code})`)));
  });
  async function stop() {
    process.off('exit', killer);
    if (proc.exitCode !== null) return;
    const gone = new Promise(r => proc.once('exit', r));
    proc.stdin.end();
    await Promise.race([gone, pause(10000).then(() => proc.kill())]);
  }
  return { first, stop };
}

// serveur du banc ; relay : l'interface passe par tests/ui/relay.py, comme le téléphone par « tailscale serve »
// (nom HTTPS, en-têtes de relais : le serveur demande le code d'accès, bench.login(page)). stop() arrête tout.
export async function startBench({ relay = false } = {}) {
  const server = await startPython('serve.py', [], 'serveur du banc');
  const { url: direct, hold, https, cookie } = JSON.parse(server.first);
  const relayed = relay ? await startPython('relay.py', [direct, https], 'relais du banc') : null;
  const url = relayed ? `http://127.0.0.1:${relayed.first.trim()}` : direct;
  return {
    url, direct,
    // par le relais : le cookie du code d'accès (celui que pose la saisie du code), puis l'interface ouverte
    async login(page) {
      await page.send('Network.setCookie', { ...cookie, url, httpOnly: true, sameSite: 'Lax' });
      await page.goto(url + '/');
    },
    // libère les générations dont le prompt porte HOLD=<name> (HOLD seul : 'hold') ; voir tests/fake_sdcli.py
    release(name = 'hold') { fs.writeFileSync(path.join(hold, name), ''); },
    async stop() { await relayed?.stop(); await server.stop(); },
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
    { timeout: 20000, what: `Chrome démarré (${exe})` });
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const pages = [];
  return {
    async phonePage() {
      const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
      const page = await connect(target.webSocketDebuggerUrl);
      pages.push(page);
      await page.send('Emulation.setDeviceMetricsOverride', PHONE);
      await page.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
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
  on('Runtime.consoleAPICalled', p => { if (p.type === 'error' || p.type === 'assert') errors.push(`console.${p.type} : ${text(p.args)}`); });
  on('Runtime.exceptionThrown', p => errors.push(`exception : ${p.exceptionDetails.exception?.description || p.exceptionDetails.text}`));
  on('Log.entryAdded', p => { if (p.entry.level === 'error') errors.push(`${p.entry.source} : ${p.entry.text}${p.entry.url ? ' (' + p.entry.url + ')' : ''}`); });
  await Promise.all([send('Runtime.enable'), send('Log.enable'), send('Page.enable')]);

  const page = {
    send, on, errors,
    // évalue une expression dans la page (promesse attendue) et renvoie sa valeur (JSON)
    async eval(expression) {
      const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
      if (r.exceptionDetails) throw new Error(`dans la page : ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}\n  ${expression}`);
      return r.result.value;
    },
    async goto(url) {
      const loaded = new Promise(r => on('Page.loadEventFired', r));
      await send('Page.navigate', { url });
      await loaded;
    },
    // attend qu'une expression de la page soit vraie
    waitFor(expression, opts = {}) { return waitUntil(() => page.eval(expression), { what: expression, ...opts }); },
    // appui sur un élément (événement click du DOM, comme un toucher) ; échoue s'il est absent ou masqué
    async click(selector) {
      const ok = await page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
        if (!el || el.hidden || el.disabled || !el.getClientRects().length) return false; el.click(); return true; })()`);
      if (!ok) throw new Error(`élément absent, masqué ou désactivé : ${selector}`);
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
    assertNoErrors() {
      if (errors.length) throw new Error(`erreurs dans la console :\n  ${errors.join('\n  ')}`);
    },
    close() { try { ws.close(); } catch { /* déjà fermée */ } },
  };
  return page;
}
