"""Contrôles de tests/check.py qui ne se voient pas en le lançant sur le dépôt : un fichier nouveau, pas encore ajouté à
git, est contrôlé comme un fichier suivi ; une adresse donnée à la main à une image affichée est refusée ; une ligne
trop longue est refusée par --lines, par le hook avant commit et par le contrôle complet, qui s'arrête alors avant le
banc ; --link-venv relie les notes du dossier principal dans un worktree."""
import contextlib, io, os, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402

LONG = "# " + "x" * 119                              # 121 caractères : un de trop
GIT_USER = ("-c", "user.name=banc", "-c", "user.email=banc@example.com")


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout


class RepoCase(unittest.TestCase):
    """Dépôt git temporaire, avec un commit de base que origin/main désigne ; check.ROOT y est repointé."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qwen-check-test-")
        self.root = os.path.join(self.tmp.name, "depot")
        os.makedirs(self.root)
        sh(self.root, "git", "init", "-q")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "--allow-empty", "-m", "base")
        sh(self.root, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
        self.base = sh(self.root, "git", "rev-parse", "HEAD").strip()
        self.patch = mock.patch.object(check, "ROOT", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def write(self, name, text, root=None):
        path = os.path.join(root or self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


class NewFilesTest(RepoCase):
    def test_a_new_file_is_checked_before_its_first_commit(self):
        self.write("nouveau.mjs", "const x = 1;\n// " + "x" * 130 + "\n")
        self.write(".gitignore", "ignore.mjs\n")
        self.write("ignore.mjs", "// " + "x" * 130 + "\n")
        self.assertEqual(check.checked_files("*.mjs"), ["nouveau.mjs"])
        self.assertEqual(check.added_lines(self.base, "*.mjs"), {"nouveau.mjs": {1, 2}})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.check_line_length(self.base), ["nouveau.mjs:2"])
        self.assertIn("nouveau.mjs:2 (133 caractères)", out.getvalue())


class LinesTest(RepoCase):
    """Une ligne de 121 caractères est refusée par --lines, par le hook (commit refusé) et par le contrôle complet,
    qui s'arrête avant le banc et la nomme dans sa dernière ligne."""
    def install_check(self):
        """check.py et le hook dans le dépôt temporaire, dans la base ; hook activé comme par --link-venv."""
        for rel in ("tests/check.py", ".githooks/pre-commit"):
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
            shutil.copy2(os.path.join(HERE, "..", rel), os.path.join(self.root, rel))
        sh(self.root, "git", "add", "tests", ".githooks")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "--no-verify", "-m", "outils")
        sh(self.root, "git", "update-ref", "refs/remotes/origin/main", "HEAD")
        sh(self.root, "git", "config", "core.hooksPath", ".githooks")

    def run_check(self, *args):
        return subprocess.run([sys.executable, os.path.join("tests", "check.py"), *args], cwd=self.root,
                              capture_output=True, text=True, env=dict(os.environ, QWEN_CHECK_REEXEC="1"))

    def commit(self, message):
        return subprocess.run(["git", *GIT_USER, "commit", "-q", "-m", message], cwd=self.root, capture_output=True,
                              text=True)

    def test_lines_option_names_the_long_line(self):
        self.install_check()
        self.write("a.py", "x = 1\n" + LONG + "\n")
        r = self.run_check("--lines")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("a.py:2 (121 caractères)", r.stdout)
        self.write("a.py", "x = 1\n" + LONG[:-1] + "\n")   # 120 : permise
        self.assertEqual(self.run_check("--lines").returncode, 0)

    def test_the_hook_refuses_a_commit_that_adds_a_long_line(self):
        self.install_check()
        self.write("notes.md", "Titre\n\n" + LONG + "\n")
        sh(self.root, "git", "add", "notes.md")
        r = self.commit("ligne longue")
        self.assertNotEqual(r.returncode, 0, "commit accepté")
        self.assertIn("notes.md:3", r.stdout + r.stderr)
        self.assertEqual(sh(self.root, "git", "log", "--format=%s", "-1").strip(), "outils")
        # le hook juge l'index : une ligne longue laissée hors de l'index ne refuse pas le commit
        self.write("notes.md", "Titre\n")
        sh(self.root, "git", "add", "notes.md")
        self.write("notes.md", "Titre\n" + LONG + "\n")
        self.assertEqual(self.commit("ligne courte").returncode, 0)

    def test_the_full_check_stops_before_the_bench_and_names_the_line_last(self):
        self.write("b.mjs", "const x = 1;\n" + "//" + LONG + "\n")
        args = mock.Mock(no_bench=False, quick=False, ui=[], lines=False, link_venv=False)
        with mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "run_bench") as bench, mock.patch.object(check, "run_ui") as ui, \
                mock.patch.object(check, "journal_path", return_value=os.path.join(self.tmp.name, "journal.log")), \
                mock.patch.object(check, "reexec_in_venv"), \
                mock.patch("argparse.ArgumentParser.parse_args", return_value=args), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(), 1)
        bench.assert_not_called()
        ui.assert_not_called()
        lines = out.getvalue().strip().splitlines()
        self.assertEqual(lines[-1], "Contrôles : ÉCHEC : Lignes : b.mjs:2")
        with open(os.path.join(self.tmp.name, "journal.log"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip().splitlines()[-1], lines[-1])


class LinkNotesTest(unittest.TestCase):
    """--link-venv dans un worktree : venv, notes non suivies et notes de docs/agents (sauf la carte du code) reliées
    au dossier principal, un lien cassé refait, un fichier réel gardé ; git status reste propre ; hook activé."""
    def test_worktree_notes_are_linked_to_the_main_checkout(self):
        with tempfile.TemporaryDirectory(prefix="qwen-check-test-") as tmp:
            main, wt = os.path.join(tmp, "principal"), os.path.join(tmp, "principal", ".claude", "worktrees", "t")
            os.makedirs(main)
            shutil.copy2(os.path.join(HERE, "..", ".gitignore"), main)
            self.write(main, "docs/agents/carte-du-code.md", "carte suivie\n")
            sh(main, "git", "init", "-q")
            sh(main, "git", "add", ".gitignore", "docs")
            sh(main, "git", *GIT_USER, "commit", "-q", "-m", "base")
            for rel in ("CLAUDE.md", "ETAT_DU_PROJET.md", "travail/plan.md", "docs/specs/spec.md",
                        "docs/agents/domain.md", "docs/agents/session-deleguee.md", "venv/" + check.VENV_PY):
                self.write(main, rel, f"principal : {rel}\n")
            sh(main, "git", "worktree", "add", "-q", wt)
            self.write(wt, "ETAT_DU_PROJET.md", "copie réelle\n")                   # gardée, signalée
            os.symlink("../../ailleurs/domain.md", os.path.join(wt, "docs", "agents", "domain.md"))   # cassé
            with mock.patch.object(check, "ROOT", wt), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.link_venv(), 0)
            for rel in ("venv", "CLAUDE.md", "travail", "docs/specs", "docs/agents/domain.md",
                        "docs/agents/session-deleguee.md"):
                self.assertTrue(os.path.islink(os.path.join(wt, rel)), rel)
                self.assertFalse(os.path.isabs(os.readlink(os.path.join(wt, rel))), rel)
                self.assertTrue(os.path.samefile(os.path.join(wt, rel), os.path.join(main, rel)), rel)
            self.assertFalse(os.path.islink(os.path.join(wt, "ETAT_DU_PROJET.md")))
            self.assertFalse(os.path.islink(os.path.join(wt, "docs", "agents", "carte-du-code.md")))
            self.assertIn("ETAT_DU_PROJET.md : un fichier réel est déjà là", out.getvalue())
            self.assertIn("docs/agents/domain.md : lien cassé refait", out.getvalue())
            self.assertEqual(sh(wt, "git", "status", "--porcelain"), "")
            self.assertEqual(sh(wt, "git", "config", "--get", "core.hooksPath").strip(), ".githooks")
            with mock.patch.object(check, "ROOT", wt), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.link_venv(), 0)              # relancé : rien ne change
            self.assertNotIn("créé", out.getvalue())

    @staticmethod
    def write(root, rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


class ImageSrcTest(unittest.TestCase):
    def test_a_displayed_image_only_gets_its_address_through_showImage(self):
        html = "\n".join([
            "$('vImg').src=url;",                     # 1 : refusée
            "const a = $( \"stageImg\" ).src = '';",  # 2 : refusée
            "if($('ivImg').src==u) go();",            # comparaison : permise
            "$('vImgX').src=u; img.src=url;",         # autre élément, ou variable (showImage) : permis
            "$('vBg').src  =  thumb;",                # 5 : refusée
            "$('paintImg').src=im.dataUrl;",          # 6 : refusée (image du dessin)
        ])
        self.assertEqual(check.image_src_lines(html), [1, 2, 5, 6])

    def test_the_interface_follows_the_rule(self):
        with open(os.path.join(os.path.dirname(check.__file__), "..", "tools", "ui", "index.html"),
                  encoding="utf-8") as f:
            self.assertEqual(check.image_src_lines(f.read()), [])


if __name__ == "__main__":
    unittest.main()
