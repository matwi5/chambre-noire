// Planche de captures : les vues principales de l'interface, côte à côte sur une seule image, à plusieurs tailles
// d'écran (téléphone, tablette en hauteur et en largeur, PC), au lieu de scripts jetables de captures avant/après.
// Lancée par la sonde, qui fournit le banc et la page :
//
//   node tests/ui/probe.mjs --script tests/ui/planche.mjs                 # planche de l'arbre de travail
//   PLANCHE_AVANT=dev node tests/ui/probe.mjs --script tests/ui/planche.mjs   // + une rangée « avant » (commit)
//
// Variables : PLANCHE_SORTIE (fichier PNG ; défaut : planche.png du dossier temporaire du système), PLANCHE_AVANT
// (commit de la rangée « avant » : rejouée par la sonde de ce commit, dans un worktree temporaire supprimé à la fin),
// PLANCHE_VUES (noms séparés par des virgules, parmi VIEWS ; défaut : toutes), PLANCHE_TAILLES (parmi SIZES ; défaut :
// toutes). Chaque vue est capturée à chaque taille, la page redimensionnée sans rechargement ; une rangée par taille et
// par version. Renvoie le chemin de la planche.
// La rangée « avant » n'emploie que des aides du pilote présentes depuis longtemps (goto, waitFor, eval, generate,
// keepPile, tab, enterPrivate, send), pour tourner avec le pilote de ce commit ; les tailles passent par applyView,
// importée du pilote de l'arbre de travail, qui n'emploie que send.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { applyView, PHONE, PC, TABLET, TABLET_WIDE } from './driver.mjs';

const SELF = fileURLToPath(import.meta.url), HERE = path.dirname(SELF);   // chemin décodé (espaces)
const READY = `$('lamp').classList.contains('ok')`;
// transitions et animations finies (les animations sans fin, comme la lampe qui pulse, exceptées) : capture nette
const SETTLED = `!document.getAnimations().some(a => a.playState === 'running'
  && a.effect.getComputedTiming().iterations !== Infinity)`;
// tailles d'écran, dans l'ordre des rangées
const SIZES = { telephone: PHONE, tablette: TABLET, 'tablette-paysage': TABLET_WIDE, pc: PC };
// hauteur d'une capture sur la planche (largeur selon les proportions de sa taille)
const CELL_H = 760;
// vues, dans l'ordre : chacune amène la page dans l'état voulu (en partant de la précédente)
const VIEWS = {
  labo: async page => { await page.waitFor(READY, { what: 'moteur prêt' }); },
  pile: async page => {
    await page.generate('planche : une image dans la pile');
    await page.waitFor(`pileItems.length > 0 && (img => img && img.complete && img.naturalWidth > 0)
      ($('pile').querySelector('[data-k="0"] img'))`, { what: 'image dans la pile', timeout: 30000 });
  },
  tirages: async page => {
    await page.keepPile();
    await page.tab('tirages');
    await page.waitFor(`histItems.length > 0`, { what: 'Tirages' });
  },
  visionneuse: async page => {
    await page.eval(`openViewer(0, histItems)`);
    await page.waitFor(`$('viewer').classList.contains('on') && $('vImg').complete`, { what: 'visionneuse' });
  },
  prive: async page => {
    await page.eval(`closeViewer()`);
    await page.tab('labo');
    await page.enterPrivate('code-de-la-planche');
  },
};

// captures des vues demandées dans dir, à chaque taille (taille/vue.png) ; une vue en échec est notée dans
// taille/vue.txt (toutes ses tailles). La page finit à la taille du téléphone
async function capture(page, dir, names, sizes) {
  for (const size of sizes) fs.mkdirSync(path.join(dir, size), { recursive: true });
  for (const name of names) {
    try {
      await VIEWS[name](page);
      for (const size of sizes) {
        await applyView(page, SIZES[size]);
        await page.waitFor(SETTLED, { what: 'animations finies' });
        await page.screenshot(path.join(dir, size, `${name}.png`));
      }
    } catch (e) {
      for (const size of sizes) fs.writeFileSync(path.join(dir, size, `${name}.txt`), String(e.message || e));
    }
    await applyView(page, PHONE);
  }
}

// rangée « avant » : la sonde du commit, dans un worktree temporaire, capture les mêmes vues dans dir
function before(commit, dir, names, sizes) {
  const tree = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-planche-'));
  const git = (...args) => spawnSync('git', args, { cwd: path.resolve(HERE, '..', '..'), encoding: 'utf8' });
  const added = git('worktree', 'add', '--detach', tree, commit);
  if (added.status) throw new Error(`worktree du commit ${commit} : ${added.stderr.trim()}`);
  try {
    const probe = path.join(tree, 'tests', 'ui', 'probe.mjs');
    const r = spawnSync('node', [probe, '--script', SELF], {
      cwd: tree, encoding: 'utf8', timeout: 600000,
      env: { ...process.env, PLANCHE_PARTIE: dir, PLANCHE_VUES: names.join(','), PLANCHE_TAILLES: sizes.join(','),
        PLANCHE_AVANT: '' } });
    if (r.status) throw new Error(`sonde du commit ${commit} : ${(r.stderr || r.stdout).trim().slice(-400)}`);
  } finally {
    git('worktree', 'remove', '--force', tree);
    fs.rmSync(tree, { recursive: true, force: true });
  }
}

// largeur d'une capture de cette taille sur la planche (hauteur CELL_H)
const cellWidth = size => Math.round(SIZES[size].width * CELL_H / SIZES[size].height);

// page HTML de la planche : une rangée par dossier ([titre, dossier, taille]), une colonne par vue, chaque capture à
// la hauteur CELL_H
function sheet(rows, names) {
  const cell = (dir, name) => {
    const png = path.join(dir, `${name}.png`), txt = path.join(dir, `${name}.txt`);
    const data = () => fs.readFileSync(png).toString('base64');
    return fs.existsSync(png) ? `<img src="data:image/png;base64,${data()}">`
      : `<div class="miss">${fs.existsSync(txt) ? fs.readFileSync(txt, 'utf8').replace(/</g, '&lt;')
        : 'absente'}</div>`;
  };
  return `<!doctype html><meta charset="utf-8"><style>
    body { margin:0; padding:16px; background:#222; color:#eee; font:14px system-ui, sans-serif; }
    .row { display:flex; gap:16px; margin-bottom:16px; }
    .col b { display:block; margin:0 0 6px; } img, .miss { width:100%; height:${CELL_H}px; display:block; }
    .miss { background:#444; padding:12px; box-sizing:border-box; white-space:pre-wrap; }
    h2 { margin:0 0 8px; font-size:16px; }</style>
    ${rows.map(([title, dir, size]) => `<h2>${title}</h2><div class="row">${names.map(n =>
      `<div class="col" style="width:${cellWidth(size)}px"><b>${n}</b>${cell(dir, n)}</div>`).join('')}</div>`)
    .join('')}`;
}

export default async (page) => {
  const names = (process.env.PLANCHE_VUES || Object.keys(VIEWS).join(',')).split(',').filter(n => VIEWS[n]);
  const sizes = (process.env.PLANCHE_TAILLES || Object.keys(SIZES).join(',')).split(',').filter(n => SIZES[n]);
  if (process.env.PLANCHE_PARTIE) {               // appelée par la sonde d'un autre commit : captures seulement
    await capture(page, process.env.PLANCHE_PARTIE, names, sizes);
    return process.env.PLANCHE_PARTIE;
  }
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-planche-vues-'));
  const avant = process.env.PLANCHE_AVANT;
  if (avant) before(avant, path.join(work, 'avant'), names, sizes);
  await capture(page, path.join(work, 'apres'), names, sizes);
  // rangées : pour chaque taille, « avant » puis « après »
  const rows = sizes.flatMap(size => [
    ...avant ? [[`${size} · avant (${avant})`, path.join(work, 'avant', size), size]] : [],
    [`${size} · ${avant ? 'après (arbre de travail)' : 'arbre de travail'}`, path.join(work, 'apres', size), size]]);
  // planche dessinée dans la même page, à sa taille exacte (densité 1 : une capture par pixel CSS)
  const html = path.join(work, 'planche.html');
  fs.writeFileSync(html, sheet(rows, names));
  const width = 16 + Math.max(...sizes.map(size => names.length * (cellWidth(size) + 16)));
  const height = 16 + rows.length * (CELL_H + 60);
  await page.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
  await page.goto('file://' + html);
  const out = process.env.PLANCHE_SORTIE || path.join(os.tmpdir(), 'planche.png');
  const shot = await page.send('Page.captureScreenshot', { format: 'png',
    clip: { x: 0, y: 0, width, height, scale: 1 }, captureBeyondViewport: true });
  fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));
  fs.rmSync(work, { recursive: true, force: true });
  return out;
};
