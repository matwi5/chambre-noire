"""tests/mutate.py : la preuve rouge d'une garde sans script jetable. La mutation est appliquée le temps de la commande,
puis le fichier est toujours rendu tel quel : commande en échec, commande réussie (la mutation n'est pas vue),
commande interrompue (SIGTERM, SIGINT) ; un texte introuvable ou ambigu ne lance rien."""
import os, signal, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MUTATE = os.path.join(HERE, "mutate.py")
ORIGINAL = "def garde(x):\n    if x is None:\n        return False\n    return True\n"


class MutateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qwen-mutate-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "garde.py")
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
