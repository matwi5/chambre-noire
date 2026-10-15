"""Contrôles du projet en une commande (bibliothèque standard seulement) :

  venv/bin/python tests/check.py            # compilation Python, JavaScript, banc de test
  venv/bin/python tests/check.py --no-bench # sans le banc (quelques secondes)
  venv/bin/python tests/check.py --ui       # en plus, les tests d'interface (Chrome sans écran, en local seulement)
  python3 tests/check.py --link-venv        # worktree : crée le lien venv vers le venv du dossier principal

1. compile chaque fichier .py suivi par git (sans écrire de .pyc) ;
2. passe à « node --check » chaque bloc <script> de tools/ui/index.html (un bloc sur une seule ligne compris) et chaque
   fichier .js ou .mjs suivi ; échoue si un bloc ouvert n'a pas été extrait ;
3. lance le banc (unittest discover -s tests) et recopie telles quelles sa ligne « Ran N tests … » et son verdict ;
4. avec --ui : node --test tests/ui/ (pilote Chrome, voir tests/ui/driver.mjs).

Le Python des contrôles est celui du venv du dépôt (venv/ à la racine, sinon celui du dossier principal quand on est
dans un worktree), sinon l'interpréteur qui lance ce script (cas de la CI) : check.py se relance de lui-même avec le
bon. Code de sortie non nul au moindre échec.
"""
import argparse, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join("Scripts", "python.exe") if os.name == "nt" else os.path.join("bin", "python")
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)


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


def check_bench():
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT,
                       capture_output=True, text=True)
    out = r.stderr + r.stdout
    if r.returncode:
        print(out.rstrip())
    lines = out.strip().splitlines()
    ran = next((l for l in reversed(lines) if l.startswith("Ran ")), "Ran ? tests : ligne introuvable")
    verdict = next((l for l in reversed(lines) if l.startswith(("OK", "FAILED"))), "verdict introuvable")
    print(f"Banc : {ran}\nBanc : {verdict}")
    return r.returncode == 0


def check_ui():
    env = dict(os.environ, PYTHON=sys.executable)
    try:
        r = subprocess.run(["node", "--test", "--test-reporter=spec", "tests/ui/"], cwd=ROOT, env=env,
                           capture_output=True, text=True)
    except OSError:
        print("Interface : node introuvable")
        return False
    out = (r.stdout + r.stderr).rstrip()
    if r.returncode:
        print(out)
    else:
        print("\n".join(l for l in out.splitlines() if l.lstrip("ℹ ").startswith(("tests ", "pass ", "fail "))))
    print("Interface : " + ("OK" if r.returncode == 0 else "ÉCHEC"))
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Contrôles du projet (compilation, JavaScript, banc, interface)")
    ap.add_argument("--no-bench", action="store_true", help="sauter le banc de test")
    ap.add_argument("--ui", action="store_true", help="lancer aussi les tests d'interface (Chrome, en local)")
    ap.add_argument("--link-venv", action="store_true", help="worktree : lier venv au venv du dossier principal")
    args = ap.parse_args()
    if args.link_venv:
        return link_venv()
    reexec_in_venv()
    results = [check_python(), check_js()]
    if not args.no_bench:
        results.append(check_bench())
    if args.ui:
        results.append(check_ui())
    print("Contrôles : " + ("OK" if all(results) else "ÉCHEC"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
