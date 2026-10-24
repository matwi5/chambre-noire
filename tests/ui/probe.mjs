// Sonde : une vérification ponctuelle de l'interface, sans écrire de script jetable. Lance le banc et Chrome sans
// écran par le pilote (driver.mjs), ouvre l'interface dans la vue du téléphone, évalue une expression (ou un module),
// imprime le résultat en JSON, puis ferme tout.
//
//   node tests/ui/probe.mjs --eval "$('lamp').ariaLabel"
//   node tests/ui/probe.mjs --width 1280 --shot /tmp/vue.png --eval "document.title"
//   node tests/ui/probe.mjs --private --eval "inPrivate()"          # dans l'espace privé (créé pour l'occasion)
//   node tests/ui/probe.mjs --script /tmp/verif.mjs                 // export default async (page, bench) => valeur
//
// --width N : largeur de la vue (367 par défaut, celle du téléphone) ; --shot fichier.png : capture après
// l'évaluation. Variables d'environnement : celles du pilote (CHROME, PYTHON).
import path from 'node:path';
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';
import { startBench, launchChrome, PHONE } from './driver.mjs';

const { values: opt } = parseArgs({ options: {
  eval: { type: 'string' }, script: { type: 'string' }, width: { type: 'string' }, shot: { type: 'string' },
  private: { type: 'boolean', default: false } } });
if (!opt.eval === !opt.script) {
  console.error('sonde : donner --eval <expression> ou --script <fichier.mjs> (l\'un des deux)');
  process.exit(2);
}

let bench, chrome, code = 0;
try {
  bench = await startBench();
  chrome = await launchChrome();
  const page = await chrome.phonePage();
  if (opt.width) await page.send('Emulation.setDeviceMetricsOverride', { ...PHONE, width: Number(opt.width) });
  await page.goto(bench.url + '/');
  await page.waitFor(`$('lamp').classList.contains('ok')`, { what: 'moteur prêt affiché' });
  if (opt.private) {
    await page.eval(`postJson('/api/private/create', { code: 'code-de-la-sonde' })`);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  }
  const result = opt.eval ? await page.eval(opt.eval)
    : await (await import(pathToFileURL(path.resolve(opt.script)).href)).default(page, bench);
  console.log(JSON.stringify(result, null, 2) ?? 'undefined');
  if (opt.shot) await page.screenshot(opt.shot);
  if (page.errors.length) console.error(`erreurs dans la console :\n  ${page.errors.join('\n  ')}`);
} catch (e) {
  console.error(e.message);
  code = 1;
} finally {
  await chrome?.close();
  await bench?.stop();
}
process.exit(code);
