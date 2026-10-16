"""Contrôles de tests/check.py qui ne se voient pas en le lançant sur le dépôt : un fichier nouveau, pas encore ajouté à
git, est contrôlé comme un fichier suivi, et une adresse donnée à la main à une image affichée est refusée."""
import contextlib, io, os, subprocess, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class NewFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qwen-check-test-")
        self.root = self.tmp.name
        sh(self.root, "git", "init", "-q")
        sh(self.root, "git", "-c", "user.name=banc", "-c", "user.email=banc@example.com", "commit", "-q",
           "--allow-empty", "-m", "base")
        self.base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True, text=True,
                                   check=True).stdout.strip()
        self.patch = mock.patch.object(check, "ROOT", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def write(self, name, text):
        with open(os.path.join(self.root, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_a_new_file_is_checked_before_its_first_commit(self):
        self.write("nouveau.mjs", "const x = 1;\n// " + "x" * 130 + "\n")
        self.write(".gitignore", "ignore.mjs\n")
        self.write("ignore.mjs", "// " + "x" * 130 + "\n")
        self.assertEqual(check.checked_files("*.mjs"), ["nouveau.mjs"])
        self.assertEqual(check.added_lines(self.base, "*.mjs"), {"nouveau.mjs": {1, 2}})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertFalse(check.check_line_length(self.base))
        self.assertIn("nouveau.mjs:2 (133 caractères)", out.getvalue())


class ImageSrcTest(unittest.TestCase):
    def test_a_displayed_image_only_gets_its_address_through_showImage(self):
        html = "\n".join([
            "$('vImg').src=url;",                     # 1 : refusée
            "const a = $( \"stageImg\" ).src = '';",  # 2 : refusée
            "if($('ivImg').src==u) go();",            # comparaison : permise
            "$('vImgX').src=u; img.src=url;",         # autre élément, ou variable (showImage) : permis
            "$('vBg').src  =  thumb;",                # 5 : refusée
        ])
        self.assertEqual(check.image_src_lines(html), [1, 2, 5])

    def test_the_interface_follows_the_rule(self):
        with open(os.path.join(os.path.dirname(check.__file__), "..", "tools", "ui", "index.html"),
                  encoding="utf-8") as f:
            self.assertEqual(check.image_src_lines(f.read()), [])


if __name__ == "__main__":
    unittest.main()
