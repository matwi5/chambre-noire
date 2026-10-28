// Bouton Avant (spec du 27/10/2026, section 4) : sur une image issue d'une édition à une seule image d'entrée (ou
// d'un Dessin avec masque), le maintenir montre l'image d'entrée à la place de l'image produite, dans le même cadre,
// dans la visionneuse et sur la carte du dessus de la pile ; relâché, l'image produite revient.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/avant.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil, elapse, PC, PHONE, TABLET } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await page.goto(bench.url + '/');
  await page.ready();
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

// photo unie de w×h px (data URL), dessinée dans la page
const plain = (color, w = 256, h = 256) => `(() => { const c = document.createElement('canvas');
  c.width = ${w}; c.height = ${h}; const g = c.getContext('2d'); g.fillStyle = '${color}'; g.fillRect(0, 0, ${w}, ${h});
  return c.toDataURL('image/png'); })()`;
// demande envoyée au Mac comme par l'interface (fields : champs JavaScript de la demande, prompt compris)
const ask = fields => page.eval(`postJson('/api/generate', { width: 512, height: 512, steps: 2, cfg: 1, seed: -1,
  preview: false, ${fields} }).then(r => r.status)`);
// rangs dans la pile affichée des images à ce prompt
const ranks = prompt => page.eval(`pileView().map((it, k) => it.prompt === ${JSON.stringify(prompt)} ? k : -1)
  .filter(k => k >= 0)`);
const BUTTON = '#vBefore .bbtn';

test('bouton présent sur les seules images comparables : une photo, variantes, campagne, masque', async () => {
  await page.freshLabo(bench);
  const one = plain('#2060c0'), two = plain('#20a040');
  assert.equal(await ask(`mode: 't2i', prompt: 'za texte'`), 202);
  assert.equal(await ask(`mode: 'edit', prompt: 'za une', ref_images: [${one}]`), 202);
  assert.equal(await ask(`mode: 'edit', prompt: 'za deux', ref_images: [${one}, ${two}]`), 202);
  assert.equal(await ask(`mode: 'edit', prompt: 'za variantes', count: 2, ref_images: [${one}]`), 202);
  assert.equal(await ask(`mode: 'edit', prompt: 'za campagne', campaign: [{ image: ${one}, width: 512,
    height: 512 }, { image: ${two}, width: 512, height: 512 }]`), 202);
  assert.equal(await ask(`mode: 'mask', prompt: 'za masque', init_image: ${one}, mask_image: ${plain('#ffffff')},
    ref_images: [${two}]`), 202);
  assert.equal(await ask(`mode: 'annot', prompt: 'za annotation', ref_images: [${one}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  const expected = { 'za texte': [false], 'za une': [true], 'za deux': [false], 'za variantes': [true, true],
    'za campagne': [true, true], 'za masque': [true], 'za annotation': [false] };
  for (const [prompt, want] of Object.entries(expected)) {
    await page.waitFor(`pileView().filter(it => it.prompt === ${JSON.stringify(prompt)}).length === ${want.length}`,
      { what: `« ${prompt} » dans la pile` });
    const shown = [];
    for (const k of await ranks(prompt)) {
      await page.eval(`openViewer(${k}, pileView())`);
      await page.imageShown('#vImg', `image de « ${prompt} »`);
      shown.push(await page.visible(BUTTON));
    }
    assert.deepEqual(shown, want, `bouton Avant de « ${prompt} »`);
  }
  await page.closeViewer();
  page.assertNoErrors();
});

// état de l'image avant du cadre sel : visible, adresse de l'image peinte, étiquette « Avant » visible
const beforeState = sel => page.eval(`(fr => { const img = fr.querySelector('.bimg'), tag = fr.querySelector('.btag');
  return { on: getComputedStyle(img).visibility === 'visible', src: img.currentSrc,
    tag: getComputedStyle(tag).visibility === 'visible' && tag.textContent === 'Avant' }; })(
  document.querySelector(${JSON.stringify(sel)}))`);
const beforeOn = (sel, what) => page.waitFor(`(fr => getComputedStyle(fr.querySelector('.bimg')).visibility
  === 'visible')(document.querySelector(${JSON.stringify(sel)}))`, { what });
const OFF = { on: false, tag: false };
const off = async sel => { const { on, tag } = await beforeState(sel); return { on, tag }; };
// visionneuse ouverte sur l'image de la pile à ce prompt, son image affichée et l'ouverture finie (l'image grandit de
// 96 % à sa taille en 0,35 s)
async function openOn(prompt) {
  await page.viewPile(prompt);
  await page.imageShown('#vImg', `image de « ${prompt} »`);
  await page.waitFor(`!$('vImg').getAnimations().length`, { what: 'ouverture de la visionneuse finie' });
}

test('visionneuse : l\'image d\'entrée tant qu\'on tient Avant, l\'image produite au relâché, même hors du bouton',
  async () => {
    await page.freshLabo(bench);
    assert.equal(await ask(`mode: 't2i', prompt: 'zb texte'`), 202);
    assert.equal(await ask(`mode: 'edit', prompt: 'zb une', ref_images: [${plain('#c04020')}]`), 202);
    await bench.idle();
    await page.eval(`loadPile()`);
    await openOn('zb une');
    assert.deepEqual(await off('#vBefore'), OFF, 'image produite avant l\'appui');
    assert.equal(await page.eval(`ready.has(inputUrl(vList[vIndex], 'ref_1.png'))`), true, 'entrée chargée en avance');

    await page.hold(BUTTON);
    await beforeOn('#vBefore', 'image avant à l\'appui');
    const held = await beforeState('#vBefore');
    assert.match(held.src, /\/api\/input\?name=.*&file=ref_1\.png$/, 'l\'image d\'entrée complète');
    assert.equal(held.tag, true, 'étiquette « Avant »');
    assert.equal(await page.eval(`$('viewer').classList.contains('immersive')`), false, 'pas de mode immersif');
    await page.release();
    assert.deepEqual(await off('#vBefore'), OFF, 'relâché');
    assert.equal(await page.eval(`vList[vIndex].prompt`), 'zb une', 'aucun pas vers une autre image');

    await page.swipe(BUTTON, -140, -60, { hold: true });   // doigt glissé hors du bouton, toujours posé
    assert.equal((await beforeState('#vBefore')).on, true, 'doigt hors du bouton : toujours l\'image avant');
    await page.release();
    assert.deepEqual(await off('#vBefore'), OFF, 'relâché hors du bouton');
    assert.equal(await page.eval(`vList[vIndex].prompt`), 'zb une', 'le glissé ne change pas d\'image');

    await page.hold(BUTTON);
    await beforeOn('#vBefore', 'image avant');
    await page.eval(`dispatchEvent(new Event('blur'))`);    // fenêtre quittée pendant l'appui
    assert.deepEqual(await off('#vBefore'), OFF, 'fenêtre quittée');
    await page.release();

    await page.hold(BUTTON);
    await beforeOn('#vBefore', 'image avant');
    const other = await page.eval(`pileView().findIndex(it => it.prompt === 'zb texte')`);
    await page.eval(`openViewer(${other}, pileView())`);   // image suivante pendant l'appui
    await page.imageShown('#vImg');
    assert.deepEqual({ ...await off('#vBefore'), button: await page.visible(BUTTON) }, { ...OFF, button: false },
      'image sans entrée : ni image avant ni bouton');
    await page.release();
    await page.closeViewer();
    page.assertNoErrors();
  });

test('carte du dessus : Avant n\'ouvre pas la visionneuse et ne trie rien', async () => {
  await page.freshLabo(bench);
  assert.equal(await ask(`mode: 'edit', prompt: 'zc une', ref_images: [${plain('#40c060')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus');
  const CARD = '#pile [data-k="0"] .bbtn';
  await page.waitFor(`!document.querySelector('#pile .bfr').hidden`, { what: 'bouton Avant de la carte' });
  assert.equal(await page.eval(`ready.has(inputUrl(pileView()[0], 'ref_1.png'))`), true, 'entrée chargée en avance');
  for (const mouse of [false, true]) {
    await page.hold(CARD, { mouse });
    await beforeOn('#pile .bfr', 'image avant sur la carte');
    assert.match((await beforeState('#pile .bfr')).src, /&file=ref_1\.png$/);
    await page.release();
    assert.deepEqual(await off('#pile .bfr'), OFF, 'relâché');
  }
  await page.swipe(CARD, 180, 0);                      // un geste qui part du bouton n'est pas un balayage
  await bench.idle();
  assert.deepEqual(await page.eval(`({ viewer: $('viewer').classList.contains('on'), pile: pileView().length,
    sorting: sorting.size, undo: !$('undoBar').hidden,
    moved: document.querySelector('#pile [data-k="0"]').style.transform })`),
  { viewer: false, pile: 1, sorting: 0, undo: false, moved: '' }, 'ni visionneuse, ni tri');
  page.assertNoErrors();
});

// rectangle affiché du contenu d'une image (object-fit : contain dans sa boîte) et rectangle du cadre de l'image avant
const RECTS = sel => `(fr => { const of = fr.of, b = of.getBoundingClientRect(), r = of.naturalWidth / of.naturalHeight;
  const w = Math.min(b.width, b.height * r), h = Math.min(b.height, b.width / r);
  const c = fr.querySelector('.bimg').getBoundingClientRect();
  return { content: [b.left + (b.width - w) / 2, b.top + (b.height - h) / 2, w, h],
    before: [c.left, c.top, c.width, c.height],
    fit: getComputedStyle(fr.querySelector('.bimg')).objectFit }; })(document.querySelector(${JSON.stringify(sel)}))`;
const within1 = (a, b) => a.length === b.length && a.every((v, k) => Math.abs(v - b[k]) <= 1);

test('cadre : le contenu affiché de l\'image produite, étirée au format « Image », entière en 1:1', async () => {
  await page.freshLabo(bench);
  const wide = plain('#8040c0', 400, 224);              // 16:9 environ ; « Image » : 512×288, 0,4 % d'écart
  assert.equal(await ask(`mode: 'edit', prompt: 'zd carre', ref_images: [${wide}]`), 202);
  assert.equal(await ask(`mode: 'edit', prompt: 'zd image', width: 512, height: 288, ref_images: [${wide}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  for (const [prompt, fit] of [['zd image', 'fill'], ['zd carre', 'contain']]) {
    for (const where of ['viewer', 'pile']) {
      let sel = '#vBefore';
      if (where === 'viewer') await openOn(prompt);
      else {
        await page.closeViewer();
        if (prompt === 'zd carre') {                       // « zd image », arrivée après, gardée : « zd carre » dessus
          await page.click('#pileYes');
          await page.waitFor(`pileView().length === 1 && pileView()[0].prompt === 'zd carre'`,
            { what: 'zd carre dessus' });
        }
        await page.imageShown('#pile [data-k="0"] .pimg img');
        sel = '#pile .bfr';
      }
      await page.hold(`${sel} .bbtn`);
      await page.waitFor(`(img => img.complete && img.naturalWidth > 0
        && getComputedStyle(img).visibility === 'visible')(document.querySelector('${sel} .bimg'))`,
      { what: `image avant de « ${prompt} » (${where})` });
      const r = await page.eval(RECTS(sel));
      await page.release();
      assert.ok(within1(r.content, r.before), `${prompt} (${where}) : ${r.before} au lieu de ${r.content}`);
      assert.equal(r.fit, fit, `${prompt} (${where}) : ${fit}`);
    }
  }
  page.assertNoErrors();
});

test('miniature de l\'image d\'entrée d\'abord, si l\'image complète n\'est pas encore là', async () => {
  await page.freshLabo(bench);
  // l'image d'entrée complète retenue avant le Mac dès sa première demande (la carte du dessus la charge en avance) ;
  // sa miniature, …&thumb=1&t=…, passe
  const held = await page.holdRequests(['*&file=ref_1.png'], () => true);
  assert.equal(await ask(`mode: 'edit', prompt: 'ze une', ref_images: [${plain('#30a0a0')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await openOn('ze une');
  await page.hold(BUTTON);
  await beforeOn('#vBefore', 'miniature à l\'appui');
  assert.match((await beforeState('#vBefore')).src, /&file=ref_1\.png&thumb=1&t=\d+$/, 'la miniature');
  await held.release();
  await page.waitFor(`$('vBeforeImg').currentSrc.endsWith('&file=ref_1.png')`, { what: 'puis l\'image complète' });
  assert.equal((await beforeState('#vBefore')).on, true, 'toujours tenu');
  await page.release();
  await page.closeViewer();
  page.assertNoErrors();
});

test('PC : zoom à la molette, puis Avant : même zoom et même cadrage', async () => {
  await page.setView(PC);
  try {
    await page.freshLabo(bench);
    assert.equal(await ask(`mode: 'edit', prompt: 'zf une', ref_images: [${plain('#a0a030')}]`), 202);
    await bench.idle();
    await page.eval(`loadPile()`);
    await openOn('zf une');
    const at = await page.eval(`(r => [r.left + r.width * .3, r.top + r.height * .3])(
      $('vImg').getBoundingClientRect())`);
    for (let k = 0; k < 3; k++) await page.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: at[0], y: at[1],
      deltaX: 0, deltaY: -200 });
    await page.waitFor(`$('viewer').classList.contains('zoomed') && !$('vStage').classList.contains('drag')`,
      { what: 'image zoomée' });
    const framing = () => page.eval(`(() => { const a = $('vImg'), b = $('vBeforeImg'), box = e => (r => [r.left,
      r.top, r.width, r.height])(e.getBoundingClientRect());
      return { same: a.style.transform === b.style.transform, zoom: a.style.transform, a: box(a), b: box(b) }; })()`);
    // le bouton à la souris, puis Espace tenue
    for (const [how, down, up] of [['bouton', () => page.hold(BUTTON, { mouse: true }), () => page.release()],
      ['Espace', () => page.keyDown(' '), () => page.keyUp(' ')]]) {
      await down();
      await beforeOn('#vBefore', `image avant sur l'image zoomée (${how})`);
      const r = await framing();
      await up();
      assert.match(r.zoom, /scale\(/, `image zoomée (${how})`);
      assert.equal(r.same, true, `même transformation (${how})`);
      assert.ok(within1(r.a, r.b), `même cadrage (${how}) : ${r.b} au lieu de ${r.a}`);
    }
    await page.closeViewer();
  } finally { await page.setView(PHONE); }
  page.assertNoErrors();
});

test('étiquette « Avant » seulement avec l\'image d\'entrée à l\'écran, pas pendant son chargement', async () => {
  await page.freshLabo(bench);
  // image d'entrée complète et sa miniature retenues avant le Mac dès leur première demande
  const held = await page.holdRequests(['*&file=ref_1.png*'], () => true);
  assert.equal(await ask(`mode: 'edit', prompt: 'zg une', ref_images: [${plain('#a03070')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus');
  await page.waitFor(`!document.querySelector('#pile .bfr').hidden`, { what: 'bouton Avant de la carte' });
  await page.hold('#pile [data-k="0"] .bbtn');
  assert.deepEqual(await off('#pile .bfr'), OFF, 'rien d\'arrivé : l\'image produite, sans étiquette');
  await held.release();
  await beforeOn('#pile .bfr', 'image d\'entrée arrivée');
  assert.equal((await beforeState('#pile .bfr')).tag, true, 'puis l\'étiquette');
  await page.release();
  page.assertNoErrors();
});

// ------------------------------------------------------------ Espace maintenue (ticket 1219940950193702, vue PC)
// Espace tenue sur sel (cadre de la carte du dessus ou de la visionneuse) : l'image avant à l'appui, répétitions du
// système comprises, l'image produite au relâché ; scrolls : la page, qui peut défiler, n'a pas défilé (mesuré une
// fois le défilement doux du navigateur fini)
async function spaceHold(sel, what, { scrolls = false } = {}) {
  if (scrolls) assert.equal(await page.eval(`document.documentElement.scrollHeight > innerHeight + 200`), true,
    `page qui défile (${what})`);
  const y = await page.eval(`scrollY`);
  await page.keyDown(' ');
  await beforeOn(sel, `Espace tenue : image avant (${what})`);
  assert.match((await beforeState(sel)).src, /&file=ref_1\.png$/, `l'image d'entrée (${what})`);
  for (let k = 0; k < 3; k++) await page.keyDown(' ', { repeat: true });
  assert.equal((await beforeState(sel)).on, true, `toujours tenue (${what})`);
  await page.keyUp(' ');
  assert.deepEqual(await off(sel), OFF, `Espace relâchée (${what})`);
  if (!scrolls) return;
  await elapse(600);
  assert.equal(await page.eval(`scrollY`), y, `page défilée (${what})`);
}

test('PC : Espace tenue montre l\'image avant, carte du dessus et visionneuse ; aucun bouton activé', async () => {
  await page.setView(PC);
  try {
    await page.freshLabo(bench);
    assert.equal(await ask(`mode: 'edit', prompt: 'zs dessous', ref_images: [${plain('#30a050')}]`), 202);
    assert.equal(await ask(`mode: 'edit', prompt: 'zs une', ref_images: [${plain('#c06020')}]`), 202);
    await bench.idle();
    await page.eval(`loadPile()`);
    await page.waitFor(`pileView()[0]?.prompt === 'zs une'`, { what: 'zs une dessus' });
    await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus');
    await page.waitFor(`!document.querySelector('#pile .bfr').hidden`, { what: 'bouton Avant de la carte' });
    await page.eval(`document.activeElement?.blur()`);
    await spaceHold('#pile .bfr', 'carte du dessus');
    // une page qui défile (tablette en hauteur, avec un clavier, champ de création déplié sous la pile) : Espace ne la
    // fait pas défiler
    await page.setView({ ...TABLET, height: 900 });
    await page.eval(`openComposer(); scrollTo(0, 0)`);
    await spaceHold('#pile .bfr', 'page qui défile', { scrolls: true });
    await page.setView(PC);
    // bouton tenu à la souris : Espace appuyée puis relâchée ne le relâche pas, le relâché de la souris oui
    await page.hold('#pile [data-k="0"] .bbtn', { mouse: true });
    await beforeOn('#pile .bfr', 'bouton tenu à la souris');
    await page.keyDown(' ');
    await page.keyUp(' ');
    assert.equal((await beforeState('#pile .bfr')).on, true, 'Espace a relâché l\'appui de la souris');
    await page.release();
    assert.deepEqual(await off('#pile .bfr'), OFF, 'relâché de la souris');
    await page.eval(`$('pileNo').focus()`);         // ✕ qui a le focus : Espace ne le déclenche pas
    await spaceHold('#pile .bfr', '✕ qui a le focus');
    assert.deepEqual(await page.eval(`[pileView()[0].prompt, !discarding, !flying]`), ['zs une', true, true],
      'Espace a jeté l\'image');
    await page.keyDown(' ');                        // fenêtre quittée pendant l'appui
    await beforeOn('#pile .bfr', 'image avant');
    await page.eval(`dispatchEvent(new Event('blur'))`);
    assert.deepEqual(await off('#pile .bfr'), OFF, 'fenêtre quittée');
    await page.keyUp(' ');
    await openOn('zs une');
    await page.eval(`$('vSort').querySelector('.btn').focus()`);   // Jeter de la visionneuse qui a le focus
    await spaceHold('#vBefore', 'visionneuse');
    assert.deepEqual(await page.eval(`[vList.length, !discarding]`), [2, true], 'Espace a jeté l\'image');
    await page.closeViewer();
  } finally { await page.setView(PHONE); }
  page.assertNoErrors();
});

test('PC : Espace sans effet sur une image non comparable, pendant une saisie, avec une feuille ouverte', async () => {
  await page.setView(PC);
  try {
    await page.freshLabo(bench);
    assert.equal(await ask(`mode: 'edit', prompt: 'zt une', ref_images: [${plain('#2080c0')}]`), 202);
    assert.equal(await ask(`mode: 't2i', prompt: 'zt texte'`), 202);
    await bench.idle();
    await page.eval(`loadPile()`);
    await page.waitFor(`pileView()[0]?.prompt === 'zt texte'`, { what: 'zt texte dessus' });
    await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus');
    await page.eval(`$('pileNo').focus()`);
    await page.press(' ');                          // non comparable : rien, ✕ pas déclenché
    assert.deepEqual(await page.eval(`[beforeHeld, pileView()[0].prompt, !discarding, !flying]`),
      [null, 'zt texte', true, true]);
    await page.click('#pileYes');                   // zt une dessus
    await page.waitFor(`pileView().length === 1 && !document.querySelector('#pile .bfr').hidden`,
      { what: 'zt une dessus, bouton Avant' });
    await page.eval(`$('prompt').focus()`);
    await page.press(' ');
    assert.equal(await page.eval(`[beforeHeld, $('prompt').value.endsWith(' ')].join()`), ',true',
      'saisie : une espace tapée, pas d\'image avant');
    await page.typePrompt('');
    await page.eval(`document.activeElement?.blur(); openSheet('setSheet')`);
    await page.keyDown(' ');
    assert.equal(await page.eval(`beforeHeld`), null, 'feuille ouverte : pas d\'image avant');
    await page.keyUp(' ');
    await page.closeSheet();
  } finally { await page.setView(PHONE); }
  page.assertNoErrors();
});

// ------------------------------------------------------------ espace privé (ticket 1219940998500742)
const PCODE = 'code-avant-prive';
// images de la page dont l'adresse (attribut, ou image peinte) est privée, et adresses privées chargées en avance
const PRIVATE_LEFT = `({ imgs: [...document.images].filter(i => secretUrl(i.getAttribute('src')) || secretUrl(i.want)
  || i.currentSrc.includes('/api/private/')).map(i => i.id || i.className || i.parentElement.className),
  ready: [...ready.keys()].filter(secretUrl), loads: secretLoads.size })`;
const NOTHING_LEFT = { imgs: [], ready: [], loads: 0 };
// dans l'espace privé, une édition privée à une photo dans la pile, ouverte dans la visionneuse, son image d'entrée
// chargée en avance, Avant tenu ; renvoie les marqueurs de l'image privée (identifiant, prompt, routes privées)
async function privateBefore(word) {
  await page.freshLabo(bench);
  await page.enterPrivate(PCODE);
  assert.equal(await ask(`mode: 'edit', prompt: '${word}', private: true, ref_images: [${plain('#6030a0')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await page.waitFor(`pileView()[0]?.prompt === '${word}'`, { what: 'image privée dans la pile' });
  await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus privée');
  await page.waitFor(`!document.querySelector('#pile .bfr').hidden`, { what: 'bouton Avant de la carte privée' });
  await openOn(word);
  await page.waitFor(`ready.get(inputUrl(vList[vIndex], 'ref_1.png'))?.im !== undefined`,
    { what: 'image d\'entrée privée chargée en avance' });
  await page.hold(BUTTON);
  await beforeOn('#vBefore', 'image avant privée');
  const id = await page.eval(`vList[vIndex].id`);
  return [id, word, '/api/private/', 'prive_'];
}

test('espace privé : Avant sur une image privée comparable, par la route privée, sans rien écrire', async () => {
  await page.freshLabo(bench);
  await page.enterPrivate(PCODE);
  assert.equal(await ask(`mode: 'edit', prompt: 'zh privee', private: true, ref_images: [${plain('#6030a0')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await page.waitFor(`pileView()[0]?.prompt === 'zh privee'`, { what: 'image privée dans la pile' });
  await page.imageShown('#pile [data-k="0"] .pimg img', 'carte du dessus privée');
  await page.waitFor(`!document.querySelector('#pile .bfr').hidden`, { what: 'bouton Avant de la carte privée' });
  const id = await page.eval(`pileView()[0].id`), disk = bench.disk();
  const PRIVATE_INPUT = new RegExp(`/api/private/input\\?id=${id}&file=ref_1\\.png$`);
  await page.hold('#pile [data-k="0"] .bbtn');
  await beforeOn('#pile .bfr', 'image avant privée sur la carte');
  assert.match((await beforeState('#pile .bfr')).src, PRIVATE_INPUT, 'carte : route privée des images d\'entrée');
  await page.release();
  await openOn('zh privee');
  await page.hold(BUTTON);
  await beforeOn('#vBefore', 'image avant privée dans la visionneuse');
  assert.match((await beforeState('#vBefore')).src, PRIVATE_INPUT, 'visionneuse : route privée');
  await page.release();
  await page.closeViewer();
  await bench.idle();
  assert.deepEqual(disk.written(), [], 'rien d\'écrit sur le disque du Mac');
  assert.equal(await page.eval(`JSON.stringify({ ...localStorage, ...sessionStorage })
    .includes(${JSON.stringify(id)})`), false, 'rien dans le stockage du navigateur');
  await page.privateIdle();
  await page.eval(`privLock()`);
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  page.assertNoErrors();
});

test('« Sortir » pendant l\'appui : bouton masqué dès l\'appui sur « Sortir », plus rien de privé après', async () => {
  const markers = await privateBefore('zi privee');
  await page.privateIdle();
  const lock = await page.holdRequests(['*/api/private/lock'], () => true);   // réponse du Mac retenue
  await page.eval(`void privLock()`);
  assert.deepEqual(await page.eval(`({ viewer: $('vBefore').hidden,
    card: document.querySelector('#pile .bfr')?.hidden, on: !!document.querySelector('.bfr.on') })`),
  { viewer: true, card: true, on: false }, 'bouton masqué pendant « Sortir »');
  await lock.release();
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  await page.release();
  assert.deepEqual(await page.eval(PRIVATE_LEFT), NOTHING_LEFT, 'images privées restées');
  assert.deepEqual(await page.leaks(markers), [], 'données privées restées dans la page');
  page.assertNoErrors();
});

test('fermeture de la page puis « Retour » pendant l\'appui : plus rien de privé', async () => {
  const markers = await privateBefore('zj privee');
  await page.privateIdle();
  await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))`);
  await page.release();
  assert.deepEqual(await page.eval(PRIVATE_LEFT), NOTHING_LEFT, 'fermeture : images privées restées');
  assert.deepEqual(await page.leaks(markers), [], 'fermeture : données privées restées');
  // règle levée : la page est déjà sortie de l'espace à pagehide, plus rien de privé n'est en route
  await page.eval(`dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))`);
  await page.lockedOnMac();
  await page.eval(`refreshStatus()`);
  assert.deepEqual(await page.eval(PRIVATE_LEFT), NOTHING_LEFT, 'retour : images privées revenues');
  assert.deepEqual(await page.leaks(markers), [], 'retour : données privées revenues');
  page.assertNoErrors();
});

test('« Retour » vers une page de l\'espace privé pendant l\'appui : plus rien de privé', async () => {
  const markers = await privateBefore('zk privee');
  await page.privateIdle();
  await page.eval(`dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))`);
  await page.release();
  await page.lockedOnMac();
  await page.eval(`refreshStatus()`);
  assert.deepEqual(await page.eval(PRIVATE_LEFT), NOTHING_LEFT, 'images privées restées');
  assert.deepEqual(await page.leaks(markers), [], 'données privées restées');
  page.assertNoErrors();
});

test('image avant privée en chargement pendant « Sortir » : rien n\'arrive après', async () => {
  await page.freshLabo(bench);
  await page.enterPrivate(PCODE);
  // l'image d'entrée privée complète retenue avant le Mac dès sa première demande (sa miniature passe) ; ses
  // demandes suivies par le réseau du navigateur jusqu'à leur issue (finie, ou abandonnée par la page)
  const FULL = /\/api\/private\/input\?.*&file=ref_1\.png$/, sent = new Set(), ended = new Set();
  page.on('Network.requestWillBeSent', p => { if (FULL.test(p.request.url)) sent.add(p.requestId); });
  page.on('Network.loadingFinished', p => ended.add(p.requestId));
  page.on('Network.loadingFailed', p => ended.add(p.requestId));
  await page.send('Network.enable');
  const held = await page.holdRequests(['*/api/private/input*&file=ref_1.png'], () => true);
  assert.equal(await ask(`mode: 'edit', prompt: 'zl privee', private: true, ref_images: [${plain('#6030a0')}]`), 202);
  await bench.idle();
  await page.eval(`loadPile()`);
  await page.waitFor(`pileView()[0]?.prompt === 'zl privee'`, { what: 'image privée dans la pile' });
  await openOn('zl privee');
  const markers = [await page.eval(`vList[vIndex].id`), 'zl privee', '/api/private/', 'prive_'];
  await page.hold(BUTTON);
  await beforeOn('#vBefore', 'miniature privée à l\'appui');
  assert.match((await beforeState('#vBefore')).src, /&thumb=1&t=\d+$/, 'la miniature, l\'image complète retenue');
  await page.eval(`privLock()`);                  // (un chargement privé reste en route exprès : pas de privateIdle)
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  await held.release();                             // la réponse de l'image complète arrive après la sortie
  // chaque demande de l'image complète arrivée à son issue, puis le temps de la décoder et de la poser
  const waiting = () => [...sent].filter(id => !ended.has(id));
  await waitUntil(() => sent.size > 0 && !waiting().length, { what: 'image complète arrivée' });
  await page.send('Network.disable');
  await page.eval(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  await page.release();
  assert.deepEqual(await page.eval(PRIVATE_LEFT), NOTHING_LEFT, 'image privée arrivée après la sortie');
  assert.deepEqual(await page.leaks(markers), [], 'données privées restées');
  page.assertNoErrors();
});

test('« Sortir » refusé par le Mac : le bouton Avant revient sur l\'image privée', async () => {
  await privateBefore('zm privee');
  await page.release();
  await page.privateIdle();
  const lock = await page.holdRequests(['*/api/private/lock'], () => true);   // réponse du Mac retenue
  await page.eval(`void privLock()`);
  assert.equal(await page.eval(`$('vBefore').hidden`), true, 'masqué pendant « Sortir »');
  // même un appui qui arriverait au cadre ne demande pas l'image d'entrée privée (preload l'ajouterait à secretLoads)
  assert.deepEqual(await page.eval(`(holdBefore($('vBefore')), { on: $('vBefore').classList.contains('on'),
    loads: secretLoads.size, want: $('vBeforeImg').want ?? null })`), { on: false, loads: 0, want: null },
  'image d\'entrée privée demandée pendant « Sortir »');
  await waitUntil(() => lock.held.length > 0, { what: 'verrouillage demandé' });
  for (const { requestId } of lock.take()) await page.send('Fetch.fulfillRequest', { requestId, responseCode: 500,
    responseHeaders: [{ name: 'Content-Type', value: 'application/json' }], body: btoa('{}') });
  await lock.release();
  await page.waitFor(`!leavingPrivate && inPrivate()`, { what: 'sortie refusée, toujours dans l\'espace' });
  await page.waitFor(`!$('vBefore').hidden && !document.querySelector('#pile .bfr').hidden`,
    { what: 'bouton Avant revenu (visionneuse et carte)' });
  await page.hold(BUTTON);
  await beforeOn('#vBefore', 'image avant privée de nouveau');
  await page.release();
  await page.closeViewer();
  await page.privateIdle();
  await page.eval(`privLock()`);
  await page.waitFor(`!inPrivate()`, { what: 'sorti' });
  // (le refus voulu du Mac est la seule erreur de la console)
  assert.deepEqual(page.errors.filter(e => !/status of 500/.test(e)), []);
  page.errors.length = 0;
});
