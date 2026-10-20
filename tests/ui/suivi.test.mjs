// Suivi d'une génération privée qui devient « inconnue » (404), dans la vue du téléphone : deux pages du même
// navigateur suivent la même génération (oubliée par celle qui l'a lancée), ou l'espace se ferme avant que la page le
// sache ; la génération quitte la page sans faux message « Échec : génération introuvable ».
//   node --test tests/ui/suivi.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/suivi.test.mjs)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, first, second;

before(async () => {
  bench = await startBench();
  chrome = await launchChrome();
  first = await chrome.phonePage();
  second = await chrome.phonePage();               // même profil : même cookie, donc même session de l'espace privé
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

const CODE = 'code-du-banc-1';
const post = (page, url, body = {}) =>
  page.eval(`postJson(${JSON.stringify(url)}, ${JSON.stringify(body)}).then(r => r.status)`);
// toasts affichés depuis l'appel (comme saisie.test.mjs)
const watchToasts = page => page.eval(`(() => { window.seenToasts = []; window.toastWatch?.disconnect();
  window.toastWatch = new MutationObserver(() => seenToasts.push($('toast').textContent));
  toastWatch.observe($('toast'), { childList: true, characterData: true, subtree: true }); })()`);
const failures = async page => (await page.eval(`seenToasts`)).filter(t => t.startsWith('Échec'));
// la console note le 404 du suivi comme une ressource en échec : c'est la réponse attendue, pas une erreur de la page
const assertNoOtherErrors = page => assert.deepEqual(page.errors.filter(e => !/status of 404/.test(e)), []);
const idle = page => page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy)`,
  { what: 'Mac au repos', timeout: 30000 });

async function open(page) {
  await page.goto(bench.url + '/');
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
}
async function enterPrivate(page) {
  const exists = await page.eval(`privState.exists`);
  assert.equal(await post(page, exists ? '/api/private/unlock' : '/api/private/create', { code: CODE }), 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
}
async function launch(page, prompt) {
  await page.eval(`(() => { const t = $('t2i_prompt'); t.value = ${JSON.stringify(prompt)};
    t.dispatchEvent(new Event('input')); })()`);
  await page.click('#go');
  await page.waitFor(`pageJobs.some(p => p.private && !p.adopted)`, { what: 'génération privée suivie par la page' });
  return page.eval(`pageJobs.find(p => p.private).id`);
}

test('deux pages : celle qui a repris la génération la voit oubliée par l\'autre, sans « Échec »', async () => {
  await open(first);
  await open(second);
  await enterPrivate(first);
  await second.eval(`refreshStatus()`);
  await second.waitFor(`inPrivate()`, { what: 'seconde page dans l\'espace privé (cookie partagé)' });
  await watchToasts(first);
  await watchToasts(second);
  const id = await launch(first, 'HOLD=deux zq7 un phare la nuit');
  await second.eval(`refreshStatus()`);
  await second.waitFor(`pageJobs.some(p => p.id === ${JSON.stringify(id)} && p.adopted)`,
    { what: 'génération reprise par la seconde page' });
  // la seconde page n'interroge plus le suivi tant que la première n'a pas fini et oublié la génération : elle
  // recevra le 404 de l'oubli (et non l'état « fini », qu'une interrogation plus rapide aurait pu voir)
  await second.eval(`(() => { window.heldFollow = true; const f = window.fetch;
    window.fetch = (u, ...a) => String(u).startsWith('/api/job/') && heldFollow
      ? new Promise(r => { const t = setInterval(() => {
        if (!heldFollow) { clearInterval(t); r(f(u, ...a)); } }, 50); })
      : f(u, ...a); })()`);
  bench.release('deux');
  await first.waitFor(`!pageJobs.some(p => p.private && p.j.status !== 'done') && $('doneList').children.length > 0`,
    { what: 'génération finie sur la première page', timeout: 30000 });
  await first.waitFor(`fetch('/api/job/${id}').then(r => r.status === 404)`, { what: 'génération oubliée par le Mac' });
  await second.eval(`heldFollow = false`);
  await second.waitFor(`!pageJobs.some(p => p.private)`, { what: 'génération quittée par la seconde page' });
  assert.deepEqual(await failures(second), [], 'pas de faux échec sur la page qui l\'avait reprise');
  assert.deepEqual(await failures(first), []);
  assert.equal(await second.eval(`inPrivate()`), true, 'la seconde page reste dans l\'espace privé');
  assertNoOtherErrors(first);
  assertNoOtherErrors(second);
  await idle(first);
});

test('espace fermé avant que /api/status le dise : le 404 du suivi ne donne pas « Échec »', async () => {
  await open(first);
  await enterPrivate(first);
  await watchToasts(first);
  await launch(first, 'HOLD=ferme zq7 une forêt sous la neige');
  // plus d'interrogation de /api/status : la page ne peut apprendre la fermeture que par le suivi
  await first.eval(`clearTimeout(statusTimer); window.refreshStatus = async () => {}`);
  assert.equal(await post(first, '/api/private/lock'), 200);  // session fermée, comme par le Mac après 15 minutes
  await first.waitFor(`!pageJobs.some(p => p.private)`, { what: 'génération privée quittée après le 404' });
  assert.equal(await first.eval(`privState.unlocked`), true, '/api/status n\'a pas encore dit l\'espace fermé');
  assert.deepEqual(await failures(first), []);
  assertNoOtherErrors(first);
  bench.release('ferme');                          // la génération continue sur le Mac et se range dans l'espace
  await idle(first);
});
