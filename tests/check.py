"""Contrôles du projet en une commande (bibliothèque standard seulement) :

  venv/bin/python tests/check.py            # compilation Python, JavaScript, lignes, banc de test
  venv/bin/python tests/check.py --no-bench # sans le banc (quelques secondes)
  venv/bin/python tests/check.py --ui       # en plus, les tests d'interface (Chrome sans écran, en local seulement)
  venv/bin/python tests/check.py --ui tests/ui/x.test.mjs   # un seul fichier d'interface (ou plusieurs)
  venv/bin/python tests/check.py --quick    # banc sauté si aucun .py n'a changé depuis la base (jamais en CI)
  python3 tests/check.py --lines            # seulement la longueur des lignes ajoutées (moins d'une seconde)
  python3 tests/check.py --link-venv        # worktree : liens vers venv et les notes du dossier principal, hook

« Suivi » veut dire ici suivi par git, ou nouveau et pas encore ajouté (fichier non suivi que .gitignore n'exclut pas) :
un fichier créé passe les contrôles avant son premier commit.

1. compile chaque fichier .py suivi (sans écrire de .pyc) ;
2. passe à « node --check » chaque bloc <script> de tools/ui/index.html (un bloc sur une seule ligne compris) et chaque
   fichier .js ou .mjs suivi ; échoue si un bloc ouvert n'a pas été extrait ; refuse une adresse donnée à la main à
   une image des visionneuses, de la zone de résultat ou du dessin ($('vImg').src=…, IMAGE_IDS) : elles passent par
   showImage ;
3. vérifie que les lignes ajoutées depuis la base (git merge-base HEAD origin/main, arbre de travail compris ; toutes
   celles d'un fichier nouveau) des fichiers .py, .md, .mjs et .js suivis ont 120 caractères au plus, hors tableaux et
   blocs de code Markdown ; base introuvable : un avis, et le contrôle passe ; --lines ne fait que ce contrôle, et
   --lines --cached juge l'index (ce que le prochain commit enregistre : hook .githooks/pre-commit) ;
   si l'un de ces trois contrôles échoue, check.py s'arrête là, sans lancer le banc ni l'interface ;
4. lance le banc (unittest discover -s tests), recopie telles quelles sa ligne « Ran N tests … » et son verdict, et
   affiche sa durée ; avec --quick et aucun .py changé depuis la base (non suivis compris ; sans base, le banc tourne),
   seul tests/test_public_repo.py tourne ;
5. avec --ui : les tests d'interface tests/ui/*.test.mjs, ou les seuls fichiers donnés (pilote Chrome, voir
   tests/ui/driver.mjs), un fichier après l'autre, chacun avec sa durée, en même temps que le banc : chacun sert le
   serveur sur un port libre, depuis son propre dossier temporaire (bench.start()), et l'interface dans un autre
   processus (tests/ui/serve.py) ;
6. avis, sans échec, « zone sensible : passe bogues /code-review requise » quand une ligne ajoutée depuis la base
   dans tools/ touche l'incognito ou l'espace privé (SENSITIVE).

La sortie complète va aussi dans un journal (chemin imprimé à la fin) ; la dernière ligne récapitule les fautes
(fichier:ligne, test du banc, fichier d'interface), pour qu'une sortie coupée par tail les montre encore.

Le Python des contrôles est celui du venv du dépôt (venv/ à la racine, sinon celui du dossier principal quand on est
dans un worktree), sinon l'interpréteur qui lance ce script (cas de la CI) : check.py se relance de lui-même avec le
bon. Code de sortie non nul au moindre échec.
"""
import argparse, concurrent.futures, glob, os, re, signal, subprocess, sys, tempfile, time

import rules                                          # tests/rules.py : règles mécaniques, index de la carte

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join("Scripts", "python.exe") if os.name == "nt" else os.path.join("bin", "python")
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
LINE_MAX = 120                                       # caractères au plus par ligne ajoutée (CODING_STANDARDS.md)
LINE_FILES = ("*.py", "*.md", "*.mjs", "*.js")
# mots d'une ligne ajoutée qui demandent la passe bogues de /code-review (confidentialité : incognito, espace privé)
SENSITIVE = ("localStorage", "incognito", "inPrivate", "privState", "asideInput", "secret(", "/api/private/",
             "private/")
# images de l'interface que seul showImage remplit (sinon l'image d'avant reste à l'écran jusqu'au chargement)
IMAGE_IDS = ("vImg", "vBg", "ivImg", "stageImg", "paintImg")
IMAGE_SRC_RE = re.compile(r"\$\(\s*['\"](" + "|".join(IMAGE_IDS) + r")['\"]\s*\)\.src\s*=(?!=)")
# notes non suivies du dossier principal, reliées dans chaque worktree par --link-venv (et chaque fichier de
# docs/agents/, sauf la carte du code, qui est suivie)
NOTES = ("CLAUDE.md", "ETAT_DU_PROJET.md", "travail", "docs/specs")
AGENT_NOTES, CODE_MAP = "docs/agents", "carte-du-code.md"
HOOKS = ".githooks"                                  # hooks versionnés (core.hooksPath), posés par --link-venv
MAPPED = ("tools/launch.py", "tools/ui/index.html")  # fichiers que la carte du code décrit (--map en donne l'index)
UI_TESTS = "tests/ui/*.test.mjs"
# délais des tests d'interface : par test (ms, node --test-timeout ; QWEN_UI_TEST_TIMEOUT le change), par fichier (s)
UI_TEST_TIMEOUT = int(os.environ.get("QWEN_UI_TEST_TIMEOUT") or 180000)
UI_FILE_TIMEOUT = 1200
UI_WAIT_LOADED = 30000                               # attente par défaut du pilote quand le banc tourne en même temps
SHOWN_FAULTS = 12                                    # fautes nommées au plus par contrôle dans la dernière ligne


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def new_files(*patterns):
    """Fichiers nouveaux, pas encore ajoutés à git et non exclus par .gitignore."""
    return git("ls-files", "--others", "--exclude-standard", "--", *patterns).splitlines()


def checked_files(*patterns):
    """Fichiers suivis par git et fichiers nouveaux (new_files), présents sur le disque."""
    names = dict.fromkeys(git("ls-files", "--", *patterns).splitlines() + new_files(*patterns))
    return [f for f in names if os.path.exists(os.path.join(ROOT, f))]


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


def link_to_main(main, rel):
    """Lien relatif ROOT/rel -> main/rel. Un lien qui s'ouvre est gardé, un lien cassé est refait, un fichier ou un
    dossier réel n'est jamais remplacé (il est signalé). Renvoie le message à afficher, ou None si rien n'a changé."""
    here, target = os.path.join(ROOT, rel), os.path.join(main, rel)
    if os.path.islink(here) and os.path.exists(here):
        return None
    if os.path.lexists(here) and not os.path.islink(here):
        return (f"{rel} : un fichier réel est déjà là, gardé tel quel : le comparer à celui du dossier principal, "
                "puis le supprimer et relancer --link-venv")
    broken = os.path.islink(here)
    try:
        if broken:
            os.remove(here)
        os.makedirs(os.path.dirname(here), exist_ok=True)
        # chemins réels des deux côtés : un dossier atteint par un lien (/tmp sous macOS) fausserait les « .. »
        os.symlink(os.path.relpath(os.path.join(os.path.realpath(main), rel), os.path.realpath(os.path.dirname(here))),
                   here, target_is_directory=os.path.isdir(target))
    except OSError as e:                              # Windows sans le droit de créer des liens
        return f"{rel} : lien impossible ({e})"
    return f"{rel} : lien {'cassé refait' if broken else 'créé'} vers le dossier principal"


def note_names(main):
    """Notes non suivies présentes dans le dossier principal : NOTES, puis les fichiers de docs/agents/ (sauf la carte
    du code)."""
    names = [n for n in NOTES if os.path.lexists(os.path.join(main, n))]
    agents = os.path.join(main, AGENT_NOTES)
    if os.path.isdir(agents):
        names += [f"{AGENT_NOTES}/{n}" for n in sorted(os.listdir(agents)) if n != CODE_MAP and not n.startswith(".")]
    return names


def link_hooks():
    """Hooks versionnés (HOOKS) activés pour le dépôt (core.hooksPath, réglage commun à tous ses worktrees, chemin
    relatif : chacun prend les siens) ; un autre réglage déjà posé est gardé."""
    try:
        current = git("config", "--get", "core.hooksPath").strip()
    except subprocess.CalledProcessError:
        current = ""
    if current == HOOKS:
        return
    if current:
        print(f"hooks : core.hooksPath vaut déjà « {current} », gardé ({HOOKS}/pre-commit n'est pas activé)")
        return
    hooks_dir = git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    own = sorted(n for n in os.listdir(os.path.join(hooks_dir, "hooks")) if not n.endswith(".sample")) \
        if os.path.isdir(os.path.join(hooks_dir, "hooks")) else []
    if own:                                        # core.hooksPath les ferait ignorer sans le dire
        print(f"hooks : .git/hooks contient {', '.join(own)}, qui ne tourneraient plus : core.hooksPath pas posé ; "
              f"les déplacer dans {HOOKS}/ puis relancer --link-venv")
        return
    git("config", "core.hooksPath", HOOKS)
    print(f"hooks : {HOOKS}/pre-commit activé (refuse un commit qui ajoute une ligne de plus de {LINE_MAX} caractères)")


def link_venv():
    """Dans un worktree : liens relatifs venv -> venv du dossier principal et vers ses notes non suivies
    (note_names) ; partout : le hook avant commit (link_hooks). Rien d'absolu n'est écrit."""
    main = main_checkout()
    if not main:
        print("hors d'un dépôt git : rien à faire", file=sys.stderr)
        return 1
    status = 0
    if not os.path.samefile(main, ROOT):
        here = os.path.join(ROOT, "venv")
        if not os.path.lexists(here) and not os.path.isfile(os.path.join(main, "venv", VENV_PY)):
            print("pas de venv dans le dossier principal du dépôt : lancer d'abord l'installation (README)",
                  file=sys.stderr)
            status = 1
        else:
            if os.path.isdir(here) and not os.path.islink(here):       # un vrai venv dans ce worktree : il marche
                print("venv existe déjà ici : dossier, rien à faire")
            else:
                print(link_to_main(main, "venv") or "venv existe déjà ici : lien, rien à faire")
        for rel in note_names(main):
            message = link_to_main(main, rel)
            if message:
                print(message)
    link_hooks()
    return status


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
    """Compile chaque .py suivi : liste des fautes (fichier:ligne)."""
    files = checked_files("*.py")
    bad = []
    for f in files:
        with open(os.path.join(ROOT, f), "rb") as fh:
            src = fh.read()
        try:
            compile(src, f, "exec")
        except SyntaxError as e:
            print(f"  {f}:{e.lineno}: {e.msg}")
            bad.append(f"{f}:{e.lineno}")
    print(f"Python : {len(files)} fichiers compilés, {len(bad)} en erreur")
    return bad


def node_check(path, label, first_line=1):
    """node --check : None si le fichier passe, sinon sa faute (label:ligne ; first_line : ligne de label où commence
    le fichier vérifié, pour un bloc extrait de index.html)."""
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    except OSError:
        print("  node introuvable : installer Node.js (le contrôle JavaScript ne peut pas être sauté)")
        return "node introuvable"
    if r.returncode == 0:
        return None
    out = (r.stderr or r.stdout).strip()
    print(f"  {label} :\n" + "\n".join("    " + l for l in out.splitlines()))
    m = re.search(r":(\d+)\s*$", out.splitlines()[0]) if out else None
    return f"{label}:{int(m.group(1)) + first_line - 1}" if m else label


def check_js():
    """node --check des blocs <script> de index.html et des .js/.mjs suivis, adresses d'images : liste des fautes."""
    with open(os.path.join(ROOT, "tools", "ui", "index.html"), encoding="utf-8") as f:
        html = f.read()
    bad = []
    opened = len(re.findall(r"<script\b", html, re.I))
    found = list(SCRIPT_RE.finditer(html))
    if not len(found) == opened > 0:                  # un bloc sauté sans prévenir est un échec
        print(f"  index.html : {opened} balise(s) <script> ouvertes, {len(found)} bloc(s) extraits")
        bad.append("tools/ui/index.html (blocs <script>)")
    blocks = [(m.start(2), m.group(2)) for m in found     # ni script externe, ni bloc de données (type JSON…)
              if "src=" not in m.group(1) and not re.search(r"type=[\"']?(?!text/javascript|module)", m.group(1))]
    with tempfile.TemporaryDirectory(prefix="qwen-check-") as tmp:
        for i, (pos, code) in enumerate(blocks, 1):
            line = html.count("\n", 0, pos) + 1
            path = os.path.join(tmp, f"index-bloc{i}-ligne{line}.js")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            bad.append(node_check(path, "tools/ui/index.html", line))
    files = checked_files("*.js", "*.mjs")
    for f in files:
        bad.append(node_check(os.path.join(ROOT, f), f))
    for line in image_src_lines(html):
        print(f"  index.html:{line} : adresse donnée à la main à une image affichée : passer par showImage")
        bad.append(f"tools/ui/index.html:{line}")
    bad = [b for b in bad if b]
    print(f"JavaScript : {len(blocks)} bloc(s) <script> de index.html et {len(files)} fichier(s) vérifiés"
          + (" : ÉCHEC" if bad else ""))
    return bad


def image_src_lines(html):
    """Numéros des lignes de html qui donnent une adresse à la main à une image de IMAGE_IDS."""
    return [k for k, text in enumerate(html.splitlines(), 1) if IMAGE_SRC_RE.search(text)]


def merge_base():
    """Commit où la branche s'est séparée de origin/main, ou None (pas de origin/main, historique absent)."""
    try:
        return git("merge-base", "HEAD", "origin/main").strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def added_lines(base, *paths, cached=False):
    """Lignes ajoutées depuis base (arbre de travail compris ; toutes celles d'un fichier nouveau, new_files) :
    {fichier : ensemble de numéros de ligne}. cached : celles de l'index, sans les fichiers non ajoutés."""
    out = git("diff", *(["--cached"] if cached else []), "--unified=0", "--no-color", "--no-ext-diff", base, "--",
              *paths)
    added, current = {}, None
    for line in out.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@") and current:
            m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            added.setdefault(current, set()).update(range(start, start + count))
    for f in [] if cached else new_files(*paths):    # fichier nouveau : git diff ne le voit pas, tout est ajouté
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                added[f] = set(range(1, len(fh.read().splitlines()) + 1))
        except (OSError, UnicodeDecodeError):
            pass
    return added


def file_lines(f, cached=False):
    """Lignes du fichier f (relatif à ROOT) : sur le disque, ou dans l'index (cached) ; None s'il n'y est pas."""
    if cached:
        try:
            return git("show", f":{f}").splitlines()
        except subprocess.CalledProcessError:
            return None
    try:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            return fh.read().splitlines()
    except OSError:
        return None


def check_line_length(base, cached=False):
    """Lignes ajoutées depuis base de plus de LINE_MAX caractères (pas octets), dans les .py, .md, .mjs et .js suivis
    (tools/ui/index.html n'en est pas) ; hors tableaux Markdown (ligne qui commence par |) et blocs ``` d'un .md.
    cached : lignes de l'index (hook avant commit). Liste des fautes (fichier:ligne)."""
    if not base:
        print(f"Lignes : avis : base introuvable (git merge-base HEAD origin/main), {LINE_MAX} caractères non vérifiés")
        return []
    bad = []
    for f, numbers in sorted(added_lines(base, *LINE_FILES, cached=cached).items()):
        lines = file_lines(f, cached)
        if lines is None:
            continue
        fenced = False
        for k, text in enumerate(lines, 1):
            md = f.endswith(".md")
            if md and text.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if k in numbers and not (md and (fenced or text.lstrip().startswith("|"))) and len(text) > LINE_MAX:
                print(f"  {f}:{k} ({len(text)} caractères)")
                bad.append(f"{f}:{k}")
    print(f"Lignes : {len(bad)} ligne(s) ajoutée(s) de plus de {LINE_MAX} caractères" + (" : ÉCHEC" if bad else ""))
    if any(".md:" in b for b in bad):
        print("  Markdown : python3 tests/rewrap.py <fichier> recoupe ces lignes sans toucher au reste")
    return bad


def read(f):
    with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
        return fh.read()


def check_rules(base):
    """Règles mécaniques de CODING_STANDARDS.md (tests/rules.py) sur les lignes ajoutées depuis base : variable
    JavaScript qui porte l'id d'un élément (index.html), « .every( » ou « all( » sans test de longueur, promesse prise
    pour un booléen, HOLD=<nom> repris d'un fichier de test à l'autre, attente de « running » sans HOLD ni SLOW
    (tests) ; et sur toute la carte du code : chaque nom cité existe dans le code. Liste des fautes (fichier:ligne)."""
    bad = []

    def report(f, found):
        for k, why in found:
            print(f"  {f}:{k} : {why}")
            bad.append(f"{f}:{k}")

    if base:
        added = added_lines(base, "tools/ui/index.html", "tests/")
        report("tools/ui/index.html", rules.id_shadows(read("tools/ui/index.html"),
                                                       added.get("tools/ui/index.html", set())))
        for f in checked_files("tests/*.mjs"):           # pathspec git : « * » traverse les dossiers
            lines = read(f).splitlines()
            report(f, rules.unchecked_every(lines, added.get(f, set())) + rules.unawaited_then(lines,
                                                                                               added.get(f, set())))
        for f in checked_files("tests/*.py"):
            if f == "tests/test_rules.py":                # ses exemples fautifs sont voulus
                continue
            src = read(f)
            report(f, rules.unchecked_all(src.splitlines(), added.get(f, set())))
            try:
                report(f, rules.running_without_hold(src, added.get(f, set())))
            except SyntaxError:                         # déjà signalé par le contrôle Python
                pass
        texts = {f: read(f) for f in checked_files("tests/test_*.py", "tests/ui/*.test.mjs")}
        for f, k, why in rules.hold_reuse(texts, {f: added.get(f, set()) for f in texts}):
            report(f, [(k, why)])
    else:
        print("Règles : avis : base introuvable, règles des lignes ajoutées non vérifiées")
    code = "\n".join(read(f) for f in checked_files("*.py", "*.html", "*.mjs", "*.js"))
    report(f"{AGENT_NOTES}/{CODE_MAP}", rules.missing_map_names(read(f"{AGENT_NOTES}/{CODE_MAP}"), code))
    print(f"Règles : {len(bad)} faute(s) (CODING_STANDARDS.md, noms de la carte du code)" + (" : ÉCHEC" if bad else ""))
    return bad


def print_index(pattern):
    """Index des fonctions, classes et constantes de MAPPED (fichier:ligne nom), filtré par pattern (sous-chaîne)."""
    for f in MAPPED:
        for k, name in rules.code_index(f, read(f)):
            if pattern.lower() in name.lower():
                print(f"{f}:{k} {name}")
    return 0


def sensitive_notice(base):
    """Avis (jamais un échec) quand une ligne ajoutée depuis base dans le code de l'application (tools/, hors .md)
    touche une zone sensible (SENSITIVE) : le ticket demande alors la passe bogues de /code-review. Les tests, qui
    nomment ces zones pour les vérifier, ne déclenchent pas l'avis."""
    if not base:
        return
    hits, current = {}, None
    for line in git("diff", "--unified=0", "--no-color", "--no-ext-diff", base, "--", "tools/",
                    ":!*.md").splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and current:
            for word in SENSITIVE:
                if word in line:
                    hits.setdefault(word, set()).add(current)
    for f in new_files("tools/", ":!*.md"):          # fichier nouveau : toutes ses lignes sont ajoutées
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for word in SENSITIVE:
            if word in text:
                hits.setdefault(word, set()).add(f)
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


def seconds(t):
    """Durée lisible : « 42 s », « 3 min 05 s »."""
    t = round(t)
    return f"{t // 60} min {t % 60:02d} s" if t >= 60 else f"{t} s"


def run_bench(pattern=None):
    """Banc (unittest discover -s tests, ou les seuls fichiers pattern) : (réussi, lignes à afficher, fautes : tests
    en échec)."""
    start = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", *(["-p", pattern] if pattern
                                                                                        else [])],
                       cwd=ROOT, capture_output=True, text=True)
    out = r.stderr + r.stdout
    lines = out.strip().splitlines()
    ran = next((l for l in reversed(lines) if l.startswith("Ran ")), "Ran ? tests : ligne introuvable")
    verdict = next((l for l in reversed(lines) if l.startswith(("OK", "FAILED"))), "verdict introuvable")
    label = "Banc" + (f" ({pattern})" if pattern else "")
    shown = [out.rstrip()] if r.returncode else []
    faults = list(dict.fromkeys(m.group(2) for m in re.finditer(r"^(FAIL|ERROR): \S+ \((\S+)\)", out, re.M)))
    if r.returncode and not faults:
        faults = ["banc"]
    return r.returncode == 0, shown + [f"{label} : {ran}", f"{label} : {verdict}",
                                       f"{label} : durée {seconds(time.monotonic() - start)}"], faults


def ui_counts(out):
    """Compteurs de la fin d'une sortie de node --test (« ℹ tests 12 », « ℹ pass 12 »…) : {nom : nombre}."""
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^\S* ?(tests|pass|fail|cancelled|skipped|todo) (\d+)$",
                                                             out, re.M)}


def ui_files(files):
    """Fichiers d'interface à lancer : ceux donnés, ou tous (UI_TESTS), relatifs à ROOT."""
    return files or sorted(os.path.relpath(f, ROOT).replace(os.sep, "/") for f in glob.glob(os.path.join(ROOT,
                                                                                                         UI_TESTS)))


def ui_titles(files):
    """Titres des tests (test('…', …)) des fichiers d'interface, lus dans leur source."""
    titles = []
    for f in files:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            src = fh.read()
        for m in re.finditer(r"\btest\(\s*(['\"`])((?:\\.|(?!\1).)*)\1", src, re.S):
            titles.append(re.sub(r"\\(.)", r"\1", m.group(2)))
    return titles


def run_ui(files, name=None, wait=None):
    """Tests d'interface (tous, ou les seuls files ; name : motif des noms de tests, --test-name-pattern), un fichier
    après l'autre, chacun dans son groupe de processus : un test dépasse UI_TEST_TIMEOUT, un fichier
    UI_FILE_TIMEOUT, et Chrome et le banc sont arrêtés à la fin de chaque fichier, même bloqué. wait : délai par
    défaut des attentes du pilote (QWEN_UI_WAIT). Renvoie (réussi, lignes à afficher, fautes : fichiers en échec)."""
    files = ui_files(files)
    env = dict(os.environ, PYTHON=sys.executable, **({"QWEN_UI_WAIT": str(wait)} if wait else {}))
    env.pop("NODE_TEST_CONTEXT", None)                # lancé depuis un test node : sinon node --test ne lance rien
    flags = ["--test-concurrency=1", "--test-reporter=spec", f"--test-timeout={UI_TEST_TIMEOUT}", "--test-force-exit",
             *([f"--test-name-pattern={name}"] if name else [])]
    shown, faults, total, start = [], [], {}, time.monotonic()
    for f in files:
        began = time.monotonic()
        try:
            proc = subprocess.Popen(["node", "--test", *flags, f], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                    start_new_session=os.name != "nt")
        except OSError:
            return False, ["Interface : node introuvable"], ["node introuvable"]
        try:
            out, _ = proc.communicate(timeout=UI_FILE_TIMEOUT)
        except subprocess.TimeoutExpired:
            stop_group(proc)
            out = proc.communicate()[0] + f"\nfichier arrêté au bout de {seconds(UI_FILE_TIMEOUT)}"
        stop_group(proc)                              # restes du fichier (Chrome, banc) : arrêtés dans tous les cas
        out = out.rstrip()
        counts = ui_counts(out)
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
        if proc.returncode or not counts.get("tests"):    # aucun test lancé : pas une réussite
            faults.append(f)
            shown.append(out)
        failed = counts.get("fail", 0) + counts.get("cancelled", 0)
        shown.append(f"Interface : {f} : {counts.get('tests', '?')} tests, {failed} en échec "
                     f"({seconds(time.monotonic() - began)})")
    failed = total.get("fail", 0) + total.get("cancelled", 0)
    shown.append(f"Interface : {len(files)} fichier(s), {total.get('tests', 0)} tests, {total.get('pass', 0)} "
                 f"réussis, {failed} en échec ({seconds(time.monotonic() - start)})")
    return not faults, shown + ["Interface : " + ("ÉCHEC" if faults else "OK")], faults


def stop_group(proc):
    """Arrête le groupe de processus de proc (node et ce qu'il a lancé : Chrome, serveur du banc) : SIGTERM d'abord,
    pour que le banc supprime son dossier temporaire, SIGKILL à ce qui reste après 5 s."""
    if os.name == "nt":
        if proc.poll() is None:
            proc.kill()
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        for _ in range(50):
            proc.poll()                            # récupère node s'il a fini : un zombie ferait attendre 5 s pour rien
            try:
                os.killpg(proc.pid, 0)
            except (ProcessLookupError, PermissionError):
                return
            time.sleep(0.1)


class Tee:
    """Sortie écrite à la fois à l'écran et dans le journal."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)
        return len(text)

    def flush(self):
        for s in self.streams:
            s.flush()


def journal_path():
    """Journal de la sortie complète : QWEN_CHECK_JOURNAL, sinon dans le dossier temporaire du système, un par dossier
    de travail."""
    return os.environ.get("QWEN_CHECK_JOURNAL") or os.path.join(tempfile.gettempdir(),
                                                                f"qwen-check-{os.path.basename(ROOT)}.log")


def summary(failed):
    """Dernière ligne de la sortie : OK, ou chaque contrôle en échec avec ses fautes (SHOWN_FAULTS au plus)."""
    if not failed:
        return "Contrôles : OK"
    parts = []
    for name, faults in failed.items():
        more = f" et {len(faults) - SHOWN_FAULTS} autre(s)" if len(faults) > SHOWN_FAULTS else ""
        parts.append(f"{name} : {', '.join(faults[:SHOWN_FAULTS])}{more}")
    return "Contrôles : ÉCHEC : " + " ; ".join(parts)


def run_checks(args):
    """Contrôles statiques, puis banc et interface s'ils passent : {contrôle : fautes} des contrôles en échec."""
    base = merge_base()
    failed = {}
    for name, check in (("Python", check_python), ("JavaScript", check_js),
                        ("Lignes", lambda: check_line_length(base)), ("Règles", lambda: check_rules(base))):
        faults = check()
        if faults:
            failed[name] = faults
    if failed:
        print("Banc et interface : pas lancés (contrôles ci-dessus en échec : les corriger d'abord)")
        return failed
    if args.ui is not None and args.name:
        try:
            found = any(re.search(args.name, t) for t in ui_titles(ui_files(args.ui)))
        except re.error:                           # syntaxe propre à JavaScript : node jugera le motif
            found = True
        if not found:
            print(f"Interface : aucun test ne correspond au motif « {args.name} » : rien n'est lancé")
            return {"Interface": [f"motif « {args.name} » sans test"]}
    jobs = []                                         # banc et interface : en parallèle (bancs indépendants)
    if args.no_bench:
        pass
    elif args.quick and not py_changed(base):
        print("Banc : sauté (--quick, aucun .py changé depuis la base) ; seul le test du dépôt public tourne")
        jobs.append(("Banc", lambda: run_bench("test_public_repo.py")))
    else:
        jobs.append(("Banc", run_bench))
    if args.ui is not None:                           # banc en même temps : machine chargée, attentes allongées
        wait = UI_WAIT_LOADED if jobs else None
        jobs.append(("Interface", lambda: run_ui(args.ui, args.name, wait)))
    with concurrent.futures.ThreadPoolExecutor(max(len(jobs), 1)) as pool:
        futures = [(name, pool.submit(job)) for name, job in jobs]
        for name, future in futures:
            ok, lines, faults = future.result()
            print("\n".join(lines))
            if not ok:
                failed[name] = faults
    sensitive_notice(base)
    return failed


def main():
    ap = argparse.ArgumentParser(description="Contrôles du projet (compilation, JavaScript, lignes, banc, interface)")
    ap.add_argument("--no-bench", action="store_true", help="sauter le banc de test")
    ap.add_argument("--quick", action="store_true",
                    help="sauter le banc si aucun .py n'a changé depuis la base (le test du dépôt public tourne)")
    ap.add_argument("--ui", nargs="*", metavar="FICHIER",
                    help="lancer aussi les tests d'interface (Chrome, en local), tous ou les seuls fichiers donnés")
    ap.add_argument("--name", metavar="MOTIF", help="avec --ui : seuls les tests dont le nom correspond (expression "
                    "régulière) ; échoue tout de suite si aucun ne correspond")
    ap.add_argument("--lines", action="store_true",
                    help=f"seulement la longueur des lignes ajoutées depuis la base ({LINE_MAX} caractères)")
    ap.add_argument("--cached", action="store_true", help="avec --lines : juger l'index (hook avant commit)")
    ap.add_argument("--link-venv", action="store_true",
                    help="worktree : liens vers venv et les notes du dossier principal ; hook avant commit")
    ap.add_argument("--map", nargs="?", const="", metavar="NOM",
                    help="index fonction → ligne de launch.py et index.html (les noms qui contiennent NOM)")
    args = ap.parse_args()
    if args.link_venv:
        return link_venv()
    if args.map is not None:
        return print_index(args.map)
    if args.lines:                                    # bibliothèque standard seulement : pas de relance dans le venv
        return 1 if check_line_length(merge_base(), cached=args.cached) else 0
    reexec_in_venv()
    path, screen = journal_path(), sys.stdout
    with open(path, "w", encoding="utf-8") as log:
        sys.stdout = Tee(screen, log)
        try:
            failed = run_checks(args)
            print(f"Journal complet : {path}")
            print(summary(failed))
        finally:
            sys.stdout = screen
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
