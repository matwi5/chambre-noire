"""tests/rewrap.py : une ligne trop longue d'un paragraphe ou d'une puce est coupée sans rien changer d'autre ; blocs
de code, tableaux, titres et lignes vides restent tels quels ; sur le README actuel, les seules lignes ajoutées depuis
la base (le cas par défaut) ne changent rien, et --all ne change que la coupe des lignes."""
import os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rewrap  # noqa: E402

WORDS = " ".join(f"mot{i}" for i in range(40))      # 40 mots, ≈ 230 caractères


def structure(text):
    """Ce qui ne doit jamais bouger : lignes vides, titres, tableaux et blocs de code, dans l'ordre."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append(line)
        elif fenced or not line.strip() or re.match(r"\s*(#|\|)", line):
            out.append(line)
    return out


class RewrapTest(unittest.TestCase):
    def test_a_paragraph_a_long_bullet_and_a_code_block(self):
        code = "    " + "x" * 130
        text = "\n".join(["# Titre", "", "Début " + WORDS, "suite du paragraphe", "", "- " + WORDS,
                          "  suite de la puce", "1. " + WORDS, "", "```text", code, "```", "",
                          "| a | " + "b" * 130 + " |", ""])
        new, cuts, left = rewrap.rewrap(text)
        self.assertEqual((cuts, left), (3, []))
        lines = new.split("\n")
        self.assertGreater(len(lines), len(text.split("\n")))
        self.assertTrue(all(len(l) <= 120 for l in lines if l not in (code, "| a | " + "b" * 130 + " |")))
        self.assertEqual(structure(new), structure(text))
        self.assertEqual(new.split(), text.split())           # mêmes mots, dans le même ordre
        blank = [k for k, l in enumerate(lines) if not l]
        paragraph = lines[blank[0] + 1:blank[1]]    # la suite sans retrait, bout repris par la ligne d'après
        self.assertTrue(len(paragraph) > 1 and all(not l[0].isspace() for l in paragraph), paragraph)
        self.assertTrue(paragraph[-1].endswith("suite du paragraphe"), paragraph)
        start = lines.index(next(l for l in lines if l.startswith("1. ")))
        bullet = lines[blank[1] + 1:start]
        self.assertTrue(bullet[0].startswith("- mot0") and len(bullet) > 1)
        self.assertTrue(all(l.startswith("  ") and not l[2].isspace() for l in bullet[1:]), bullet)
        self.assertTrue(bullet[-1].endswith("suite de la puce"), bullet)
        numbered = lines[start:blank[2]]
        self.assertTrue(all(l.startswith("   mot") for l in numbered[1:]) and len(numbered) > 1, numbered)
        self.assertEqual(lines[lines.index("```text") + 1], code)   # bloc de code : intact

    def test_the_tail_stays_alone_before_another_block(self):
        line = "Texte " + WORDS
        for after in ("", "- une puce", "    code en retrait", "# Titre"):
            new = rewrap.rewrap(line + "\n" + after)[0].split("\n")
            self.assertEqual(new[-1], after)
            self.assertEqual(" ".join(new[:-1]), line)

    def test_a_cut_never_starts_a_line_with_a_block_mark(self):
        line = "a" * 110 + " - b 1. c # d > e | f " + "g " * 20
        new, cuts, _ = rewrap.rewrap(line)
        self.assertEqual(cuts, 1)
        for l in new.split("\n")[1:]:
            self.assertNotRegex(l, r"^(- |\d+\. |#|>|\|)", new)

    def test_code_spans_are_kept_whole_when_possible(self):
        line = "texte " * 15 + "`une commande avec des espaces` " + "fin " * 10
        new, _, _ = rewrap.rewrap(line)
        self.assertTrue(any("`une commande avec des espaces`" in l for l in new.split("\n")), new)

    def test_a_line_without_spaces_is_left_and_reported(self):
        line = "https://exemple.org/" + "x" * 130
        self.assertEqual(rewrap.rewrap("a\n" + line + "\n"), ("a\n" + line + "\n", 0, [2]))

    def test_code_keeps_strings_and_single_quoted_docstrings_whole(self):
        py = "\n".join(["def f():",
                        "    '" + WORDS + "'",                              # docstring entre simples guillemets
                        "    SAMPLE = '''début",
                        "# " + WORDS,                                       # dans une chaîne : pas un commentaire
                        "'''",
                        "    # " + WORDS,                                   # vrai commentaire : coupé
                        "    return SAMPLE", ""])
        new, cuts, left = rewrap.rewrap_code("a.py", py, None)
        self.assertEqual((cuts, left), (1, [2, 4]))
        compile(new, "a.py", "exec")
        self.assertIn("# " + WORDS, new.split("\n"))
        js = "\n".join(["const page = `", "// " + WORDS, "`;", "  // " + WORDS, "const s = '// " + WORDS + "';", ""])
        new, cuts, left = rewrap.rewrap_code("a.mjs", js, None)
        self.assertEqual((cuts, left), (1, [2, 5]))
        self.assertEqual(new.split("\n")[1], "// " + WORDS, "ligne d'un gabarit : laissée")

    def test_the_current_readme(self):
        with open(os.path.join(HERE, "..", "README.md"), encoding="utf-8") as f:
            readme = f.read()
        with tempfile.TemporaryDirectory(prefix="qwen-rewrap-test-") as tmp:
            for rel in ("tests/rewrap.py", "tests/check.py", "tests/rules.py"):
                os.makedirs(os.path.join(tmp, "tests"), exist_ok=True)
                shutil.copy2(os.path.join(HERE, "..", rel), os.path.join(tmp, rel))
            with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as f:
                f.write(readme)
            for args in (("init", "-q"), ("add", "."), ("-c", "user.name=banc", "-c", "user.email=banc@example.com",
                                                        "commit", "-q", "-m", "base"),
                         ("update-ref", "refs/remotes/origin/main", "HEAD")):
                subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True)
            r = subprocess.run([sys.executable, "tests/rewrap.py", "README.md"], cwd=tmp, capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(tmp, "README.md"), encoding="utf-8") as f:
                self.assertEqual(f.read(), readme, "lignes de la base recoupées")
        new, cuts, _ = rewrap.rewrap(readme)                  # --all : seules les lignes trop longues bougent
        self.assertGreater(cuts, 0)
        self.assertEqual(structure(new), structure(readme))
        self.assertEqual(new.split(), readme.split())
        self.assertEqual(rewrap.rewrap(new)[0], new)          # une deuxième passe ne change plus rien


class DocstringIndentTest(unittest.TestCase):
    def test_a_recut_docstring_line_keeps_its_own_indent(self):
        """Une ligne en retrait dans une docstring de module (la suite d'un point numéroté) garde ce retrait : le hook
        qui recoupe seul la prose la remettait au bord gauche."""
        text = '"""Module.\n\n1. point\n   ' + " ".join(["mot"] * 40) + '\n"""\nx = 1\n'
        new, cuts, left = rewrap.rewrap_code("m.py", text, None)
        self.assertEqual((cuts, left), (1, []))
        body = new.split("\n")[3:-3]
        self.assertGreater(len(body), 1)
        self.assertTrue(all(line.startswith("   mot") for line in body), body)


if __name__ == "__main__":
    unittest.main()
