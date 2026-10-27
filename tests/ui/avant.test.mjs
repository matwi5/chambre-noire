// Bouton Avant (spec du 27/10/2026, section 4) : sur une image issue d'une édition à une seule image d'entrée (ou
// d'un Dessin avec masque), le maintenir montre l'image d'entrée à la place de l'image produite, dans le même cadre,
// dans la visionneuse et sur la carte du dessus de la pile ; relâché, l'image produite revient.
//   venv/bin/python tests/check.py --no-bench --ui tests/ui/avant.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, PC, PHONE } from './driver.mjs';

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
    await page.hold(BUTTON, { mouse: true });
    await beforeOn('#vBefore', 'image avant sur l\'image zoomée');
    const r = await page.eval(`(() => { const a = $('vImg'), b = $('vBeforeImg'), box = e => (r => [r.left, r.top,
      r.width, r.height])(e.getBoundingClientRect());
      return { same: a.style.transform === b.style.transform, zoom: a.style.transform, a: box(a), b: box(b) }; })()`);
    await page.release();
    assert.match(r.zoom, /scale\(/, 'image zoomée');
    assert.equal(r.same, true, 'même transformation');
    assert.ok(within1(r.a, r.b), `même cadrage : ${r.b} au lieu de ${r.a}`);
    await page.closeViewer();
  } finally { await page.setView(PHONE); }
  page.assertNoErrors();
});
