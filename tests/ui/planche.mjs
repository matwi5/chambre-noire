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
// toutes). Chaque vue est capturée à chaque taille, la page redimensionnée sans rechargement, une fois les animations
// d'ouverture finies (deux images d'animation, puis plus rien en cours ni en attente) ; une rangée par taille et par
// version. Renvoie le chemin de la planche. Vues d'état, des scénarios tenus le temps des captures : avant (bouton
// Avant tenu sur la carte du dessus, au doigt ou à la souris selon la taille), encours (carte en cours avec la
// pastille « +1 en attente », générations retenues par HOLD=planche, relâchées après les captures).
// La rangée « avant » n'emploie que des aides du pilote présentes depuis longtemps (goto, waitFor, eval, generate,
// keepPile, tab, enterPrivate, send ; bench.release, bench.idle), pour tourner avec le pilote de ce commit ; les
// tailles passent par applyView, importée du pilote de l'arbre de travail, qui n'emploie que send.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { applyView, PHONE, PC, TABLET, TABLET_WIDE } from './driver.mjs';

const SELF = fileURLToPath(import.meta.url), HERE = path.dirname(SELF);   // chemin décodé (espaces)
const READY = `$('lamp').classList.contains('ok')`;
// transitions et animations finies, et aucune en attente de départ (les animations sans fin, comme la lampe qui pulse,
// exceptées), après deux images d'animation (une ouverture lancée au rendu suivant) : capture nette
const SETTLED = `new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))).then(() =>
  !document.getAnimations().some(a => (a.playState === 'running' || a.pending)
    && a.effect.getComputedTiming().iterations !== Infinity))`;
// image d'entrée d'une édition, dessinée dans la page (data URL)
const PLAIN = `(() => { const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d'); g.fillStyle = '#3050a0'; g.fillRect(0, 0, 256, 256); return c.toDataURL(); })()`;
// demande envoyée au Mac par la page, comme l'interface (fields : champs JavaScript, prompt compris)
const ask = (page, fields) => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 2, cfg: 1,
  seed: -1, preview: false, ref_images: [], ${fields} }).then(r => r.status)`);
// visionneuse refermée si le relâché d'un appui l'a ouverte (un toucher sur la carte l'ouvre), fondu fini
async function closed(page) {
  await page.eval(`$('viewer').classList.contains('on') && closeViewer()`);
  await page.waitFor(`getComputedStyle($('viewer')).visibility === 'hidden'`, { what: 'visionneuse fermée' });
}
// appui tenu au centre de l'élément selector, au doigt (taille tactile) ou à la souris, par le seul protocole (la
// rangée « avant » tourne avec le pilote d'un ancien commit) ; rend de quoi le relâcher
async function holdAt(page, selector, mobile) {
  const c = await page.eval(`(r => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 }))(document.querySelector(
    ${JSON.stringify(selector)}).getBoundingClientRect())`);
  if (mobile) {
    await page.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: c.x, y: c.y, id: 1 }] });
    return () => page.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  }
  const mouse = type => page.send('Input.dispatchMouseEvent', { type, x: c.x, y: c.y, button: 'left',
    buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1 });
  await mouse('mouseMoved');
  await mouse('mousePressed');
  return () => mouse('mouseReleased');
}
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
  avant: async page => {
    await ask(page, `mode: 'edit', prompt: 'planche : avant tenu', ref_images: [${PLAIN}]`);
    await page.waitFor(`(loadPile(), pileItems[0]?.prompt === 'planche : avant tenu')
      && (img => img && img.complete && img.naturalWidth > 0)($('pile').querySelector('[data-k="0"] img'))
      && !document.querySelector('#pile .bfr').hidden`, { what: 'édition sur la pile, bouton Avant', timeout: 30000 });
    let release = null;
    const BEFORE = `getComputedStyle(document.querySelector('#pile .bfr .bimg')).visibility === 'visible'`;
    return {
      each: async size => {                       // tenu de nouveau à chaque taille (le doigt ou la souris)
        await release?.();
        await closed(page);
        await page.waitFor(SETTLED, { what: 'mise en page finie' });   // (le bouton à sa place à cette taille)
        release = await holdAt(page, '#pile [data-k="0"] .bbtn', size.mobile);
        await page.waitFor(BEFORE, { what: 'image d\'avant affichée' });
      },
      after: async () => { await release?.(); await closed(page); },
    };
  },
  encours: async (page, bench) => {
    await page.generate('HOLD=planche planche : carte en cours');
    await ask(page, `mode: 't2i', prompt: 'HOLD=planche planche : en attente'`);
    await page.eval(`refreshStatus()`);
    await page.waitFor(`!$('runCard').hidden && !$('queueChip').hidden`, { what: 'carte en cours, pastille de file' });
    return { after: async () => { bench.release('planche'); await bench.idle(); } };
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
async function capture(page, bench, dir, names, sizes) {
  for (const size of sizes) fs.mkdirSync(path.join(dir, size), { recursive: true });
  for (const name of names) {
    let state = null;                             // vue d'état : each (à chaque taille) et after (fin des captures)
    try {
      state = await VIEWS[name](page, bench) || {};
      for (const size of sizes) {
        await applyView(page, SIZES[size]);
        if (state.each) await state.each(SIZES[size]);
        await page.waitFor(SETTLED, { what: 'animations finies' });
        await page.screenshot(path.join(dir, size, `${name}.png`));
      }
    } catch (e) {
      for (const size of sizes) fs.writeFileSync(path.join(dir, size, `${name}.txt`), String(e.message || e));
    } finally {
      await state?.after?.();
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

export default async (page, bench) => {
  const names = (process.env.PLANCHE_VUES || Object.keys(VIEWS).join(',')).split(',').filter(n => VIEWS[n]);
  const sizes = (process.env.PLANCHE_TAILLES || Object.keys(SIZES).join(',')).split(',').filter(n => SIZES[n]);
  if (process.env.PLANCHE_PARTIE) {               // appelée par la sonde d'un autre commit : captures seulement
    await capture(page, bench, process.env.PLANCHE_PARTIE, names, sizes);
    return process.env.PLANCHE_PARTIE;
  }
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'qwen-planche-vues-'));
  const avant = process.env.PLANCHE_AVANT;
  if (avant) before(avant, path.join(work, 'avant'), names, sizes);
  await capture(page, bench, path.join(work, 'apres'), names, sizes);
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
