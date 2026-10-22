// Test volontairement bloqué, lancé seulement par pilote.test.mjs (pas un *.test.mjs : jamais lancé par --ui seul) :
// il attend sans délai une promesse de la page jamais tenue, comme une confirmation qui attend sa réponse. Il doit
// échouer dans le délai par test de check.py, sans laisser Chrome ni le serveur du banc derrière lui.
import { test, after } from 'node:test';
import { startBench, launchChrome } from '../driver.mjs';

let bench, chrome;

after(async () => {
  await chrome?.close();
  await bench?.stop();
});

test('bloqué', async () => {
  bench = await startBench();
  chrome = await launchChrome();
  const page = await chrome.phonePage();
  console.log(`PIDS ${JSON.stringify([...bench.pids, chrome.pid])}`);
  await page.eval('new Promise(() => {})', { timeout: 10 * 60 * 1000 });
});
