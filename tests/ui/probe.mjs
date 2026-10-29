// Sonde : une vérification ponctuelle de l'interface, sans écrire de script jetable. Lance le banc et Chrome sans
// écran par le pilote (driver.mjs), ouvre l'interface dans la vue du téléphone, évalue une expression (ou un module),
// imprime le résultat en JSON, puis ferme tout.
//
//   node tests/ui/probe.mjs --eval "$('lamp').ariaLabel"
//   node tests/ui/probe.mjs --width 1280 --shot /tmp/vue.png --eval "document.title"
//   node tests/ui/probe.mjs --private --eval "inPrivate()"          # dans l'espace privé (créé pour l'occasion)
//   node tests/ui/probe.mjs --script /tmp/verif.mjs                 // export default async (page, bench) => valeur
//   node tests/ui/probe.mjs --script tests/ui/planche.mjs           // planche de captures (voir planche.mjs)
//   node tests/ui/probe.mjs --svg tools/ui/logo.svg --size 512 --shot /tmp/icone.png   // SVG rendu à 512×512 px
//   node tests/ui/probe.mjs --measure '#pile,#composer' [--width 1280]   # boîtes, défilement, visibilité
//   node tests/ui/probe.mjs --dump                                         # état de la page (page.state du pilote)
//
// --measure sel1,sel2 : pour chaque sélecteur, chaque élément trouvé (rectangle à l'écran, scrollHeight et
// clientHeight, visible : présent, ni masqué ni sans boîte, au moins en partie dans la fenêtre), sans script jetable ;
// --dump : la ligne d'état que le pilote ajoute à un délai dépassé (page visible, focus, onglets, onglet affiché,
// verrous de tri). Les deux se combinent avec --eval ou --script (évalués d'abord), ou s'emploient seuls.
//
// --width N : largeur de la vue (367 par défaut, celle du téléphone) ; --shot fichier.png : capture après
// l'évaluation. --svg : sans banc, le SVG est dessiné seul à --size px de côté (densité 1, fond transparent), et la
// capture est coupée à cette taille exacte (Chrome sans écran a une fenêtre plus haute que la zone affichée : sans la
// coupe, l'image sortirait plus haute). Variables d'environnement : celles du pilote (CHROME, PYTHON).
import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';
import { startBench, launchChrome, PHONE } from './driver.mjs';

const { values: opt } = parseArgs({ options: {
  eval: { type: 'string' }, script: { type: 'string' }, width: { type: 'string' }, shot: { type: 'string' },
  private: { type: 'boolean', default: false }, svg: { type: 'string' }, size: { type: 'string' },
  measure: { type: 'string' }, dump: { type: 'boolean', default: false } } });
const given = [opt.eval, opt.script, opt.svg].filter(Boolean).length;
if (given > 1 || (!given && !opt.measure && !opt.dump) || (opt.svg && !(opt.shot && opt.size))) {
  console.error('sonde : donner --eval <expression>, --script <fichier.mjs> ou --svg <fichier.svg> --size N '
    + '--shot <fichier.png> (un seul des trois), et ou --measure <sélecteurs>, --dump');
  process.exit(2);
}

// boîtes des éléments de chaque sélecteur (séparés par des virgules hors parenthèses : '#a,.b:not(.c, .d)' en donne
// deux) : rectangle, défilement, visibilité
function measure(page, selectors) {
  const list = [];
  let depth = 0, cur = '';
  for (const c of selectors) {
    depth += c === '(' ? 1 : c === ')' ? -1 : 0;
    if (c === ',' && !depth) { list.push(cur.trim()); cur = ''; } else cur += c;
  }
  if (cur.trim()) list.push(cur.trim());
  return page.eval(`Object.fromEntries(${JSON.stringify(list)}.map(sel => [sel,
    [...document.querySelectorAll(sel)].map(el => { const r = el.getBoundingClientRect();
      const shown = !el.hidden && getComputedStyle(el).display !== 'none' && el.getClientRects().length > 0;
      return { id: el.id || undefined, rect: { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width),
        height: Math.round(r.height) }, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
        visible: shown && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth }; })]))`);
}

// SVG rendu seul à size × size px : vue à la taille exacte, densité 1, fond transparent, capture coupée à la taille
async function renderSvg(page, file, size, shot) {
  const metrics = { width: size, height: size, deviceScaleFactor: 1, mobile: false };
  await page.send('Emulation.setDeviceMetricsOverride', metrics);
  await page.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  const html = `<!doctype html><style>html,body{margin:0;background:transparent}img{display:block;width:${size}px;`
    + `height:${size}px}</style><img src="data:image/svg+xml;base64,${fs.readFileSync(file).toString('base64')}">`;
  await page.goto('data:text/html;base64,' + Buffer.from(html).toString('base64'));
  await page.waitFor(`document.querySelector('img').complete`, { what: 'SVG dessiné' });
  const r = await page.send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: size, height: size,
    scale: 1 } });
  fs.writeFileSync(shot, Buffer.from(r.data, 'base64'));
  return { shot, size };
}

let bench, chrome, code = 0;
try {
  if (!opt.svg) bench = await startBench();         // avant Chrome : la page est connectée au banc (cookie)
  chrome = await launchChrome();
  const page = await chrome.phonePage();
  if (opt.svg) {
    console.log(JSON.stringify(await renderSvg(page, opt.svg, Number(opt.size), opt.shot)));
  } else {
    if (opt.width) await page.send('Emulation.setDeviceMetricsOverride', { ...PHONE, width: Number(opt.width) });
    await page.goto(bench.url + '/');
    await page.ready();
    if (opt.private) await page.enterPrivate('code-de-la-sonde');
    if (opt.eval || opt.script) {
      const result = opt.eval ? await page.eval(opt.eval)
        : await (await import(pathToFileURL(path.resolve(opt.script)).href)).default(page, bench);
      console.log(JSON.stringify(result, null, 2) ?? 'undefined');
    }
    if (opt.measure) console.log(JSON.stringify(await measure(page, opt.measure), null, 2));
    if (opt.dump) console.log(await page.state());
    if (opt.shot) await page.screenshot(opt.shot);
    if (page.errors.length) console.error(`erreurs dans la console :\n  ${page.errors.join('\n  ')}`);
  }
} catch (e) {
  console.error(e.message);
  code = 1;
} finally {
  await chrome?.close();
  await bench?.stop();
}
process.exit(code);
