"""setup.py : une calibration qui échoue ne passe plus inaperçue. L'erreur de tools/calibrate.py est affichée, et
l'installation dit qu'elle continue sans calibration (une calibration cassée était passée inaperçue au groupe B du
parcours des pages, 10/2026). Le moteur du Mac installé est la release épinglée, et remplace l'ancienne. MiniMax H3
s'installe par --h3 et --h3-q8 (Mac seulement), sans retélécharger un fichier déjà vérifié, et --check dit ce qui est
installé pour chaque modèle.

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


def small(entries):
    """Les fichiers épinglés entries (dict ou liste de (url, chemin, taille, sha256)) avec une taille de 5 octets : les
    faux téléchargements écrivent 5 octets, au lieu de 11 à 21 Go."""
    if isinstance(entries, dict):
        return {k: (url, local, 5, digest) for k, (url, local, _, digest) in entries.items()}
    return [(url, local, 5, digest) for url, local, _, digest in entries]


class H3InstallTest(unittest.TestCase):
    """setup.py --h3 et --h3-q8, et --check, dans un dossier temporaire : téléchargements et empreintes simulés."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qwen-setup-h3-")
        self.addCleanup(self.tmp.cleanup)
        self.urls, self.digests = [], []
        files = {"H3_DIFFUSION": small(setup.H3_DIFFUSION), "H3_FILES": small(setup.H3_FILES),
                 "DIFFUSION": small(setup.DIFFUSION), "ENCODER": small(setup.ENCODER), "VAE": small([setup.VAE])[0]}
        digest = {local: d for _, local, _, d in
                  list(setup.DIFFUSION.values()) + list(setup.H3_DIFFUSION.values()) + list(setup.H3_FILES.values())
                  + setup.ENCODER + [setup.VAE]}
        for name, value in files.items():
            patcher = mock.patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        def download(url, dest, size):
            self.urls.append(url)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(b"poids")

        def sha256(path):
            self.digests.append(os.path.basename(path))
            return digest[os.path.relpath(path, self.tmp.name).replace(os.sep, "/")]

        for name, value in (("P", lambda *a: os.path.join(self.tmp.name, *a)), ("download", download),
                            ("sha256", sha256), ("MACOS", True), ("WINDOWS", False)):
            patcher = mock.patch.object(setup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_setup(self, *argv):
        """main() de setup.py avec ces options, réduit à ses étapes de modèles (moteur, correctif, réglage du moteur,
        raccourci et calibration remplacés) ; renvoie ce qu'il imprime."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["setup.py", *argv]), contextlib.redirect_stdout(out), \
                mock.patch.object(setup, "step_engine", lambda backends, check_only: True), \
                mock.patch.object(setup, "step_fix", lambda check_only: True), \
                mock.patch.object(setup, "step_config", lambda backends, check_only: None), \
                mock.patch.object(setup, "step_shortcut", lambda check_only: True), \
                mock.patch.object(setup, "step_calibrate", lambda versions, check_only, skip: []):
            setup.main()
        return out.getvalue()

    def pinned(self, *keys):
        """Adresses épinglées des fichiers MiniMax H3 nommés (clés de H3_DIFFUSION ou de H3_FILES)."""
        return [{**setup.H3_DIFFUSION, **setup.H3_FILES}[k][0] for k in keys]

    def h3_urls(self):
        return sorted(u for u in self.urls if u in self.pinned(*setup.H3_DIFFUSION, *setup.H3_FILES))

    def test_h3_downloads_the_pinned_q4_files_once(self):
        self.run_setup("--h3", "--no-calibrate")
        self.assertEqual(self.h3_urls(), sorted(self.pinned("h3-q4", "llm", "vae")))
        self.urls.clear()
        self.digests.clear()
        self.run_setup("--h3", "--no-calibrate")                     # déjà vérifiés : ni téléchargés ni rehachés
        self.assertEqual(self.urls, [])
        self.assertEqual(self.digests, [])

    def test_h3_q8_downloads_the_q8_model_with_the_shared_files(self):
        self.run_setup("--h3-q8", "--no-calibrate")
        self.assertEqual(self.h3_urls(), sorted(self.pinned("h3-q8", "llm", "vae")))

    def test_without_the_option_nothing_of_h3_is_downloaded(self):
        self.run_setup("--no-calibrate")
        self.assertTrue(self.urls)
        self.assertEqual(self.h3_urls(), [])

    def test_the_options_are_refused_outside_macos_before_any_download(self):
        for option in ("--h3", "--h3-q8"):
            with mock.patch.object(setup, "MACOS", False), mock.patch.object(setup, "WINDOWS", True), \
                    self.assertRaises(SystemExit) as stop:
                self.run_setup(option)
            self.assertIn("Mac", str(stop.exception), option)
            self.assertIn(option, str(stop.exception), option)
        self.assertEqual(self.urls, [])
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_check_says_what_is_installed_for_each_model(self):
        self.run_setup("--no-calibrate")                             # Qwen seul
        out = self.run_setup("--check")
        self.assertIn("Qwen : installé (q4)", out)
        self.assertIn("MiniMax H3 : non installé (option --h3, ou --h3-q8 pour la version Q8_0)", out)
        self.assertIn("État : complet", out)
        self.run_setup("--h3", "--no-calibrate")
        self.urls.clear()
        out = self.run_setup("--check")
        self.assertIn("MiniMax H3 : installé (h3-q4)", out)
        self.assertIn("État : complet", out)
        self.assertEqual(self.urls, [])                              # --check ne télécharge rien

    def test_check_says_a_partial_h3_install_and_its_option(self):
        self.run_setup("--h3-q8", "--no-calibrate")
        os.remove(os.path.join(self.tmp.name, *setup.H3_FILES["llm"][1].split("/")))
        out = self.run_setup("--check")
        self.assertIn("MiniMax H3 : incomplet", out)
        self.assertIn("setup.py --h3-q8", out)
        self.assertIn("État : incomplet", out)

    def test_check_says_an_interrupted_h3_download(self):
        part = os.path.join(self.tmp.name, *setup.H3_DIFFUSION["h3-q4"][1].split("/")) + ".part"
        os.makedirs(os.path.dirname(part))
        with open(part, "wb") as f:
            f.write(b"po")
        out = self.run_setup("--check")
        self.assertIn("MiniMax H3 : incomplet, lancez : venv/bin/python setup.py --h3", out)
        self.assertIn("État : incomplet", out)

    def test_check_outside_macos_says_h3_is_for_the_mac(self):
        with mock.patch.object(setup, "MACOS", False), mock.patch.object(setup, "WINDOWS", True):
            out = self.run_setup("--check")
        self.assertIn("MiniMax H3 : Mac seulement", out)


if __name__ == "__main__":
    unittest.main()
