"""Contrôles du projet en une commande (bibliothèque standard seulement) :

  venv/bin/python tests/check.py            # compilation Python, JavaScript, banc de test
  venv/bin/python tests/check.py --no-bench # sans le banc (quelques secondes)
  venv/bin/python tests/check.py --ui       # en plus, les tests d'interface (Chrome sans écran, en local seulement)
  venv/bin/python tests/check.py --ui tests/ui/x.test.mjs   # un seul fichier d'interface (ou plusieurs)
  venv/bin/python tests/check.py --quick    # banc sauté si aucun .py n'a changé depuis la base (jamais en CI)
  python3 tests/check.py --link-venv        # worktree : crée le lien venv vers le venv du dossier principal

1. compile chaque fichier .py suivi par git (sans écrire de .pyc) ;
2. passe à « node --check » chaque bloc <script> de tools/ui/index.html (un bloc sur une seule ligne compris) et chaque
   fichier .js ou .mjs suivi ; échoue si un bloc ouvert n'a pas été extrait ;
3. vérifie que les lignes ajoutées depuis la base (git merge-base HEAD origin/main, arbre de travail compris) des
   fichiers .py, .md, .mjs et .js suivis ont 120 caractères au plus, hors tableaux et blocs de code Markdown ; base
   introuvable : un avis, et le contrôle passe ;
4. lance le banc (unittest discover -s tests) et recopie telles quelles sa ligne « Ran N tests … » et son verdict ;
   avec --quick et aucun .py changé depuis la base (non suivis compris ; sans base, le banc tourne), seul
   tests/test_public_repo.py tourne ;
5. avec --ui : les tests d'interface tests/ui/*.test.mjs, ou les seuls fichiers donnés (pilote Chrome, voir
   tests/ui/driver.mjs), en même temps que le banc : chacun sert le serveur sur un port libre, depuis son propre
   dossier temporaire (bench.start()), et l'interface dans un autre processus (tests/ui/serve.py) ;
6. avis, sans échec, « zone sensible : passe bogues /code-review requise » quand une ligne de code ajoutée depuis la
   base touche l'incognito ou l'espace privé (SENSITIVE).

Le Python des contrôles est celui du venv du dépôt (venv/ à la racine, sinon celui du dossier principal quand on est
dans un worktree), sinon l'interpréteur qui lance ce script (cas de la CI) : check.py se relance de lui-même avec le
bon. Code de sortie non nul au moindre échec.
"""
import argparse, concurrent.futures, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join("Scripts", "python.exe") if os.name == "nt" else os.path.join("bin", "python")
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
LINE_MAX = 120                                       # caractères au plus par ligne ajoutée (CODING_STANDARDS.md)
LINE_FILES = ("*.py", "*.md", "*.mjs", "*.js")
# mots d'une ligne ajoutée qui demandent la passe bogues de /code-review (confidentialité : incognito, espace privé)
SENSITIVE = ("localStorage", "incognito", "inPrivate", "privState", "asideInput", "secret(", "/api/private/",
             "private/")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def main_checkout():
    """Dossier principal du dépôt (celui qui porte .git), vu depuis la racine ou depuis un worktree ; None hors git."""
    try:
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return os.path.dirname(common)


def find_venv():
    """venv/ de ce dossier, sinon celui du dossier principal (un worktree n'a pas le sien : venv/ n'est pas suivi)."""
    for base in (ROOT, main_checkout()):
        if base and os.path.isfile(os.path.join(base, "venv", VENV_PY)):
            return os.path.join(base, "venv")
    return None


def link_venv():
    """Crée dans ce worktree un lien relatif venv -> venv du dossier principal (rien d'absolu n'est écrit)."""
    here = os.path.join(ROOT, "venv")
    if os.path.lexists(here):
        print(f"venv existe déjà ici : {'lien' if os.path.islink(here) else 'dossier'}, rien à faire")
        return 0
    main = main_checkout()
    target = main and os.path.join(main, "venv")
    if not target or not os.path.isfile(os.path.join(target, VENV_PY)) or os.path.samefile(main, ROOT):
        print("pas de venv dans le dossier principal du dépôt : lancer d'abord l'installation (README)", file=sys.stderr)
        return 1
    os.symlink(os.path.relpath(target, ROOT), here, target_is_directory=True)
    print("lien venv créé vers le venv du dossier principal")
    return 0


def reexec_in_venv():
    """Relance ce script avec le Python du venv s'il en existe un et que ce n'est pas déjà lui."""
    venv = find_venv()
    if not venv or os.environ.get("QWEN_CHECK_REEXEC"):
        return
    if os.path.realpath(sys.prefix) == os.path.realpath(venv):
        return
    os.environ["QWEN_CHECK_REEXEC"] = "1"
    py = os.path.join(venv, VENV_PY)
    sys.stdout.flush()
    os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])


def check_python():
    files = [f for f in git("ls-files", "*.py").splitlines() if os.path.exists(os.path.join(ROOT, f))]
    bad = []
    for f in files:
        with open(os.path.join(ROOT, f), "rb") as fh:
            src = fh.read()
        try:
            compile(src, f, "exec")
        except SyntaxError as e:
            bad.append(f"{f}:{e.lineno}: {e.msg}")
    for line in bad:
        print("  " + line)
    print(f"Python : {len(files)} fichiers compilés, {len(bad)} en erreur")
    return not bad


def node_check(path, label):
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    except OSError:
        print("  node introuvable : installer Node.js (le contrôle JavaScript ne peut pas être sauté)")
        return False
    if r.returncode:
        print(f"  {label} :\n" + "\n".join("    " + l for l in (r.stderr or r.stdout).strip().splitlines()))
    return r.returncode == 0


def check_js():
    with open(os.path.join(ROOT, "tools", "ui", "index.html"), encoding="utf-8") as f:
        html = f.read()
    opened = len(re.findall(r"<script\b", html, re.I))
    found = list(SCRIPT_RE.finditer(html))
    ok = len(found) == opened > 0                    # un bloc sauté sans prévenir est un échec
    if not ok:
        print(f"  index.html : {opened} balise(s) <script> ouvertes, {len(found)} bloc(s) extraits")
    blocks = [(m.start(), m.group(2)) for m in found     # ni script externe, ni bloc de données (type JSON…)
              if "src=" not in m.group(1) and not re.search(r"type=[\"']?(?!text/javascript|module)", m.group(1))]
    with tempfile.TemporaryDirectory(prefix="qwen-check-") as tmp:
        for i, (pos, code) in enumerate(blocks, 1):
            line = html.count("\n", 0, pos) + 1
            path = os.path.join(tmp, f"index-bloc{i}-ligne{line}.js")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            ok &= node_check(path, f"index.html, bloc <script> {i} (ligne {line})")
    files = [f for f in git("ls-files", "*.js", "*.mjs").splitlines() if os.path.exists(os.path.join(ROOT, f))]
    for f in files:
        ok &= node_check(os.path.join(ROOT, f), f)
    print(f"JavaScript : {len(blocks)} bloc(s) <script> de index.html et {len(files)} fichier(s) vérifiés"
          + ("" if ok else " : ÉCHEC"))
    return ok


def merge_base():
    """Commit où la branche s'est séparée de origin/main, ou None (pas de origin/main, historique absent)."""
    try:
        return git("merge-base", "HEAD", "origin/main").strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def added_lines(base, *paths):
    """Lignes ajoutées depuis base (arbre de travail compris) : {fichier : ensemble de numéros de ligne}."""
    out = git("diff", "--unified=0", "--no-color", "--no-ext-diff", base, "--", *paths)
    added, current = {}, None
    for line in out.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@") and current:
            m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            added.setdefault(current, set()).update(range(start, start + count))
    return added


def check_line_length(base):
    """Lignes ajoutées depuis base de plus de LINE_MAX caractères (pas octets), dans les .py, .md, .mjs et .js suivis
    (tools/ui/index.html n'en est pas) ; hors tableaux Markdown (ligne qui commence par |) et blocs ``` d'un .md."""
    if not base:
        print(f"Lignes : avis : base introuvable (git merge-base HEAD origin/main), {LINE_MAX} caractères non vérifiés")
        return True
    bad = []
    for f, numbers in sorted(added_lines(base, *LINE_FILES).items()):
        if not os.path.exists(os.path.join(ROOT, f)):
            continue
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        fenced = False
        for k, text in enumerate(lines, 1):
            md = f.endswith(".md")
            if md and text.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if k in numbers and not (md and (fenced or text.lstrip().startswith("|"))) and len(text) > LINE_MAX:
                bad.append(f"{f}:{k} ({len(text)} caractères)")
    for line in bad:
        print("  " + line)
    print(f"Lignes : {len(bad)} ligne(s) ajoutée(s) de plus de {LINE_MAX} caractères" + (" : ÉCHEC" if bad else ""))
    return not bad


def sensitive_notice(base):
    """Avis (jamais un échec) quand une ligne ajoutée depuis base, hors documentation (.md) et hors ce fichier, touche
    une zone sensible (SENSITIVE) : le ticket demande alors la passe bogues de /code-review (CLAUDE.md global)."""
    if not base:
        return
    hits, current = {}, None
    for line in git("diff", "--unified=0", "--no-color", "--no-ext-diff", base, "--", ".", ":!*.md",
                    ":!tests/check.py").splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and current:
            for word in SENSITIVE:
                if word in line:
                    hits.setdefault(word, set()).add(current)
    if hits:
        print("Avis : zone sensible : passe bogues /code-review requise ("
              + " ; ".join(f"{w} dans {', '.join(sorted(fs))}" for w, fs in hits.items()) + ")")


def py_changed(base):
    """Vrai si un .py a changé depuis base (arbre de travail et fichiers non suivis compris), ou sans base."""
    if not base:
        return True
    changed = git("diff", "--name-only", base, "--", "*.py") + git("ls-files", "--others", "--exclude-standard",
                                                                   "*.py")
    return bool(changed.strip())


def run_bench(pattern=None):
    """Banc (unittest discover -s tests, ou les seuls fichiers pattern) : (réussi, lignes à afficher)."""
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", *(["-p", pattern] if pattern
                                                                                        else [])],
                       cwd=ROOT, capture_output=True, text=True)
    out = r.stderr + r.stdout
    lines = out.strip().splitlines()
    ran = next((l for l in reversed(lines) if l.startswith("Ran ")), "Ran ? tests : ligne introuvable")
    verdict = next((l for l in reversed(lines) if l.startswith(("OK", "FAILED"))), "verdict introuvable")
    label = "Banc" + (f" ({pattern})" if pattern else "")
    shown = [out.rstrip()] if r.returncode else []
    return r.returncode == 0, shown + [f"{label} : {ran}", f"{label} : {verdict}"]


def run_ui(files):
    """Tests d'interface (tous, ou les seuls files) : (réussi, lignes à afficher)."""
    env = dict(os.environ, PYTHON=sys.executable)
    try:
        r = subprocess.run(["node", "--test", "--test-concurrency=1", "--test-reporter=spec",
                            *(files or ["tests/ui/*.test.mjs"])], cwd=ROOT, env=env, capture_output=True, text=True)
    except OSError:
        return False, ["Interface : node introuvable"]
    out = (r.stdout + r.stderr).rstrip()
    shown = [out] if r.returncode else [l for l in out.splitlines()
                                        if l.lstrip("ℹ ").startswith(("tests ", "pass ", "fail "))]
    return r.returncode == 0, shown + ["Interface : " + ("OK" if r.returncode == 0 else "ÉCHEC")]


def main():
    ap = argparse.ArgumentParser(description="Contrôles du projet (compilation, JavaScript, banc, interface)")
    ap.add_argument("--no-bench", action="store_true", help="sauter le banc de test")
    ap.add_argument("--quick", action="store_true",
                    help="sauter le banc si aucun .py n'a changé depuis la base (le test du dépôt public tourne)")
    ap.add_argument("--ui", nargs="*", metavar="FICHIER",
                    help="lancer aussi les tests d'interface (Chrome, en local), tous ou les seuls fichiers donnés")
    ap.add_argument("--link-venv", action="store_true", help="worktree : lier venv au venv du dossier principal")
    args = ap.parse_args()
    if args.link_venv:
        return link_venv()
    reexec_in_venv()
    base = merge_base()
    results = [check_python(), check_js(), check_line_length(base)]
    jobs = []                                         # banc et interface : en parallèle (bancs indépendants)
    if args.no_bench:
        pass
    elif args.quick and not py_changed(base):
        print("Banc : sauté (--quick, aucun .py changé depuis la base) ; seul le test du dépôt public tourne")
        jobs.append(lambda: run_bench("test_public_repo.py"))
    else:
        jobs.append(run_bench)
    if args.ui is not None:
        jobs.append(lambda: run_ui(args.ui))
    with concurrent.futures.ThreadPoolExecutor(max(len(jobs), 1)) as pool:
        for ok, lines in [f.result() for f in [pool.submit(job) for job in jobs]]:
            print("\n".join(lines))
            results.append(ok)
    sensitive_notice(base)
    print("Contrôles : " + ("OK" if all(results) else "ÉCHEC"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
