"""Versions du modèle de diffusion et réglages locaux : setup.py et tools/launch.py restent d'accord.

  venv/bin/python -m unittest discover -s tests -p test_models.py

Pas besoin du serveur du banc : les deux modules sont importés, rien n'est téléchargé.
"""
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import launch, setup


class ModelsTest(unittest.TestCase):
    def test_setup_installs_the_files_the_launcher_loads(self):
        self.assertEqual(list(setup.DIFFUSION), list(launch.DIFFUSION))
        self.assertEqual(set(launch.SETUP_FLAGS), set(launch.DIFFUSION))
        for version, (url, local, size, digest) in setup.DIFFUSION.items():
            self.assertEqual(os.path.basename(local), os.path.basename(launch.DIFFUSION[version]), version)
            self.assertEqual(url.rsplit("/", 1)[1], os.path.basename(local), version)
            self.assertRegex(digest, r"^[0-9a-f]{64}$", version)
            self.assertGreater(size, 0, version)

    def test_default_versions_come_from_the_base_branch_of_official_weights(self):
        for version in ("q4", "q8"):
            url = setup.DIFFUSION[version][0]
            self.assertTrue(url.startswith(setup.BASE), version)
            self.assertNotIn("-UC-", url, version)


class LocalConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.saved = launch.CONFIG, launch.CONFIG_LOCAL
        launch.CONFIG = os.path.join(self.dir.name, "config.json")
        launch.CONFIG_LOCAL = os.path.join(self.dir.name, "config.local.json")
        with open(launch.CONFIG, "w", encoding="utf-8") as f:
            json.dump({"backend": "vulkan", "ui_port": 7860}, f)

    def tearDown(self):
        launch.CONFIG, launch.CONFIG_LOCAL = self.saved
        self.dir.cleanup()

    def test_without_a_local_file_the_shared_config_applies(self):
        cfg = launch.load_config()
        self.assertEqual(cfg["ui_port"], 7860)
        self.assertNotIn("model", cfg)

    def test_the_local_file_overrides_the_shared_config(self):
        with open(launch.CONFIG_LOCAL, "w", encoding="utf-8") as f:
            json.dump({"model": "uc-q8", "ui_port": 7861}, f)
        cfg = launch.load_config()
        self.assertEqual((cfg["model"], cfg["ui_port"], cfg["backend"]), ("uc-q8", 7861, "vulkan"))


if __name__ == "__main__":
    unittest.main()
