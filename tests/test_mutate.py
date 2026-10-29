"""tests/mutate.py : la preuve rouge d'une garde sans script jetable. La mutation est appliquée le temps de la commande,
puis le fichier est toujours rendu tel quel : commande en échec, commande réussie (la mutation n'est pas vue),
commande interrompue (SIGTERM, SIGINT) ; un texte introuvable ou ambigu ne lance rien."""
import json, os, signal, subprocess, sys, tempfile, time, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
MUTATE = os.path.join(HERE, "mutate.py")
ORIGINAL = "def garde(x):\n    if x is None:\n        return False\n    return True\n"


class MutateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qwen-mutate-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "garde.py")
        # le journal des preuves du test, pas celui du dossier de travail (l'avis « zone sensible » le lit)
        p = mock.patch.dict(os.environ, QWEN_MUTATE_JOURNAL=os.path.join(self.tmp.name, "preuves.jsonl"))
        p.start()
        self.addCleanup(p.stop)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(ORIGINAL)

    def text(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def mutate(self, *command, old="if x is None:", new="if False:"):
        return subprocess.run([sys.executable, MUTATE, self.path, "--old", old, "--new", new, "--", *command],
                              capture_output=True, text=True, timeout=60)

    def check_guard(self):
        """Commande qui échoue quand la garde manque : elle lit le fichier tel qu'il est pendant la mutation."""
        return [sys.executable, "-c", f"import sys; sys.exit('if x is None' not in open({self.path!r}).read())"]

    def test_a_guard_proved_red_then_the_file_is_restored(self):
        r = self.mutate(*self.check_guard())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("la commande échoue avec la mutation", r.stdout)
        self.assertEqual(self.text(), ORIGINAL)

    def test_a_mutation_the_command_does_not_see_is_reported(self):
        r = self.mutate(sys.executable, "-c", "pass")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("la commande passe malgré la mutation", r.stdout)
        self.assertEqual(self.text(), ORIGINAL)

    @unittest.skipIf(os.name == "nt", "SIGINT et SIGTERM envoyés à un processus : POSIX seulement")
    def test_an_interrupted_command_still_restores_the_file(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=sig.name):
                started = os.path.join(self.tmp.name, "lancee")
                proc = subprocess.Popen([sys.executable, MUTATE, self.path, "--old", "return True", "--new",
                                         "return 1", "--", sys.executable, "-c",
                                         f"import time; open({started!r}, 'w').close(); time.sleep(60)"],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                end = time.time() + 30
                while not os.path.exists(started) and time.time() < end:
                    time.sleep(0.05)
                self.assertIn("return 1", self.text(), "mutation appliquée pendant la commande")
                proc.send_signal(sig)
                out, err = proc.communicate(timeout=30)
                self.assertNotEqual(proc.returncode, 0, out + err)
                self.assertIn("interrompue", out + err)
                self.assertEqual(self.text(), ORIGINAL)
                os.remove(started)

    def test_several_pairs_the_failing_test_and_the_proof_journal(self):
        """Plusieurs paires --old/--new d'un coup ; la sortie nomme le test en échec et le premier message de son
        assertion (unittest, node --test) ; la preuve va au journal, avec la fonction de chaque texte muté."""
        journal = os.path.join(self.tmp.name, "preuves.jsonl")
        report = os.path.join(self.tmp.name, "sortie.txt")
        with open(report, "w", encoding="utf-8") as f:
            f.write("FAIL: test_garde (test_x.GardeTest.test_garde)\n" + "-" * 70 + "\nTraceback (most recent call "
                    "last):\n  File \"t.py\", line 3\nAssertionError: False is not true : la garde laisse passer\n\n"
                    + "-" * 70 + "\nRan 1 test in 0.001s\n\nFAILED (failures=1)\n"
                    "✖ failing tests:\n\ntest at x.test.mjs:4:1\n✖ rien ne part pendant « Sortir » (12.5ms)\n"
                    "  AssertionError [ERR_ASSERTION]: requête privée partie\n")
        both = f"import sys; t = open({self.path!r}).read(); print(open({report!r}).read()); " \
               "sys.exit(0 if 'if x is None' in t and 'return True' in t else 1)"
        r = subprocess.run([sys.executable, MUTATE, self.path, "--old", "if x is None:", "--new", "if False:",
                            "--old", "return True", "--new", "return 1", "--", sys.executable, "-c", both],
                           capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, QWEN_MUTATE_JOURNAL=journal))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.text(), ORIGINAL)
        self.assertIn("mutate : en échec : test_x.GardeTest.test_garde : AssertionError: False is not true : la garde "
                      "laisse passer", r.stdout)
        self.assertIn("mutate : en échec : rien ne part pendant « Sortir » : AssertionError [ERR_ASSERTION]: requête "
                      "privée partie", r.stdout)
        with open(journal, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        self.assertEqual([row["fonction"] for row in rows], ["garde", "garde"])
        self.assertEqual(rows[0]["tests"], ["test_x.GardeTest.test_garde", "rien ne part pendant « Sortir »"])
        r = subprocess.run([sys.executable, MUTATE, self.path, "--old", "a", "--old", "b", "--new", "c", "--",
                            sys.executable, "-c", "pass"], capture_output=True, text=True, timeout=60)   # incomplètes
        self.assertEqual(r.returncode, 2)
        self.assertIn("2 --old pour 1 --new", r.stderr)

    def test_a_missing_or_ambiguous_text_runs_nothing(self):
        flag = os.path.join(self.tmp.name, "lancee")
        command = [sys.executable, "-c", f"open({flag!r}, 'w').close()"]
        for old, why in (("introuvable", "absent"), ("return", "2 fois")):
            with self.subTest(old=old):
                r = self.mutate(*command, old=old)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn(why, r.stderr)
                self.assertFalse(os.path.exists(flag), "commande lancée")
                self.assertEqual(self.text(), ORIGINAL)


if __name__ == "__main__":
    unittest.main()
