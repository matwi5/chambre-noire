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

    def test_setup_installs_the_h3_files_the_launcher_loads(self):
        """MiniMax H3 : mêmes versions et mêmes fichiers des deux côtés (noms et dossier seulement : le banc repointe
        les chemins du serveur), adresses épinglées sur un commit, tailles et empreintes en forme."""
        self.assertEqual(list(setup.H3_DIFFUSION), list(launch.H3_DIFFUSION))
        self.assertEqual(list(setup.H3_FILES), list(launch.H3_FILES))
        for served, installed in ((launch.H3_DIFFUSION, setup.H3_DIFFUSION), (launch.H3_FILES, setup.H3_FILES)):
            for key, (url, local, size, digest) in installed.items():
                self.assertEqual(os.path.basename(local), os.path.basename(served[key]), key)
                self.assertEqual(local.split("/")[:2], ["models", {"llm": "text_encoders", "vae": "vae"}.get(
                    key, "diffusion_models")], key)
                self.assertEqual(url.rsplit("/", 1)[1], os.path.basename(local), key)
                self.assertRegex(url, r"^https://huggingface\.co/[\w.-]+/[\w.-]+/resolve/[0-9a-f]{40}/", key)
                self.assertRegex(digest, r"^[0-9a-f]{64}$", key)
                self.assertGreater(size, 0, key)
        spec = launch.MODEL_TABLE["h3"]
        self.assertEqual(set(spec["config"].values()), set(launch.H3_DIFFUSION))
        self.assertEqual(spec["setup"], "--h3")
        options = setup.parser().parse_args(["--h3", "--h3-q8"])
        self.assertTrue(options.h3 and options.h3_q8)

    def test_setup_installs_the_video_files_the_launcher_loads(self):
        """Vidéo : mêmes clés et mêmes fichiers des deux côtés (noms et dossiers), adresses épinglées sur un commit,
        tailles et empreintes en forme ; l'encodeur est celui de MiniMax H3 ; option --h3-video des deux côtés."""
        self.assertEqual(list(setup.VIDEO_DIFFUSION), list(launch.VIDEO_DIFFUSION))
        self.assertEqual(list(setup.VIDEO_FILES), list(launch.VIDEO_FILES))
        folders = {"llm": "text_encoders", "vae": "vae", "lora": "loras"}
        for served, installed in ((launch.VIDEO_DIFFUSION, setup.VIDEO_DIFFUSION), (launch.VIDEO_FILES,
                                                                                   setup.VIDEO_FILES)):
            for key, (url, local, size, digest) in installed.items():
                self.assertEqual(os.path.basename(local), os.path.basename(served[key]), key)
                self.assertEqual(local.split("/")[:2], ["models", folders.get(key, "diffusion_models")], key)
                self.assertEqual(url.rsplit("/", 1)[1], os.path.basename(local), key)
                self.assertRegex(url, r"^https://huggingface\.co/[\w.-]+/[\w.-]+/resolve/[0-9a-f]{40}/", key)
                self.assertRegex(digest, r"^[0-9a-f]{64}$", key)
                self.assertGreater(size, 0, key)
        self.assertEqual(setup.VIDEO_FILES["llm"], setup.H3_FILES["llm"])
        self.assertEqual(setup.VIDEO_FILES["lora"][3],
                         "70103fd0d80a947ed4e7fe6f88915863d54ef22c5cab03bd5d2fd649385ffe1e")
        spec = launch.MODEL_TABLE["video"]
        self.assertEqual(set(spec["versions"]), set(launch.VIDEO_DIFFUSION))
        self.assertEqual(spec["setup"], "--h3-video")
        self.assertTrue(setup.parser().parse_args(["--h3-video"]).h3_video)


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
