// Interface servie comme au téléphone par Tailscale (tests/ui/relay.py : nom HTTPS de « tailscale serve », en-têtes
// de relais, code d'accès), dans la vue du téléphone : l'espace privé s'y ouvre, et l'aperçu d'une génération privée
// s'affiche toutes les 5 étapes.
//   node --test tests/ui/relais.test.mjs   (ou : venv/bin/python tests/check.py --ui tests/ui/relais.test.mjs)
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBench, launchChrome } from './driver.mjs';

let bench, chrome, page;

before(async () => {
  bench = await startBench({ relay: true });
  chrome = await launchChrome();
  page = await chrome.phonePage();
  await bench.login(page);
  await page.waitFor(`$('status').className === 'ok'`, { what: 'moteur prêt affiché' });
});

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

test('par l\'adresse HTTPS relayée : espace privé ouvert, aperçus d\'une génération privée affichés', async () => {
  const created = await page.eval(`postJson('/api/private/create', { code: 'code-du-relais-1' }).then(r => r.status)`);
  assert.equal(created, 200);
  await page.eval(`refreshStatus()`);
  await page.waitFor(`inPrivate()`, { what: 'dans l\'espace privé' });
  await page.eval(`$('previewChk').checked = true;
    (() => { const t = $('t2i_prompt'); t.value = 'SLOW=0.2 zq8 aperçu relayé';
      t.dispatchEvent(new Event('input')); })()`);
  await page.click('#go');
  await page.waitFor(`shown && shown.private && $('stageImg').classList.contains('preview')
    && $('stageImg').getAttribute('src').includes('/preview?v=') && $('stageImg').naturalWidth > 0`,
  { what: 'aperçu privé affiché', timeout: 30000 });
  await page.waitFor(`fetch('/api/status').then(r => r.json()).then(s => !s.busy && !s.queue.length)`,
    { what: 'génération finie', timeout: 30000 });
  await page.click('#privExit');
  await page.waitFor(`!inPrivate()`, { what: 'sorti de l\'espace privé' });
  page.assertNoErrors();
});
