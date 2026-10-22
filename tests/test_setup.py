"""setup.py : une calibration qui échoue ne passe plus inaperçue. L'erreur de tools/calibrate.py est affichée, et
l'installation dit qu'elle continue sans calibration (une calibration cassée était passée inaperçue au groupe B du
parcours des pages, 10/2026).

  venv/bin/python -m unittest discover -s tests -p test_setup.py

Pas de vraie calibration : tools/calibrate.py est remplacé par un faux script dans un dossier temporaire.
"""
import contextlib, io, os, sys, tempfile, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import setup  # noqa: E402

# faux scripts muets sur la sortie standard (celle de setup.py, pas capturée par le test)
BROKEN = "raise RuntimeError('moteur introuvable (essai)')\n"
WORKING = "pass\n"


class CalibrationTest(unittest.TestCase):
    def calibrate(self, script):
        """step_calibrate avec ce faux tools/calibrate.py : (modèles en échec, sortie affichée)."""
        with tempfile.TemporaryDirectory(prefix="qwen-setup-test-") as tmp:
            os.makedirs(os.path.join(tmp, "tools"))
            with open(os.path.join(tmp, "tools", "calibrate.py"), "w", encoding="utf-8") as f:
                f.write(script)
            with mock.patch.object(setup, "P", lambda *a: os.path.join(tmp, *a)), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                failed = setup.step_calibrate(["q4"], check_only=False, skip=False)
        return failed, out.getvalue()

    def test_a_failed_calibration_shows_its_error_and_goes_on(self):
        failed, out = self.calibrate(BROKEN)
        self.assertEqual(failed, ["q4"])
        self.assertIn("RuntimeError: moteur introuvable (essai)", out)          # l'erreur, pas seulement « échec »
        self.assertIn("[calibration] ÉCHEC du modèle q4 (RuntimeError: moteur introuvable (essai))", out)
        self.assertIn("l'installation continue sans calibration", out)

    def test_a_working_calibration_says_nothing_of_a_failure(self):
        failed, out = self.calibrate(WORKING)
        self.assertEqual(failed, [])
        self.assertNotIn("ÉCHEC", out)

    def test_skipped_or_checked_runs_nothing(self):
        with mock.patch.object(setup.subprocess, "run") as run:
            self.assertEqual(setup.step_calibrate(["q4"], check_only=True, skip=False), [])
            self.assertEqual(setup.step_calibrate(["q4"], check_only=False, skip=True), [])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
