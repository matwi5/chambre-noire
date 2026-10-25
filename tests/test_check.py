"""Contrôles de tests/check.py qui ne se voient pas en le lançant sur le dépôt : un fichier nouveau, pas encore ajouté à
git, est contrôlé comme un fichier suivi ; une adresse donnée à la main à une image affichée est refusée ; une ligne
trop longue est refusée par --lines, par le hook avant commit et par le contrôle complet, qui s'arrête alors avant le
banc ; --link-venv relie les notes du dossier principal dans un worktree ; les fichiers d'interface tournent sur
plusieurs Chrome à la fois ; l'avis « zone sensible » ne regarde que le travail de la branche en cours."""
import contextlib, io, json, os, shutil, subprocess, sys, tempfile, threading, unittest
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
        for rel in ("tests/check.py", "tests/rules.py", "tests/rewrap.py", ".githooks/pre-commit"):
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

    def test_fix_recuts_only_the_long_added_lines(self):
        words = " ".join(f"mot{i}" for i in range(30))       # ≈ 170 caractères
        base_md = ["# Notes", "", "Ancienne " + words, "suite ancienne", ""]
        self.write("notes.md", "\n".join(base_md))
        self.write("a.py", "\n".join(["def f():", '    """Court."""', "    return 1", ""]))
        sh(self.root, "git", "add", "notes.md", "a.py")
        self.install_check()                                    # notes.md et a.py dans la base
        md = base_md[:4] + ["", "- puce " + words, "  suite de la puce", "", "> citation " + words, "",
                            "Paragraphe court.", "Ligne " + words, "dernière ligne du paragraphe", ""]
        self.write("notes.md", "\n".join(md))
        py = ["def f():", '    """Court.', "", "    Docstring " + words, '    """',
              "    # commentaire " + words, "    return 1  # " + words, ""]
        self.write("a.py", "\n".join(py))
        r = self.run_check("--lines", "--fix")
        self.assertEqual(r.returncode, 1, r.stdout)          # la ligne de code reste : signalée
        self.assertIn("a.py:", r.stdout)
        self.assertIn("à recouper à la main", r.stdout)
        with open(os.path.join(self.root, "notes.md"), encoding="utf-8") as f:
            new_md = f.read().split("\n")
        self.assertEqual(new_md[:4], base_md[:4], "ligne de la base laissée telle quelle")
        words_of = lambda ls: [w for w in " ".join(ls).split() if w not in (">", "#")]   # marques des suites ôtées
        self.assertEqual(words_of(new_md), words_of(md), "mêmes mots, même ordre")
        added = new_md[4:]
        self.assertTrue(len(added) > 10 and all(len(l) <= 120 for l in added), new_md)
        bullet = new_md[new_md.index(next(l for l in new_md if l.startswith("- puce"))):]
        self.assertTrue(bullet[1].startswith("  mot") or bullet[1].startswith("  suite"), bullet)
        quote = [l for l in new_md if "citation" in l or (l.startswith("> ") and "mot" in l)]
        self.assertTrue(len(quote) > 1 and all(l.startswith("> ") for l in quote), quote)
        self.assertIn("Paragraphe court.", new_md, "le reste du paragraphe n'est pas recoupé")
        with open(os.path.join(self.root, "a.py"), encoding="utf-8") as f:
            new_py = f.read().split("\n")
        self.assertEqual(words_of(new_py), words_of(py))
        comment = [l for l in new_py if l.lstrip().startswith("#")]
        self.assertTrue(len(comment) > 1 and all(l.startswith("    # ") for l in comment), comment)
        doc = new_py[new_py.index(next(l for l in new_py if "Docstring" in l)) + 1]
        self.assertTrue(doc.startswith("    mot"), doc)
        self.assertIn("    return 1  # " + words, new_py, "ligne de code : laissée")
        compile("\n".join(new_py), "a.py", "exec")

    def test_fix_gives_back_a_file_it_would_break(self):
        text = "x = 1\n" + LONG + "\n"
        self.write("a.py", text)
        import rewrap
        with mock.patch.object(rewrap, "rewrap_code", return_value=("def (:\n", 1, [])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.fix_lines(self.base), 1)
        with open(os.path.join(self.root, "a.py"), encoding="utf-8") as f:
            self.assertEqual(f.read(), text)
        self.assertIn("a.py : recoupe annulée, le fichier ne se lisait plus", out.getvalue())

    def test_the_editor_hook_judges_the_edited_file_only(self):
        self.install_check()
        self.write("a.py", "x = 1\n" + LONG + "\n")
        self.write("b.md", "Court.\n")
        hook = lambda path: subprocess.run([sys.executable, os.path.join(self.root, "tests", "check.py"), "--hook"],
                                           input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}),
                                           capture_output=True, text=True, cwd=self.tmp.name)
        r = hook(os.path.join(self.root, "a.py"))
        self.assertEqual(r.returncode, 2, r.stderr)           # code 2 : Claude Code montre stderr
        self.assertIn("a.py:2 (121 caractères)", r.stderr)
        self.assertIn("--lines --fix", r.stderr)
        r = hook(os.path.join(self.root, "b.md"))             # autre fichier, sans faute : rien
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        r = hook(os.path.join(self.tmp.name, "hors-du-depot.py"))
        self.assertEqual((r.returncode, r.stderr), (0, ""))

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
        with mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "check_rules", return_value=[]), \
                mock.patch.object(check, "run_bench") as bench, mock.patch.object(check, "run_ui") as ui, \
                mock.patch.object(check, "journal_path", return_value=os.path.join(self.tmp.name, "journal.log")), \
                mock.patch.object(check, "reexec_in_venv"), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(["--ui"]), 1)
        bench.assert_not_called()
        ui.assert_not_called()
        lines = out.getvalue().strip().splitlines()
        self.assertTrue(lines[-1].startswith("Contrôles : ÉCHEC : Lignes : b.mjs:2 (journal gardé : "), lines[-1])
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
        argv = ["--ui", "tests/ui/smoke.test.mjs", "--name", "zz-aucun-test"]
        with tempfile.TemporaryDirectory(prefix="qwen-check-test-") as tmp, \
                mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "check_line_length", return_value=[]), \
                mock.patch.object(check, "check_rules", return_value=[]), \
                mock.patch.object(check, "run_bench") as bench, mock.patch.object(check, "run_ui") as ui, \
                mock.patch.object(check, "journal_path", return_value=os.path.join(tmp, "journal.log")), \
                mock.patch.object(check, "reexec_in_venv"), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(check.main(argv), 1)
        bench.assert_not_called()                     # rien n'est lancé, ni le banc ni Chrome
        ui.assert_not_called()
        self.assertIn("aucun test ne correspond au motif « zz-aucun-test »", out.getvalue())
        self.assertTrue(out.getvalue().strip().splitlines()[-1].startswith(
            "Contrôles : ÉCHEC : Interface : motif « zz-aucun-test » sans test (journal gardé : "))
        args = check.parse_args(["--ui", "tests/ui/smoke.test.mjs", "--name", "Révéler"])   # vise un test : lancé
        with mock.patch.object(check, "run_ui", return_value=(True, [], [])) as ui, \
                mock.patch.object(check, "run_bench", return_value=(True, [], [])), \
                mock.patch.object(check, "sensitive_notice"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check.run_checks(args)[0], {})
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


class UiRepeatTest(unittest.TestCase):
    """--ui <fichiers> --repeat N repasse N fois chaque fichier (un échec intermittent se montre) ; chaque passage a sa
    ligne, et un seul passage en échec fait échouer le contrôle."""
    def test_each_file_runs_n_times(self):
        runs = []

        def fake(f, flags, env):
            runs.append(f)
            bad = f == "b.test.mjs" and runs.count(f) == 2
            return f"ℹ tests 1\nℹ pass {0 if bad else 1}\nℹ fail {1 if bad else 0}", int(bad)
        with mock.patch.object(check, "run_ui_file", fake):
            ok, lines, faults = check.run_ui(["a.test.mjs", "b.test.mjs"], jobs=1, repeat=3)
        self.assertEqual(sorted(runs), ["a.test.mjs"] * 3 + ["b.test.mjs"] * 3)
        self.assertFalse(ok)
        self.assertEqual(faults, ["b.test.mjs (passage 2/3)"])
        self.assertIn("Interface : b.test.mjs (passage 2/3) : 1 tests, 1 en échec", "\n".join(lines))
        self.assertTrue(any("6 fichier(s), 6 tests, 5 réussis, 1 en échec" in line for line in lines), lines)
        self.assertEqual(check.parse_args(["--ui", "x.test.mjs", "--repeat", "3"]).repeat, 3)

    def test_a_todo_test_is_counted_without_failing(self):
        out = "ℹ tests 3\nℹ pass 2\nℹ fail 0\nℹ todo 1"
        with mock.patch.object(check, "run_ui_file", return_value=(out, 0)):
            ok, lines, _ = check.run_ui(["a.test.mjs"], jobs=1)
        self.assertTrue(ok)
        self.assertIn("Interface : a.test.mjs : 3 tests, 0 en échec, 1 à faire", "\n".join(lines))


class NoticeBaseTest(RepoCase):
    """L'avis « zone sensible » compte depuis le dernier commit (le ticket en cours, arbre de travail et fichiers
    nouveaux compris ; décision du 25/10/2026), quelle que soit la branche : un ticket n'hérite plus des mots des
    tickets d'avant. Il compte aussi la suppression de données et nomme la fonction (ou la route) de chaque ligne."""
    def notice(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            check.sensitive_notice(check.ticket_base())
        return out.getvalue()

    def commit(self, message):
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", message)

    def test_only_the_ticket_in_progress_counts(self):
        sh(self.root, "git", "branch", "dev")
        sh(self.root, "git", "checkout", "-q", "-b", "worktree-groupe-x")             # branche de groupe, partie de dev
        self.write("tools/vieux.js", "inPrivate();\n")
        self.commit("ticket d'avant, sur la même branche")
        self.assertEqual(self.notice(), "", "ticket d'avant commité : plus d'avis")
        self.write("tools/neuf.js", "privState;\n")                 # fichier nouveau, pas encore ajouté
        self.write("tools/vieux.js", "inPrivate();\nconst x = 1;\n")
        notice = self.notice()
        self.assertIn("tools/neuf.js", notice)
        self.assertIn("privState", notice)
        self.assertNotIn("vieux.js", notice)
        sh(self.root, "git", "checkout", "-q", "--detach")              # tête détachée (CI d'une PR) : pareil
        self.assertIn("tools/neuf.js", self.notice())

    def test_deleting_data_is_sensitive_too(self):
        self.write("tools/ui/index.html", "<script>\nfunction discardItem(it){\n  keep(it);\n}\n</script>\n")
        self.commit("interface")
        self.write("tools/ui/index.html", "<script>\nfunction discardItem(it){\n  keep(it);\n  commitDiscard(it);\n}\n"
                                          "</script>\n")
        notice = self.notice()
        self.assertIn("passe bogues /code-review requise", notice)
        self.assertIn("discardItem (commitDiscard)", notice)

    def test_the_notice_names_the_function_or_route_of_each_line(self):
        before = ["def sort_image(action, name):",
                  "    return 200, {}",
                  "",
                  "class H:",
                  "    def do_POST(self, path):",
                  "        if path in (\"/api/keep\", \"/api/other\"):",
                  "            return sort_image(path, None)",
                  "        return 404",
                  ""]
        self.write("tools/launch.py", "\n".join(before))
        self.commit("serveur")
        after = before[:1] + ["    delete_output(name)"] + before[1:6] + ["            secret(None)"] + before[6:]
        self.write("tools/launch.py", "\n".join(after))
        notice = self.notice()
        self.assertIn("tools/launch.py : sort_image (delete_output)", notice)
        self.assertIn("H.do_POST [/api/keep, /api/other] (secret()", notice)

    def test_outside_git_there_is_no_notice(self):
        with mock.patch.object(check, "git", side_effect=OSError("git absent")):
            self.assertIsNone(check.ticket_base())


class QuickTest(RepoCase):
    """--quick saute le banc quand aucun .py n'a changé depuis le dernier commit, même si la branche en a changé depuis
    main (sur dev et sur une branche de groupe, c'est toujours le cas) ; un .py modifié ou nouveau le relance."""
    def bench_pattern(self):
        args = check.parse_args(["--quick"])
        with mock.patch.object(check, "check_python", return_value=[]), \
                mock.patch.object(check, "check_js", return_value=[]), \
                mock.patch.object(check, "check_line_length", return_value=[]), \
                mock.patch.object(check, "check_rules", return_value=[]), \
                mock.patch.object(check, "run_bench", return_value=(True, [], [])) as bench, \
                mock.patch.object(check, "sensitive_notice"), contextlib.redirect_stdout(io.StringIO()):
            check.run_checks(args)
        bench.assert_called_once()
        return bench.call_args.args[0] if bench.call_args.args else None

    def test_quick_compares_to_the_last_commit(self):
        sh(self.root, "git", "checkout", "-q", "-b", "dev")
        self.write("tools/a.py", "x = 1\n")
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", "un .py changé depuis main")
        self.assertEqual(self.bench_pattern(), "test_public_repo.py", "rien depuis le dernier commit : banc sauté")
        self.write("tools/a.py", "x = 2\n")
        self.assertIsNone(self.bench_pattern(), "un .py modifié : banc entier")
        sh(self.root, "git", "checkout", "--", "tools/a.py")
        self.write("tests/test_neuf.py", "y = 1\n")
        self.assertIsNone(self.bench_pattern(), "un .py nouveau : banc entier")


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


class MainTest(RepoCase):
    """Fin d'un contrôle : la dernière ligne récapitule les comptes à citer (banc, interface) ; les lignes de pile de
    Node restent dans le journal ; un passage en échec garde son journal sous un nom horodaté ; un contrôle vert sur
    un arbre identique, aux mêmes options, ne se relance pas (sauf --force)."""
    CITED = ["Banc : Ran 3 tests in 0.512s", "Banc : OK",
             "Interface : 2 fichier(s), 5 tests, 5 réussis, 0 en échec (9 s)"]

    def setUp(self):
        super().setUp()
        self.journal = os.path.join(self.tmp.name, "journal.log")
        self.write("a.py", "x = 1\n")
        self.write(".gitignore", "ignore.txt\n")
        sh(self.root, "git", "add", ".")
        sh(self.root, "git", *GIT_USER, "commit", "-q", "-m", "code")
        self.failed, self.printed, self.runs = {}, "", 0
        for target, value in (("journal_path", self.journal), ("reexec_in_venv", None)):
            p = mock.patch.object(check, target, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def fake_checks(self, args):
        self.runs += 1
        print(self.printed)
        return self.failed, self.CITED

    def main(self, *argv):
        with mock.patch.object(check, "run_checks", self.fake_checks), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = check.main(list(argv))
        return code, out.getvalue()

    def kept(self):
        folder = os.path.join(self.tmp.name, check.FAILURES_DIR)
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def test_the_last_line_gives_the_counts_to_cite(self):
        code, out = self.main()
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().splitlines()[-1], "Contrôles : OK (" + " ; ".join(self.CITED) + ")")

    def test_node_stack_lines_stay_in_the_journal(self):
        self.printed = "Error: boum\n    at f (file:///x.test.mjs:1:2)\n    at async g (node:internal/x:3:4)\nsuite"
        _, out = self.main()
        self.assertNotIn("at f (file", out)
        self.assertIn("Error: boum\nsuite", out)
        self.assertIn("2 ligne(s) de pile Node masquée(s)", out)
        with open(self.journal, encoding="utf-8") as f:
            self.assertIn("    at f (file:///x.test.mjs:1:2)", f.read())

    def test_a_failed_run_keeps_its_journal(self):
        self.main()
        self.assertEqual(self.kept(), [], "un passage vert ne garde rien")
        self.failed, self.printed = {"Banc": ["test_x"]}, "sortie du passage en échec"
        code, out = self.main("--force")                    # même arbre que le passage vert : forcé
        self.assertEqual(code, 1)
        kept = self.kept()
        self.assertEqual(len(kept), 1)
        path = os.path.join(self.tmp.name, check.FAILURES_DIR, kept[0])
        last = out.strip().splitlines()[-1]
        self.assertTrue(last.startswith("Contrôles : ÉCHEC : Banc : test_x ("), last)
        self.assertTrue(last.endswith(f"(journal gardé : {path})"), last)
        with open(path, encoding="utf-8") as f:
            self.assertIn("sortie du passage en échec", f.read())
        for _ in range(check.FAILURES_KEPT + 2):
            self.main("--force")
        self.assertEqual(len(self.kept()), check.FAILURES_KEPT, "les plus vieux sont retirés")

    def test_a_green_state_is_not_checked_twice(self):
        self.main()
        code, out = self.main()
        self.assertEqual((code, self.runs), (0, 1), out)
        self.assertIn("déjà vert sur cet état (passage du ", out)
        self.assertEqual(out.strip().splitlines()[-1], "Contrôles : OK (" + " ; ".join(self.CITED) + ")")
        self.main("--quick")                                  # autres options : relancé
        self.assertEqual(self.runs, 2)
        self.main("--force")
        self.assertEqual(self.runs, 3)
        self.write("ignore.txt", "ignoré par git\n")         # fichier ignoré : même état
        self.main()
        self.assertEqual(self.runs, 3)
        self.write("a.py", "x = 2\n")                        # fichier changé : relancé
        self.main()
        self.assertEqual(self.runs, 4)
        self.write("neuf.py", "y = 1\n")                      # fichier nouveau : relancé
        self.main()
        self.assertEqual(self.runs, 5)
        sh(self.root, "git", *GIT_USER, "commit", "-q", "--allow-empty", "-m", "rien")   # autre commit : relancé
        self.main()
        self.assertEqual(self.runs, 6)
        self.failed = {"Banc": ["test_x"]}                  # un échec forcé efface le vert du même arbre
        self.main("--force")
        self.assertEqual(self.runs, 7)
        self.failed = {}
        self.main()
        self.assertEqual(self.runs, 8, "« déjà vert » après un échec sur le même arbre")
        self.failed = {"Banc": ["test_x"]}                  # un échec n'est pas enregistré
        self.write("a.py", "x = 3\n")
        self.main()
        self.main()
        self.assertEqual(self.runs, 10)
        self.assertEqual(sh(self.root, "git", "status", "--porcelain"), " M a.py\n?? neuf.py\n", "index réel intact")


class UsesShowTest(RepoCase):
    """--uses <mot> liste les usages d'un nom dans tools/, tests/, le README et la carte du code ; --show <nom> imprime
    le corps de la fonction (Python ou JavaScript de index.html) que --map situe."""
    def run_main(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = check.main(list(argv))
        return code, out.getvalue()

    def test_uses_lists_every_use_in_the_followed_places(self):
        self.write("tools/launch.py", "def sort_image(a):\n    return a\n\nsort_images = 1\n")
        self.write("tests/test_a.py", "from launch import sort_image\n")
        self.write("README.md", "Le tri passe par `sort_image`.\n")
        self.write("docs/agents/carte-du-code.md", "- `sort_image(action, name)` : tri\n")
        self.write("ailleurs/notes.md", "sort_image\n")
        code, out = self.run_main("--uses", "sort_image")
        self.assertEqual(code, 0)
        self.assertEqual([l.split(":")[0] + ":" + l.split(":")[1] for l in out.strip().splitlines()],
                         ["README.md:1", "docs/agents/carte-du-code.md:1", "tests/test_a.py:1", "tools/launch.py:1"])

    def test_show_prints_the_body_of_a_function(self):
        self.write("tools/launch.py", "\n".join(["import os", "", "def first(a):", "    if a:",
                                                 "        return {'k': '}'}", "    return 2", "", "",
                                                 "class H:", "    def do_GET(self):", "        return 1", "",
                                                 "def after():", "    pass", ""]))
        self.write("tools/ui/index.html", "\n".join(["<script>", "function showImage(el, src) {",
                                                     "  const s = '}{';  // }", "  if (src) { el.src = src; }",
                                                     "}", "function other() {}", "</script>", ""]))
        code, out = self.run_main("--show", "first")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["tools/launch.py:3", "def first(a):", "    if a:",
                                            "        return {'k': '}'}", "    return 2"])
        self.assertEqual(self.run_main("--show", "do_GET")[1].splitlines(),
                         ["tools/launch.py:10", "    def do_GET(self):", "        return 1"])
        self.assertEqual(self.run_main("--show", "showImage")[1].splitlines(),
                         ["tools/ui/index.html:2", "function showImage(el, src) {", "  const s = '}{';  // }",
                          "  if (src) { el.src = src; }", "}"])
        code, out = self.run_main("--show", "absente")
        self.assertEqual(code, 1)
        self.assertIn("absente : introuvable", out)


class HelpTest(unittest.TestCase):
    """check.py --help porte le détail que CLAUDE.md ne recopie plus : commandes, quand lancer quoi, ce qu'on cite,
    délais, options."""
    def test_the_help_says_how_to_use_the_checks(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "check.py"), "--help"], capture_output=True, text=True,
                           env=dict(os.environ, QWEN_CHECK_REEXEC="1"))
        self.assertEqual(r.returncode, 0, r.stderr)
        for said in ("--no-bench --ui tests/ui/x.test.mjs", "jamais « node --test » nu", "déjà vert sur cet état",
                     "« Ran N tests … »", "« timeout » sous macOS", "QWEN_UI_JOBS", "--repeat", "--lines --fix",
                     "--hook", "zone sensible", "--uses", "--show", ".githooks/pre-commit", "checks.yml"):
            self.assertIn(said, r.stdout)


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
