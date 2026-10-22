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
    HTML = "\n".join(['<button id="incog"></button><div id="log"></div>',
                      "<script>",
                      "let incog = false;",                  # 3 : refusée (le bug du 15/10/2026)
                      "let incogOn = false, x = 1;",         # permise
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
                    "assert.ok([...rows].every(r => r.ok));")                              # 6 : refusée
        self.assertEqual([k for k, _ in rules.unchecked_every(src)], [1, 6])
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


if __name__ == "__main__":
    unittest.main()
