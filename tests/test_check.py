"""Contrôles de tests/check.py qui ne se voient pas en le lançant sur le dépôt : un fichier nouveau, pas encore ajouté à
git, est contrôlé comme un fichier suivi ; une adresse donnée à la main à une image affichée est refusée ; une ligne
trop longue est refusée par --lines, par le hook avant commit et par le contrôle complet, qui s'arrête alors avant le
banc ; --link-venv relie les notes du dossier principal dans un worktree ; les fichiers d'interface tournent sur
plusieurs Chrome à la fois ; l'avis « zone sensible » ne regarde que le travail de la branche en cours."""
import argparse, contextlib, io, os, shutil, subprocess, sys, tempfile, threading, unittest
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
        for rel in ("tests/check.py", "tests/rules.py", ".githooks/pre-commit"):
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
        args = argparse.Namespace(no_bench=False, quick=False, ui=[], name=None, lines=False, link_venv=False,
                                  map=None)
        with mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "check_rules", return_value=[]), \
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


class UiNameTest(unittest.TestCase):
    """--ui --name : un motif qui ne vise aucun test échoue tout de suite, sans lancer Chrome ni le banc."""
    def test_titles_are_read_from_the_test_files(self):
        titles = check.ui_titles(["tests/ui/smoke.test.mjs"])
        self.assertGreater(len(titles), 0)
        self.assertTrue(all(isinstance(t, str) and t for t in titles))
        self.assertTrue(any(t.startswith("« Révéler » suit la génération sur le Labo") for t in titles), titles)

    def test_a_pattern_without_test_fails_at_once(self):
        args = argparse.Namespace(no_bench=False, quick=False, ui=["tests/ui/smoke.test.mjs"], name="zz-aucun-test",
                                  lines=False, link_venv=False, map=None)
        with tempfile.TemporaryDirectory(prefix="qwen-check-test-") as tmp, \
                mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "check_line_length", return_value=[]), \
                mock.patch.object(check, "check_rules", return_value=[]), \
                mock.patch.object(check, "run_bench") as bench, mock.patch.object(check, "run_ui") as ui, \
                mock.patch.object(check, "journal_path", return_value=os.path.join(tmp, "journal.log")), \
                mock.patch.object(check, "reexec_in_venv"), \
                mock.patch("argparse.ArgumentParser.parse_args", return_value=args), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(), 1)
        bench.assert_not_called()                     # rien n'est lancé, ni le banc ni Chrome
        ui.assert_not_called()
        self.assertIn("aucun test ne correspond au motif « zz-aucun-test »", out.getvalue())
        self.assertEqual(out.getvalue().strip().splitlines()[-1],
                         "Contrôles : ÉCHEC : Interface : motif « zz-aucun-test » sans test")
        args.name = "Révéler"                         # un motif qui vise un test : l'interface est lancée
        with mock.patch.object(check, "run_ui", return_value=(True, [], [])) as ui, \
                mock.patch.object(check, "run_bench", return_value=(True, [], [])), \
                mock.patch.object(check, "sensitive_notice"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.run_checks(args), {})
        ui.assert_called_once()


class UiParallelTest(unittest.TestCase):
    """Les fichiers d'interface tournent sur UI_JOBS Chrome à la fois (chacun son banc, ses ports et son dossier
    temporaire) ; les lignes et les totaux restent dans l'ordre des fichiers."""
    def test_files_run_side_by_side_and_report_in_order(self):
        both = threading.Barrier(2, timeout=10)          # a et b doivent tourner ensemble : sinon le test échoue

        def fake(f, flags, env):
            if f in ("a.test.mjs", "b.test.mjs"):
                both.wait()
            return f"ℹ tests 2\nℹ pass {1 if f == 'b.test.mjs' else 2}\nℹ fail {1 if f == 'b.test.mjs' else 0}", \
                int(f == "b.test.mjs")
        with mock.patch.object(check, "run_ui_file", fake):
            ok, lines, faults = check.run_ui(["a.test.mjs", "b.test.mjs", "c.test.mjs"], jobs=2)
        self.assertFalse(ok)
        self.assertEqual(faults, ["b.test.mjs"])
        per_file = [line.split(" : ")[1] for line in lines
                    if line.startswith("Interface : ") and ".test.mjs : " in line]
        self.assertEqual(per_file, ["a.test.mjs", "b.test.mjs", "c.test.mjs"])
        self.assertTrue(any("3 fichier(s), 6 tests, 5 réussis, 1 en échec" in line for line in lines), lines)


class NoticeBaseTest(RepoCase):
    """L'avis « zone sensible » compare à la base de la branche en cours (celle d'un groupe : là où elle a quitté
    dev ; dev lui-même : le dernier commit), pas à origin/main : il ne cite plus les groupes déjà fusionnés."""
    def notice(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            check.sensitive_notice(check.notice_base())
        return out.getvalue()

    def test_merged_work_does_not_raise_the_notice_again(self):
        sh(self.root, "git", "checkout", "-q", "-b", "dev")
        self.write("tools/vieux.js", "inPrivate();\n")
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", "groupe fusionné")
        self.assertEqual(self.notice(), "", "dev propre : rien de neuf")
        self.write("tools/neuf.js", "privState;\n")
        self.assertIn("privState dans tools/neuf.js", self.notice())
        sh(self.root, "git", "checkout", "-q", "-b", "worktree-groupe-x")
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", "ticket du groupe")
        notice = self.notice()
        self.assertIn("privState dans tools/neuf.js", notice)
        self.assertNotIn("vieux.js", notice)

    def test_main_a_detached_head_or_no_dev_count_only_what_is_not_committed(self):
        self.write("tools/vieux.js", "inPrivate();\n")
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", "travail fusionné")
        sh(self.root, "git", "checkout", "-q", "-b", "autre")          # branche de groupe, sans branche dev
        self.assertEqual(self.notice(), "")
        sh(self.root, "git", "checkout", "-q", "--detach")              # tête détachée (CI d'une PR)
        self.assertEqual(self.notice(), "")
        self.write("tools/neuf.js", "privState;\n")
        self.assertIn("privState dans tools/neuf.js", self.notice())

    def test_outside_git_there_is_no_notice(self):
        with mock.patch.object(check, "git", side_effect=OSError("git absent")):
            self.assertIsNone(check.notice_base())


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


class HooksMessageTest(RepoCase):
    """--link-venv : un core.hooksPath qui pointe déjà vers un dossier qui contient le hook (celui du dossier principal,
    vu d'un worktree, en chemin absolu ou relatif) est dit actif, pas « non activé »."""
    def hooks_message(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            check.link_hooks()
        return out.getvalue()

    def test_a_hooks_path_that_holds_the_hook_is_reported_active(self):
        self.write("ailleurs/.githooks/pre-commit", "#!/bin/sh\n")
        for value in (os.path.join(self.root, "ailleurs", ".githooks"), "ailleurs/.githooks"):
            sh(self.root, "git", "config", "core.hooksPath", value)
            message = self.hooks_message()
            self.assertIn("pre-commit actif", message)
            self.assertNotIn("pas activé", message)
            self.assertNotIn("n'est pas activé", message)
        sh(self.root, "git", "config", "core.hooksPath", "autres-hooks")      # sans le hook : signalé
        self.assertIn("n'est pas activé", self.hooks_message())


class ImageSrcTest(unittest.TestCase):
    def test_a_displayed_image_only_gets_its_address_through_showImage(self):
        html = "\n".join([
            "$('vImg').src=url;",                     # 1 : refusée
            "const a = $( \"ivImg\" ).src = '';",     # 2 : refusée
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
