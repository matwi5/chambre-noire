// File d'attente du Labo, dans la vue du téléphone : la pastille « +N en attente » de la pile ouvre sa feuille, une
// carte par demande (un lot sur une carte, une case par image, réglages, heure « prête vers », « autre appareil »),
// cloisonnée par espace comme la carte en cours ; « Passer en tête » et l'annulation d'une carte ou d'une image d'un
// lot dépliée, les générations de la page restant reconnues.
//   venv/bin/python tests/check.py --quick --ui tests/ui/file.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome, waitUntil } from './driver.mjs';

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

const CODE = 'code-du-banc-1';
const post = (url, body = {}) => page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(async r => ({ status: r.status, body: await r.json() }))`);
async function enterPrivate() {
  const exists = await page.eval(`privState.exists`);
  assert.equal((await post(exists ? '/api/private/unlock' : '/api/private/create', { code: CODE })).status, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
// génération de la page annulée depuis la file du Labo
async function cancelOwnFromQueue() {
  await page.openQueue();
  await page.waitFor(`!!$('queueList').querySelector('.qcard.own [data-kind="cancel"]')`,
    { what: 'carte de la génération' });
  await page.click('#queueList .qcard.own [data-kind="cancel"]');
}
const cards = () => page.eval(`[...$('queueList').querySelectorAll('.qcard')].map(r => r.textContent)`);
const count = n => `$('queueList').querySelectorAll('.qcard').length === ${n}`;

test('espace privé : la file ne montre que les générations privées, avec leur prompt, derrière le travail caché', async () => {
  await enterPrivate();
  const pub = await page.launch('SLOW=1 zq9public en cours');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`,
    { what: 'génération publique en cours' });
  await page.launch('zq9secret d\'un autre appareil', { private: true });
  await page.generate('zq9secret de cette page');
  await page.waitFor(`pageJobs.some(p => p.private && isActive(p))`, { what: 'génération privée suivie par la page' });
  await page.eval(`refreshStatus()`);
  // carte en cours : rien de l'espace ne tourne : « En attente » ; pastille « +2 en attente »
  await page.waitFor(`!$('runCard').hidden && $('runStep').textContent === 'En attente'
    && $('queueChip').textContent === '+2 en attente'`, { what: 'carte en attente, pastille +2' });
  await page.openQueue();
  await page.waitFor(count(2), { what: 'file avec les deux générations privées' });
  const [other, mine] = await cards();
  assert.match(other, /zq9secret d'un autre appareil/);
  assert.match(mine, /zq9secret de cette page/);
  const all = (await cards()).join(' ');
  // rien de tel dans l'espace privé
  assert.doesNotMatch(all, /zq9public|Génération privée|· autre appareil/);
  // lot privé d'un autre appareil : une carte, annulée en entier depuis la file
  await page.launch('zq9secret lot', { private: true, count: 2 });
  await page.eval(`refreshStatus()`);
  const lotCancel = `#queueList [data-post^="/api/lot/"][data-kind="cancel"]`;
  await page.waitFor(`${count(3)} && !!document.querySelector('${lotCancel}')`, { what: 'carte du lot privé' });
  await page.click(lotCancel);
  await page.waitFor(count(2), { what: 'lot privé annulé' });
  // annulation d'une génération privée lancée par un autre appareil, depuis la file (la page la suit aussi : elle suit
  // toutes les générations privées actives)
  assert.equal(await page.eval(`$('queueList').querySelectorAll('.qcard [data-kind="cancel"]').length`), 2);
  await page.eval(`$('queueList').querySelector('.qcard [data-kind="cancel"]').click()`);
  await page.waitFor(count(1), { what: 'génération de l\'autre appareil annulée' });
  await page.click('#queueList .qcard [data-kind="cancel"]');
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération de cette page annulée' });
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy)`, { what: 'Mac au repos' });
  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

// ------------------------------------------------------------ sortie de l'espace privé et retour
const jobs = () => page.eval(`pageJobs.map(p => (p.private ? 'privée ' : 'publique ') + p.prompt)`);
const onScreen = () => page.eval(`({ shown: shown && (shown.private ? 'privée ' : 'publique ') + shown.prompt,
  card: !$('runCard').hidden, chip: !$('queueChip').hidden })`);
// PUB retenue (HOLD) jusqu'à la fin du test : SECRET reste en attente derrière elle, avec sa carte
const PUB = 'HOLD=sortie zq9public de la page', SECRET = 'SLOW=0.05 zq9secret de la page';

test('sortie : la génération privée quitte l\'écran et la page ; elle revient au retour, aussi après un rechargement', async () => {
  await bench.idle();
  await page.goto(bench.url + '/');
  await page.ready();
  await page.generate(PUB);                                   // génération publique de la page, en cours
  await page.waitFor(`pageJobs.some(p => !p.private && p.j.status === 'running')`,
    { what: 'génération publique en cours' });

  await enterPrivate();                            // elle quitte l'écran, reste suivie en mémoire
  assert.deepEqual(await onScreen(), { shown: null, card: false, chip: false });
  assert.deepEqual(await jobs(), ['publique ' + PUB]);
  await page.generate(SECRET);                                // génération privée, en attente derrière la publique
  await page.waitFor(`shown && shown.private`, { what: 'génération privée à l\'écran' });

  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');                   // « Sortir » : la privée quitte l'écran et la page, la publique revient
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.deepEqual(await jobs(), ['publique ' + PUB]);
  const out = await onScreen();
  assert.equal(out.shown, 'publique ' + PUB);
  assert.equal(out.card, true);
  assert.doesNotMatch(await page.eval(`document.body.innerText`), /zq9secret/);

  await enterPrivate();                            // retour : la page suit de nouveau la génération privée
  await page.waitFor(`pageJobs.some(p => p.private && isActive(p))`, { what: 'génération privée retrouvée' });
  assert.equal((await onScreen()).shown, 'privée ' + SECRET);

  await page.goto(bench.url + '/');                // rechargement dans l'espace privé
  await page.ready();
  if (!await page.eval(`inPrivate()`)) await enterPrivate();   // la fermeture de la page a pu verrouiller l'espace
  await page.waitFor(`pageJobs.some(p => p.private && isActive(p))`,
    { what: 'génération privée retrouvée après le rechargement' });
  assert.equal((await onScreen()).shown, 'privée ' + SECRET);

  await cancelOwnFromQueue();                      // en attente derrière la publique, cachée
  await page.waitFor(`!pageJobs.some(p => p.private && isActive(p))`, { what: 'génération privée annulée' });
  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  // de retour dans l'espace public, la page reprend la génération publique qu'elle avait lancée
  bench.release('sortie');
  await page.waitFor(`pageJobs.some(p => !p.private && p.prompt === ${JSON.stringify(PUB)})`,
    { what: 'génération publique reprise' });
  await bench.idle();
  page.assertNoErrors();
});

test('fermé par le Mac : la génération privée quitte l\'écran comme après « Sortir »', async () => {
  await bench.idle();
  await page.goto(bench.url + '/');
  await page.ready();
  const pub = await page.launch('SLOW=1 zq9public d\'un autre appareil');   // la privée attend derrière
  await enterPrivate();
  await page.generate(SECRET);
  await page.waitFor(`shown && shown.private`, { what: 'génération privée à l\'écran' });
  assert.equal((await post('/api/private/lock')).status, 200);   // session fermée sans « Sortir »
  await page.eval(`refreshStatus()`);
  await page.waitFor(`!inPrivate()`, { what: 'hors de l\'espace privé' });
  assert.deepEqual(await jobs(), []);
  // la génération publique d'un autre appareil tourne : la carte la montre, rien de la privée
  assert.deepEqual(await onScreen(), { shown: null, card: true, chip: false });
  assert.doesNotMatch(await page.eval(`document.body.innerText`), /zq9secret/);
  await enterPrivate();
  await page.waitFor(`pageJobs.some(p => p.private && isActive(p))`, { what: 'génération privée retrouvée' });
  await cancelOwnFromQueue();                      // en attente derrière la publique, cachée
  await page.waitFor(`!pageJobs.some(isActive)`, { what: 'génération privée annulée' });
  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  assert.equal((await post(`/api/job/${pub.id}/cancel`)).status, 200);
  // suivi interrompu par la fermeture : Chrome note les réponses « inconnu » d'un suivi déjà parti, seules erreurs admises
  assert.deepEqual(page.errors.filter(e => !/404 \(Not Found\)/.test(e)), []);
  page.errors.length = 0;
});

test('espace public : une génération privée en cours n\'a pas de carte et n\'est pas dans la file', async () => {
  await enterPrivate();
  const priv = await page.launch('SLOW=1 zq9secret en cours', { private: true });
  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`,
    { what: 'génération privée en cours' });
  await page.eval(`refreshStatus()`);
  assert.deepEqual(await page.eval(`[$('runCard').hidden, $('queueChip').hidden]`), [true, true],
    'ni carte en cours ni pastille');
  // une génération publique derrière elle : « En attente », sans ligne pour la privée
  await page.generate('zq9public derrière');
  await page.waitFor(`pageJobs.some(p => !p.private && isActive(p))`, { what: 'génération publique suivie' });
  await page.eval(`refreshStatus()`);
  await page.waitFor(`$('runStep').textContent === 'En attente' && $('runEta').textContent.startsWith('fin vers')`,
    { what: 'carte en attente' });
  await page.openQueue();
  await page.waitFor(count(1), { what: 'une seule carte' });
  const [card] = await cards();
  assert.match(card, /zq9public derrière/);
  assert.doesNotMatch(card, /zq9secret|· autre appareil/);
  assert.match(await page.eval(`$('queueNote').textContent`), /^1 en attente · file vide vers \d+ h \d\d \(≈ /);
  await page.click('#queueList .qcard.own [data-kind="cancel"]');
  await page.waitFor(`!pageJobs.some(p => !p.private && isActive(p))`, { what: 'génération publique annulée' });
  await enterPrivate();
  assert.equal((await post(`/api/job/${priv.id}/cancel`)).status, 200);
  await page.closeSheet();                         // le voile d'une feuille ouverte recouvre l'en-tête
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});

// ------------------------------------------------------------ cartes et « Passer en tête »
const firstPaths = () => page.eval(`[...$('queueList').querySelectorAll('.qcard')]
  .map(c => c.querySelector('[data-kind="first"]')?.dataset.post || '')`);

test('cartes : un lot de la page sur une carte avec ses cases, réglages, heure ; « autre appareil »', async () => {
  await bench.idle();
  await page.goto(bench.url + '/');
  await page.ready();
  const held = await page.launch('HOLD=cartes zq9 d\'un autre appareil');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération en cours' });
  const other = await page.launch('zq9 attend ailleurs', { width: 960, height: 640, steps: 12 });
  await page.eval(`opt.count = 3; opt.res = 'low'; opt.steps = 'low'; saveOpt(); refreshChoices()`);
  await page.generate('SLOW=0.4 zq9 trois essais');
  await page.eval(`opt.count = 1; saveOpt(); refreshChoices()`);
  await page.openQueue();
  // en cours (pas de carte), l'autre appareil, puis le lot de la page sur une seule carte
  await page.waitFor(`${count(2)} && $('queueList').querySelectorAll('.qcard.own .qcase').length === 3`,
    { what: 'deux cartes, trois cases' });
  const [away, mine] = await cards();
  assert.match(away, /zq9 attend ailleurs/);
  assert.match(away, /3:2 · 540p · 12 étapes/);
  assert.match(away, /prête vers \d+ h \d\d/);
  assert.match(away, /· autre appareil/);
  assert.match(mine, /zq9 trois essais/);
  assert.match(mine, /3 variantes · 1:1 · 360p · 8 étapes/);
  assert.doesNotMatch(mine, /· autre appareil/);
  assert.match(await page.eval(`$('queueNote').textContent`), /^4 en attente · file vide vers \d+ h \d\d \(≈ /);
  // carte dépliée : une ligne par image ; l'image 2 annulée seule, sa case le dit
  await page.click('#queueList .qcard.own [data-toggle]');
  await page.waitFor(`$('queueList').querySelectorAll('.qcard.own .qsub').length === 3`, { what: 'images du lot' });
  await page.eval(`$('queueList').querySelectorAll('.qcard.own .qsub')[1]
    .querySelector('[data-kind="cancel"]').click()`);
  await page.waitFor(`[...$('queueList').querySelectorAll('.qcard.own .qcase')].map(c => c.className).join()
    === 'qcase wait,qcase gone,qcase wait'`, { what: 'image 2 annulée' });
  // « Passer en tête » de la carte du lot : ses images passent devant l'autre appareil
  await page.click('#queueList .qcard.own [data-kind="first"]');
  await page.waitFor(`queueState.length === 4 && ownOf(queueState[1])?.prompt === 'SLOW=0.4 zq9 trois essais'`,
    { what: 'lot en tête' });
  await page.waitFor(`/zq9 trois essais/.test($('queueList').firstElementChild.textContent)`,
    { what: 'carte redessinée' });
  bench.release('cartes');
  // image 1 faite : sa case montre sa vignette, tant que le lot tourne encore
  await page.waitFor(`!!$('queueList').querySelector('.qcard.own .qcase.done img')`,
    { what: 'case faite avec sa vignette',
    timeout: 30000 });
  // le lot fini : sa carte quitte la file, ses deux images sont dans la pile
  await page.waitFor(`!$('queueList').querySelector('.qcard.own')
    && pileItems.filter(it => it.prompt === 'SLOW=0.4 zq9 trois essais').length === 2`,
    { what: 'lot terminé', timeout: 30000 });
  assert.equal((await post(`/api/job/${other.id}/cancel`)).status, 200);
  await bench.idle();
  assert.equal((await post(`/api/job/${held.id}/cancel`)).status, 200);   // déjà finie : rien ne change
  page.assertNoErrors();
});

test('« Passer en tête » : juste après la génération en cours, générations de la page reconnues', async () => {
  const held = await page.launch('HOLD=tete zq9 d\'un autre appareil');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération en cours' });
  for (const [k, text] of [[1, 'zq9 page un'], [2, 'zq9 page deux']]) {
    await page.generate(text);
    await page.waitFor(`pageJobs.filter(isActive).length === ${k}`, { what: `génération ${k} suivie` });
  }
  await page.openQueue();
  await page.waitFor(count(2), { what: 'deux cartes (la génération en cours est sur la carte en cours)' });
  // génération de la page derrière chaque entrée (état lu, pas l'écran), et chemin porté par chaque carte affichée
  const owners = () => page.eval(`queueState.map(e => ownOf(e) ? ownOf(e).prompt : e.id ? 'autre appareil' : '?')`);
  const idOf = word => page.eval(`pageJobs.find(p => p.prompt === 'zq9 page ${word}').id`);
  assert.deepEqual(await owners(), ['autre appareil', 'zq9 page un', 'zq9 page deux']);
  await page.eval(`$('queueList').querySelectorAll('.qcard')[1].querySelector('[data-kind="first"]').click()`);
  await page.waitFor(`queueState.length === 3 && ownOf(queueState[1])?.prompt === 'zq9 page deux'`,
    { what: 'file réordonnée' });
  assert.deepEqual(await owners(), ['autre appareil', 'zq9 page deux', 'zq9 page un']);
  const want = JSON.stringify([`/api/job/${await idOf('deux')}/first`, `/api/job/${await idOf('un')}/first`]);
  await waitUntil(async () => JSON.stringify(await firstPaths()) === want,
    { what: 'cartes redessinées dans le nouvel ordre' });
  for (const id of await page.eval(`pageJobs.filter(isActive).map(p => p.id)`)) {
    assert.equal((await post(`/api/job/${id}/cancel`)).status, 200);
  }
  assert.equal((await post(`/api/job/${held.id}/cancel`)).status, 200);
  bench.release('tete');
  await bench.idle();
  page.assertNoErrors();
});

test('« Passer en tête » d\'une image du lot d\'un autre appareil, carte dépliée ; puis tout le lot annulé',
  async () => {
    const held = await page.launch('HOLD=entete zq9 en cours');
    await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération en cours' });
    const other = await page.launch('zq9 avant le lot');
    const lot = await page.launch('zq9 lot', { count: 3 });
    await page.openQueue();
    await page.waitFor(count(2), { what: 'deux cartes : l\'autre génération et le lot' });
    const lotCard = `[...$('queueList').querySelectorAll('.qcard')].find(c => /zq9 lot/.test(c.textContent))`;
    assert.equal(await page.eval(`${lotCard}.querySelectorAll('.qcase.wait').length`), 3);
    await page.eval(`${lotCard}.querySelector('[data-toggle]').click()`);
    await page.waitFor(`${lotCard}.querySelectorAll('.qsub').length === 3`, { what: 'carte du lot dépliée' });
    await page.eval(`${lotCard}.querySelectorAll('.qsub')[2].querySelector('[data-kind="first"]').click()`);
    await page.waitFor(`queueState[1]?.id === ${JSON.stringify(lot.jobs[2].id)}`, { what: 'image 3 du lot en tête' });
    // la carte du lot passe devant (sa première entrée est maintenant juste après celle en cours), toujours une seule
    await page.waitFor(`${count(2)} && /zq9 lot/.test($('queueList').firstElementChild.textContent)`,
      { what: 'carte du lot en premier' });
    // bouton périmé : l'image 1 annulée ailleurs, son « Passer en tête » encore affiché répond 409, sans message ; la
    // file rafraîchie montre sa case « sortie » (issue inconnue pour cet appareil)
    await page.eval(`clearTimeout(statusTimer); $('toastBox').textContent = ''`);
    assert.equal((await post(`/api/job/${lot.jobs[0].id}/cancel`)).status, 200);
    const stale = `${lotCard}.querySelector('.qsub [data-post="/api/job/${lot.jobs[0].id}/first"]')`;
    assert.equal(await page.eval(`!!${stale}`), true, 'bouton encore affiché');
    await page.eval(`${stale}.click()`);
    await page.waitFor(`${lotCard}.querySelectorAll('.qsub').length === 2
      && ${lotCard}.querySelectorAll('.qcase.out').length === 1`,
      { what: 'file rafraîchie, image 1 sortie' });
    assert.equal(await page.eval(`$('toastBox').textContent`), '', 'aucun message');
    // Chrome note la réponse 409 comme une ressource en échec : seule erreur admise
    assert.deepEqual(page.errors.filter(e => !/409 \(Conflict\)/.test(e)), []);
    page.errors.length = 0;
    await page.eval(`${lotCard}.querySelector('[data-post^="/api/lot/"][data-kind="cancel"]').click()`);
    await page.waitFor(count(1), { what: 'lot annulé' });
    for (const id of [other.id, held.id]) assert.equal((await post(`/api/job/${id}/cancel`)).status, 200);
    bench.release('entete');
    await bench.idle();
    page.assertNoErrors();
  });

test('rien ne dépasse à 367 px : cartes, cases et lignes dépliées', async () => {
  const held = await page.launch('HOLD=largeur zq9 en cours');
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => s.busy)`, { what: 'génération en cours' });
  await page.launch('zq9 Portrait of an old fisherman mending his nets at dawn, golden light, 85 mm', { count: 4 });
  await page.launch('zq9 seule', { width: 1536, height: 2752 });
  await page.openQueue();
  await page.waitFor(count(2), { what: 'deux cartes' });
  await page.eval(`$('queueList').querySelector('[data-toggle]').click()`);
  await page.waitFor(`!!$('queueList').querySelector('.qsub')`, { what: 'lot déplié' });
  const out = await page.eval(`[...$('fileSheet').querySelectorAll('*')].filter(el => el.getClientRects().length)
    .filter(el => { const r = el.getBoundingClientRect(); return r.left < -.5 || r.right > innerWidth + .5; })
    .map(el => el.className || el.tagName)`);
  assert.deepEqual(out, []);
  if (process.env.SHOT_DIR) {                     // capture à regarder : la file à l'écran
    await page.screenshot(process.env.SHOT_DIR + '/cartes.png');
  }
  for (const id of await page.eval(`queueState.filter(e => e.id).map(e => e.id)`))
    await post(`/api/job/${id}/cancel`);
  bench.release('largeur');
  await bench.idle();
  assert.equal((await post(`/api/job/${held.id}/cancel`)).status, 200);
  page.assertNoErrors();
});
