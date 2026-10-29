"""tests/rules.py : chaque règle mécanique de CODING_STANDARDS.md refuse son exemple fautif et laisse passer la forme
correcte et les lignes de la base ; la carte du code ne cite que des noms du code ; --map imprime l'index des
fonctions."""
import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check, rules  # noqa: E401, E402


H = "HOLD" + "="                                      # écrit ainsi pour que ce fichier ne prenne aucun nom HOLD


def lines(*text):
    return list(text)


class IdShadowTest(unittest.TestCase):
    HTML = "\n".join(['<button id="lamp"></button><div id="log"></div>',
                      "<script>",
                      "let lamp = false;",                   # 3 : refusée (le bug du 15/10/2026)
                      "let lampOn = false, x = 1;",          # permise
                      "function log(t){ }",                  # 5 : refusée
                      "const logs = [];",                    # permise
                      "</script>"])

    def test_a_variable_named_like_an_element_id_is_refused(self):
        self.assertEqual([k for k, _ in rules.id_shadows(self.HTML)], [3, 5])
        self.assertEqual(rules.id_shadows(self.HTML, {4, 6}), [])   # lignes de la base : laissées


class EveryAllTest(unittest.TestCase):
    def test_every_needs_a_length_check(self):
        src = lines("assert.ok(excerpts.every(p => p.length < 9));",                       # 1 : refusée
                    "assert.ok(excerpts.length > 0 && excerpts.every(p => p.length < 9));",
                    "await page.waitFor(`histItems.length === 2",
                    "  && histItems.every(it => !it.private)`);",                         # longueur à la ligne d'avant
                    "assert.ok(['outputs', 'jobs'].every(d => ok(d)));",                  # littéral : jamais vide
                    "assert.ok([...rows].every(r => r.ok));",                              # 6 : refusée
                    "assert.ok([$('a'), $('b')].filter(Boolean).every(e => e.hidden));")  # 7 : filtré, peut être vide
        self.assertEqual([k for k, _ in rules.unchecked_every(src)], [1, 6, 7])
        self.assertEqual(rules.unchecked_every(src, {2, 3, 4, 5}), [])

    def test_all_needs_a_length_check(self):
        src = lines("self.assertTrue(all(j['private'] for j in jobs))",                   # 1 : refusée
                    "self.assertTrue(jobs and all(j['private'] for j in jobs))",
                    "self.assertGreater(len(seeds), 0)",
                    "self.assertTrue(all(s >= 0 for s in seeds))",                         # longueur à la ligne d'avant
                    "wait_until(lambda: all(code(j) == 404 for j in (done, failed)))",     # tuple littéral
                    "self.assertTrue(all(x for x in journal() if x))")                     # 6 : refusée
        self.assertEqual([k for k, _ in rules.unchecked_all(src)], [1, 6])


class ThenTest(unittest.TestCase):
    def test_a_promise_is_not_a_boolean(self):
        src = lines("const ok = () => page.eval('x').then(v => v === 1) && ready;",       # 1 : refusée
                    "const busy = fetch(u).then(r => r.json()).then(s => s.busy && !s.q) || x;",   # 2 : refusée
                    "await page.waitFor(`fetch(u).then(r => r.json()).then(s => !s.busy && !s.q)`);",
                    "const ok = (await page.eval('x').then(v => v === 1)) && ready;")
        self.assertEqual([k for k, _ in rules.unawaited_then(src)], [1, 2])


class HoldTest(unittest.TestCase):
    def test_a_hold_name_is_not_reused_across_files(self):
        texts = {"tests/a.test.mjs": f"launch('{H}lot x');\nlaunch('{H}seul y');",
                 "tests/test_b.py": f"generate('{H}lot z')\ngenerate('{H}autre')"}
        added = {"tests/a.test.mjs": {1, 2}, "tests/test_b.py": {1, 2}}
        self.assertEqual([(f, k) for f, k, _ in rules.hold_reuse(texts, added)],
                         [("tests/a.test.mjs", 1), ("tests/test_b.py", 1)])
        self.assertEqual(rules.hold_reuse(texts, {"tests/a.test.mjs": {2}, "tests/test_b.py": set()}), [])

    def test_the_tests_do_not_reuse_a_hold_name(self):
        texts = {}
        for f in check.checked_files("tests/test_*.py", "tests/ui/*.test.mjs"):
            with open(os.path.join(check.ROOT, f), encoding="utf-8") as fh:
                texts[f] = fh.read()
        self.assertGreater(len(texts), 10)
        self.assertEqual(rules.hold_reuse(texts, {f: None for f in texts}), [])


class RunningTest(unittest.TestCase):
    SRC = "\n".join([
        "def test_a(self):",
        "    jid = generate('a red car')['id']",
        "    wait_job(jid, ('running',))",                       # 3 : refusée (finit peut-être avant)
        "def test_b(self):",
        "    jid = generate('SLOW=0.1 lent')['id']",
        "    wait_job(jid, ('running',))",
        "def test_c(self):",
        "    jobs = generate_lot(steps=30)['jobs']",
        "    wait_job(jobs[0]['id'], ('running',))",              # 9 : refusée (prompt par défaut)
        "def test_d(self):",
        f"    p = '{H}d retenue'",
        "    a = generate(p)['id']",
        "    wait_job(a, ('running',))",
        "def test_e(self, jid):",
        "    wait_job(jid, ('running',))",                        # identifiant reçu : laissé
        "def test_f(self):",
        "    code, reply = call('POST', '/api/generate', {'prompt': 'vite', 'steps': 2})",
        "    wait_job(reply['id'], until=('running',))",          # 18 : refusée
        "def test_g(self):",
        "    jid = generate('vite')['id']",
        "    wait_job(jid, ('running', 'done'))",
        "def test_h(self):",
        "    p = 'HOLD=x'",
        "    jid = generate(f'{p} chat')['id']",
        "    wait_job(jid, ('running',))",                        # HOLD par la valeur interpolée : laissé
    ])

    def test_waiting_for_running_needs_hold_or_slow(self):
        self.assertEqual([k for k, _ in rules.running_without_hold(self.SRC)], [3, 9, 18])
        self.assertEqual(rules.running_without_hold(self.SRC, {6, 13}), [])


class MapTest(unittest.TestCase):
    def test_an_invented_name_in_the_map_fails(self):
        code = "def worker():\n    pass\nconst MAX_DONE = 12;\nfunction showImage(el, src) {}"
        text = ("- `worker()` lit la file, `MAX_DONE`, `showImage(img, url)`, `S.turn`, fichier `driver.mjs` ;\n"
                "- `inventee()` et `PAS_LA` n'existent pas.")
        self.assertEqual([why.split(" : ")[0] for _, why in rules.missing_map_names(text, code + "\nturn")],
                         ["« inventee() »", "« PAS_LA »"])

    def test_the_code_map_only_names_code(self):
        code = "\n".join(check.read(f) for f in check.checked_files("*.py", "*.html", "*.mjs", "*.js"))
        names = rules.map_names(check.read("docs/agents/carte-du-code.md"))
        self.assertGreater(len(names), 100)
        self.assertEqual(rules.missing_map_names(check.read("docs/agents/carte-du-code.md"), code), [])

    def test_map_option_prints_the_index(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "check.py"), "--map", "worker"], capture_output=True,
                           text=True, env=dict(os.environ, QWEN_CHECK_REEXEC="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?m)^tools/launch\.py:\d+ worker$")
        index = rules.code_index("tools/ui/index.html", check.read("tools/ui/index.html"))
        self.assertIn("showImage", [name for _, name in index])

    def test_show_finds_every_name_of_a_declaration_and_the_driver_helpers(self):
        """--show trouve le second nom d'un « const a = …, b = … » (privThumb) et les aides du pilote et du banc."""
        src = "const a = x => f(x, 1), b = (y) => { return y; }, c = [1, 2];\nconst d = 1;\n"
        self.assertEqual([n for _, n in rules.code_index("x.html", src)], ["a", "b", "c", "d"])
        self.assertEqual(rules.function_spans("x.html", src, "b"), [(1, 1)])
        mjs = "export const TOP = `x`;\nexport async function waitUntil(c) {\n}\n  return {\n    async keepPile() {\n" \
              "      if (x) {\n      }\n    },\n  };\n"
        self.assertEqual([n for _, n in rules.code_index("d.mjs", mjs)], ["TOP", "waitUntil", "keepPile"])
        self.assertEqual(rules.function_spans("d.mjs", mjs, "keepPile"), [(5, 8)])
        # paramètres déstructurés, sur plusieurs lignes, défaut en gabarit : le corps, pas la seule signature
        params = "    async sort(a, { b = 1 } = {}) {\n      x();\n    },\nfunction f(x, {y}={},\n  z = `x ${y}`) {\n" \
                 "  return 1;\n}\nconst g = (u, { v } = {}) => {\n  w();\n};\n"
        self.assertEqual(rules.function_spans("d.mjs", params, "sort"), [(1, 3)])
        self.assertEqual(rules.function_spans("d.mjs", params, "f"), [(4, 7)])
        self.assertEqual(rules.function_spans("d.mjs", params, "g"), [(8, 10)])
        for name, where in (("privThumb", "tools/ui/index.html"), ("keepPile", "tests/ui/driver.mjs"),
                            ("wait_job", "tests/bench.py")):
            r = subprocess.run([sys.executable, os.path.join(HERE, "check.py"), "--show", name], capture_output=True,
                               text=True, env=dict(os.environ, QWEN_CHECK_REEXEC="1"))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(r.stdout.startswith(where + ":"), r.stdout[:200])


class InterfaceRulesTest(unittest.TestCase):
    """Règles de tools/ui/index.html : couleurs hors des jetons, @keyframes sans animation, adresse privée posée hors
    de showImage et preload."""
    def test_a_colour_is_written_in_the_tokens_only(self):
        html = lines(":root { --void:#0d0a08; --line:rgba(241,230,210,.13);",       # jetons : permis
                     "  .x { color:#ffa53a; }",                                       # 2 : refusée
                     "  .y { box-shadow:0 0 4px rgba(0,0,0,.5); }",                  # 3 : refusée
                     "  x.fillStyle=`rgba(${r},${g},${b},.18)`;",                    # tirée des jetons : permise
                     '<meta name="theme-color" content="#0d0a08">',                   # métadonnée : permise
                     "  .m { mask:linear-gradient(90deg, #000 85%, transparent); }",  # masque (alpha) : permis
                     "  $('#add').click(); .z { color:var(--ink); }",                 # identifiant, jeton : permis
                     "  .w { border:1px solid #fff }",                                # 8 : refusée
                     "  el.style.color = '#fff';",                                    # 9 : refusée (en JavaScript)
                     "  .bar #add{ color:var(--ink) }",                               # sélecteur d'id : permis
                     "  .k { box-shadow:0 0 2px #000; } /* sous un mask */")          # 11 : « mask » cité seulement
        self.assertEqual([k for k, _ in rules.hardcoded_colors(html)], [2, 3, 8, 9, 11])
        self.assertEqual(rules.hardcoded_colors(html, {1, 4}), [])

    def test_keyframes_need_an_animation_that_names_them(self):
        html = lines("@keyframes shake { 20% { transform:translateX(-8px) } }",   # employée
                     "@keyframes oubli { to { opacity:0 } }",                     # 2 : refusée
                     ".shake { animation:shake .4s; }",
                     "@keyframes pane-l { from { opacity:0 } }",
                     ".p { animation-name: pane-l; }",
                     "@keyframes spin { to { transform:rotate(1turn) } }",       # posée en JavaScript : permise
                     "el.style.animation = 'spin 1s linear';")
        self.assertEqual([k for k, _ in rules.unused_keyframes(html)], [2])

    def test_a_private_address_reaches_an_image_through_showImage(self):
        html = "\n".join(["<script>",
                          "function showImage(img, src){ img.src=src; }",                    # permise
                          "function preload(url){ const im=new Image(); im.src=url; }",       # permise
                          "function renderX(it){",
                          "  im.src=thumbOf(it);",                                            # 5 : refusée
                          "  g.innerHTML=`<img src=\"${privImage(it.id)}\">`;",               # 6 : refusée
                          "  showImage(im, srcOf(it));",                                      # permise
                          "  const u=privThumb(it.id); a.href=u; }",                          # pas une image
                          "function renderGallery(it){ im.src=thumbOf(it); }",                # exception connue
                          "</script>"])
        self.assertEqual([k for k, _ in rules.private_src(html)], [5, 6])


class TestFileRulesTest(unittest.TestCase):
    """Règles des tests d'interface : attente fixe, aide ou attente recopiée d'un fichier à l'autre, espace privé fermé
    sans attendre son repos, entrée privée écrite à la main ; « // règle levée : <raison> » lève une règle."""
    def test_a_fixed_wait_is_refused(self):
        src = lines("await new Promise(r => setTimeout(r, 300));",                      # 1 : refusée
                    "await elapse(5500);                    // délai voulu",
                    "await page.eval(`setTimeout(() => $('pileNo').click(), 250)`);",  # code de la page
                    "// règle levée : rejoue le minuteur de 700 ms de la page",
                    "await new Promise(r => setTimeout(r, 700));",
                    "await new Promise(resolve => setTimeout(() => resolve(), 200));",   # 6 : refusée
                    "await new Promise(go => { setTimeout(go, 150); });")                # 7 : refusée
        self.assertEqual([k for k, _ in rules.fixed_waits(src)], [1, 6, 7])

    def test_a_helper_or_a_wait_copied_into_a_second_file_is_refused(self):
        texts = {"tests/ui/a.test.mjs": "\n".join([
                     "async function fresh() {", "}",
                     "const post = (url, body) => page.eval(`postJson(${url})`);",
                     "const CODE = 'code-1';",
                     "await page.waitFor(`$('viewer').classList.contains('on')`);",
                     "await page.waitFor(`inPrivate()`);"]),
                 "tests/ui/b.test.mjs": "\n".join([
                     "async function fresh(pane) {",                                   # 1 : refusée
                     "const post = url => page.eval(url);",                            # 2 : refusée
                     "const CODE = 'code-2';",                                         # constante : permise
                     "await page.waitFor(`$('viewer').classList.contains('on')`, { what: 'x' });",   # 4 : refusée
                     "await page.waitFor(`inPrivate()`);"])}                           # courte : permise
        added = {"tests/ui/a.test.mjs": set(), "tests/ui/b.test.mjs": None}
        self.assertEqual([(f, k) for f, k, _ in rules.copied_helpers(texts, added) + rules.copied_waits(texts, added)],
                         [("tests/ui/b.test.mjs", 1), ("tests/ui/b.test.mjs", 2), ("tests/ui/b.test.mjs", 4)])

    def test_closing_the_private_space_waits_for_it_to_settle(self):
        src = lines("test('a', async () => {",
                    "  await page.enterPrivate(CODE);",
                    "  await page.generate('x');",
                    "  assert.equal(await post('/api/private/lock'), 200);",                # 4 : refusée
                    "  await page.privateIdle();",
                    "  assert.equal(await post('/api/private/lock'), 200);",                # au repos : permise
                    "  await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide'))`);",   # 7 : refusée
                    "  const h = await page.holdRequests(['*/api/private/lock'], () => true);",   # retenue : permise
                    "  // règle levée : la fermeture pendant une lecture privée est le sujet du test",
                    "  await page.eval(`dispatchEvent(new PageTransitionEvent('pagehide'))`);",
                    "});")
        self.assertEqual([k for k, _ in rules.unsettled_private_close(src)], [4, 7])

    def test_entering_the_private_space_goes_through_the_driver(self):
        src = lines("assert.equal(await post('/api/private/create', { code: CODE }), 200);",   # 1 : refusée
                    "await page.eval(`postJson('/api/private/unlock', { code: 'x' })`);",       # 2 : refusée
                    "await page.enterPrivate(CODE);",
                    "const h = await page.holdRequests(['*/api/private/unlock'], () => true);",
                    "assert.equal(await privatePost('/api/private/unlock'), 200);",              # 5 : refusée
                    "await fetch(`${bench.url}/api/private/create`, { method: 'POST' });",       # 6 : refusée
                    "await page.waitFor(`zqCalls.includes('/api/private/unlock')`);")             # lecture : permise
        self.assertEqual([k for k, _ in rules.private_entry_by_hand(src)], [1, 2, 5, 6])

    def test_a_sort_goes_through_the_driver(self):
        src = lines("await page.click('#pileYes');",                                     # 1 : refusée
                    "await page.eval(`$('pileNo').click(); $('pileNo').click()`);",      # 2 : refusée
                    "await page.click('#vSort .btn.secondary');",                        # 3 : refusée
                    "await page.eval(`sortFromViewer('discard')`);",                    # 4 : refusée
                    "await page.press('ArrowLeft');",                                     # 5 : refusée
                    "await page.waitFor(`!sortBusy() && !sortHeld`);",                   # 6 : refusée
                    "assert.equal(await page.eval(`topHeld`), true);",                    # 7 : refusée
                    "await page.sort('discard', { by: 'key', ready: false });",
                    "await page.eval(`${PRESS.discard}; ${VIEWER_PRESS.keep}`);",
                    "await page.waitFor(`${SORT_IDLE} && ${VIEWER_SEEN}`);",
                    "assert.equal((await page.sortState()).topHeld, true);",
                    "await page.eval(`$('pileNo').focus()`);",                            # focus : permis
                    "// ✕ puis sortHeld levé : un commentaire n'est pas un tri",
                    "await page.keyDown(ARROWS.discard, { repeat: true });",
                    "await page.press('ArrowLeft');   // règle levée : touches du pilote lui-même")
        found = rules.raw_sorts(src)
        self.assertEqual([k for k, _ in found], [1, 2, 3, 4, 5, 6, 7])
        other = lines("await page.tryClick('#pileNo');",                                     # 1
                      "await page.eval(`document.querySelector('#vSort .btn').click()`);",  # 2
                      "await page.eval(`document.getElementById('pileYes').click()`);",     # 3
                      "await page.press(`ArrowLeft`);",                                      # 4
                      "await page.eval(`dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))`);",  # 5
                      "$('pileNo').click(); await new Promise(r => setTimeout(r, 300));   // règle levée : envol",  # 6
                      "assert.deepEqual(await page.sortState(), { flying: false, topHeld: false });",
                      "const { topHeld } = await page.sortState();",
                      "for (const sel of ['#pileYes', '#pileNo']) await page.click(sel);")   # 9 : par une variable
        self.assertEqual([k for k, _ in rules.raw_sorts(other)], [1, 2, 3, 4, 5, 6, 9],
                         "toutes les écritures d'un tri ; une levée d'une autre règle ne vaut pas pour le tri")
        self.assertIn("page.sort(action", found[0][1])
        self.assertIn("page.stepViewer", found[4][1])
        self.assertIn("SORT_IDLE", found[5][1])

    def test_a_page_opened_by_a_test_is_closed_in_a_finally_with_await(self):
        src = lines("before(async () => {",
                    "  page = await chrome.phonePage();",                                 # before : permise
                    "});",
                    "test('a', async () => {",
                    "  const other = await chrome.phonePage();",                          # 5 : refusée
                    "  await other.goto(url);",
                    "  await other.close();",
                    "});",
                    "test('b', async () => {",
                    "  const pc = await chrome.newPage(PC);",
                    "  try {",
                    "    await pc.goto(url);",
                    "  } finally {",
                    "    pc.close();",                                                    # 14 : sans await
                    "  }",
                    "});",
                    "async function second() {",
                    "  const p = await alone.phonePage();",                               # rendue : permise
                    "  return p;",
                    "}",
                    "test('c', async () => {",
                    "  const p = await alone.phonePage();",
                    "  try { await p.goto(url); } finally { await alone.close(); }",       # son Chrome fermé
                    "});")
        self.assertEqual([k for k, _ in rules.unclosed_pages(src)], [5])
        self.assertEqual([k for k, _ in rules.unawaited_close(src)], [14])
        late = lines("test('d', async () => {",
                     "  const p = await chrome.phonePage();",                                 # 2 : fermée après
                     "  try { await x(); } finally { await y(); }",
                     "  await waitUntil(async () => { return p.eval('1'); });",
                     "  await p.close();",
                     "});")
        self.assertEqual([k for k, _ in rules.unclosed_pages(late)], [2],
                         "fermée après le finally, pas dedans ; « return p.eval » ne rend pas la page")

    def test_a_driver_helper_is_not_redefined_in_a_test_file(self):
        names = rules.driver_names("\n".join([
            "export const TOP = `x`;", "export async function waitUntil(cond) {", "}",
            "  return {", "    async inPile(prompt) { return 1; },", "    if (x) {", "  };"]))
        self.assertEqual(names, {"TOP", "waitUntil", "inPile"})
        src = lines("const TOP = `y`;",                                                   # 1 : refusée
                    "async function inPile(p) {", "}",                                    # 2 : refusée
                    "const cards = () => 1;",
                    "  const TOP = 2;")                                                   # pas de premier niveau
        self.assertEqual([k for k, _ in rules.driver_redefined(src, names)], [1, 2])

    def test_a_prompt_prefix_belongs_to_one_test(self):
        src = lines("test('a', async () => {",
                    "  await page.made('zp1 premier');",
                    "});",
                    "test('b', async () => {",
                    "  await page.made('zp2 autre');",
                    "});",
                    "test('c', async () => {",
                    "  await page.made('zp1 repris');",                                    # 8 : refusée
                    "  await page.generate('HOLD=zp2 zp2 encore');",                     # suite de b : permise
                    "});",
                    "test('d', async () => {",
                    "  await page.made('zp1 suite');",                                     # suite de c : permise
                    "  assert.ok(await bench.kept('zp2 autre'));",                        # lecture : permise
                    "});")
        self.assertEqual([k for k, _ in rules.prefix_reuse(src)], [8])
        forms = lines("test('a', async () => {",
                      "  await page.launch('SLOW=1 zqC4 un pont');",
                      "  await page.postGenerate(`{ prompt: 'zqE4file' }`);",
                      "});",
                      "test('b', async () => {", "});",
                      "test.skip('c', async () => {",
                      "  await page.made('zqC4 repris');",                                    # 8 : refusée
                      "  await postAs(`{ prompt: 'zqE4autre' }`);",                           # 9 : refusée
                      "  await page.made('zen jardin');",                                     # pas un préfixe
                      "});")
        self.assertEqual([k for k, _ in rules.prefix_reuse(forms)], [8, 9])


class ServerRulesTest(unittest.TestCase):
    """Règles statiques du serveur et des tests Python, lancées avant le banc."""
    def test_no_print_depends_on_secret(self):
        src = "\n".join(["def a(job):",
                         "    if secret(job):",
                         "        print('privée')",                              # 3 : refusée
                         "    print('fin', 'p' if secret(job) else 'q')",       # 4 : refusée
                         "    print(DONE_LINE)",
                         "    open(os.devnull if secret(job) else f)"])
        self.assertEqual([k for k, _ in rules.secret_prints(src)], [3, 4])

    def test_every_route_is_in_the_docstring(self):
        src = '\n'.join(['"""API : POST /api/generate, GET /api/private/image|thumb?id=<id>."""',
                         'def do_GET(path):',
                         '    if path == "/api/generate": pass',
                         '    if path in ("/api/private/image", "/api/private/thumb"): pass',
                         '    if path == "/api/oubliee": pass',                       # 5 : refusée
                         '    if path.startswith("/api/job/"): pass'])               # préfixe : laissé
        self.assertEqual(rules.undocumented_routes(src), [(5, "route /api/oubliee absente de la docstring")])

    def test_a_private_write_under_the_lock_finishes_a_rekey_first(self):
        src = "\n".join(["def keep():",
                         "    with PRIVATE_LOCK:",
                         "        finish_rekey()",
                         "        write(x)",
                         "def forget():",
                         "    with PRIVATE_LOCK:",                                  # 7 : refusée
                         "        remove_private_item(x)",
                         "def count():",
                         "    with PRIVATE_LOCK:",                                  # aucun appel : permise
                         "        S.rev += 1",
                         "def reset():",
                         "    with PRIVATE_LOCK:",                                  # tout l'espace : permise
                         "        shutil.rmtree(PRIVATE)"])
        self.assertEqual([k for k, _ in rules.private_lock_without_rekey(src)], [6])

    def test_an_internal_import_names_something_that_exists(self):
        sources = {"tools/launch.py": "import estimate\nX = 1\ndef worker():\n    estimate.fit()\n",
                   "tools/estimate.py": "def fit():\n    pass\n",
                   "tests/bench.py": "import launch\ndef call():\n    pass\nlaunch.ROOT = 'x'\n"
                                     "print(launch.X, launch.Y)\n",
                   "tests/test_a.py": "from bench import call, appel\nimport bench\nbench.__file__\n"}  # 1 : appel
        self.assertEqual(rules.broken_imports(sources),
                         [("tests/bench.py", 5, "launch.Y introuvable dans tools/launch.py"),
                          ("tests/test_a.py", 1, "appel introuvable dans tests/bench.py")])

    def test_the_repository_follows_the_server_rules(self):
        src = check.read("tools/launch.py")
        self.assertEqual(rules.secret_prints(src), [])
        self.assertEqual(rules.undocumented_routes(src), [])
        self.assertEqual(rules.private_lock_without_rekey(src), [])
        sources = {f: check.read(f) for f in check.checked_files("tools/*.py", "tests/*.py", "*.py")}
        self.assertGreater(len(sources), 10)
        self.assertEqual(rules.broken_imports(sources), [])


if __name__ == "__main__":
    unittest.main()
