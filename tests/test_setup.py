"""setup.py : une calibration qui échoue ne passe plus inaperçue. L'erreur de tools/calibrate.py est affichée, et
l'installation dit qu'elle continue sans calibration (une calibration cassée était passée inaperçue au groupe B du
parcours des pages, 10/2026). Le moteur du Mac installé est la release épinglée, et remplace l'ancienne.

  venv/bin/python -m unittest discover -s tests -p test_setup.py

Pas de vraie calibration : tools/calibrate.py est remplacé par un faux script dans un dossier temporaire. Pas de vrai
téléchargement : l'archive du moteur est un faux fichier, dont l'empreinte est remplacée.
"""
import contextlib, io, os, re, sys, tempfile, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import estimate, setup  # noqa: E402

# release du moteur du Mac, son archive et l'empreinte publiée (ticket 01 de la mission MiniMax H3)
MAC_TAG = "master-1090-8b1e9df"
MAC_ARCHIVE = "sd-master-8b1e9df-bin-Darwin-macOS-26.7.2-arm64.zip"
MAC_SHA = "dcf8fcd492a0d7c89eab61a662a393df082f7b81d53a21855e957d389f4d2528"

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


class MacEngineTest(unittest.TestCase):
    def install(self, have):
        """step_engine(["metal"]) sur un moteur installé à la release have (None : aucun) : (adresses téléchargées,
        marqueur écrit, empreintes demandées)."""
        urls, digests = [], []

        def download(url, path):
            urls.append(url)
            os.makedirs(os.path.dirname(path), exist_ok=True)       # comme download_once
            with open(path, "wb") as f:
                f.write(b"archive")

        def sha256(path):
            digests.append(os.path.basename(path))
            return MAC_SHA

        with tempfile.TemporaryDirectory(prefix="qwen-setup-test-") as tmp:
            if have:
                os.makedirs(os.path.join(tmp, "sdcpp", "metal"))
                with open(os.path.join(tmp, "sdcpp", "metal", ".installed"), "w", encoding="utf-8") as f:
                    f.write(have)
            with mock.patch.object(setup, "P", lambda *a: os.path.join(tmp, *a)), \
                    mock.patch.object(setup, "download", download), mock.patch.object(setup, "sha256", sha256), \
                    mock.patch.object(setup, "extract", lambda z, dest: os.makedirs(dest, exist_ok=True)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(setup.step_engine(["metal"], check_only=False))
            with open(os.path.join(tmp, "sdcpp", "metal", ".installed"), encoding="utf-8") as f:
                marker = f.read()
        return urls, marker, digests

    def test_the_mac_installs_the_pinned_release(self):
        urls, marker, digests = self.install(None)
        self.assertEqual(urls, ["https://github.com/leejet/stable-diffusion.cpp/releases/download/"
                                f"{MAC_TAG}/{MAC_ARCHIVE}"])
        self.assertEqual(digests, [MAC_ARCHIVE])
        self.assertEqual(marker, MAC_TAG)
        self.assertRegex(marker, r"^master-\d+-[0-9a-f]{7}$")       # forme lue par estimate.prefix_cache
        self.assertTrue(estimate.prefix_cache(marker))

    def test_an_older_mac_engine_is_replaced(self):
        urls, marker, _ = self.install("master-959-d637cfb")
        self.assertEqual(len(urls), 1)
        self.assertEqual(marker, MAC_TAG)

    def test_every_pinned_release_keeps_the_marker_form(self):
        for be, (tag, archives) in setup.SDCPP.items():
            self.assertRegex(tag, r"^master-\d+-[0-9a-f]{7}$", be)
            self.assertIn(tag.rsplit("-", 1)[1], archives[0][0], be)     # l'archive est celle de la release


if __name__ == "__main__":
    unittest.main()
