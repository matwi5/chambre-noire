"""Contrôles du projet en une commande (bibliothèque standard seulement ; c'est aussi la CI GitHub,
.github/workflows/checks.yml, sur chaque pull request vers main et chaque envoi sur dev) :

  venv/bin/python tests/check.py            # contrôle complet : compilation, JavaScript, lignes, règles, banc
  venv/bin/python tests/check.py --ui       # en plus, tous les tests d'interface (Chrome sans écran, en local)
  venv/bin/python tests/check.py --no-bench --ui tests/ui/x.test.mjs [--name <motif>]   # boucle de travail
  venv/bin/python tests/check.py --quick    # banc sauté si aucun .py n'a changé depuis le dernier commit
  venv/bin/python tests/check.py --ui tests/ui/x.test.mjs --repeat 3   # un fichier passé 3 fois (intermittent)
  venv/bin/python tests/check.py --failed   # seuls les tests rouges du dernier passage, rejoués
  venv/bin/python tests/check.py --at dev --ui tests/ui/x.test.mjs [--name <motif>]   # tests actuels, tools/ de dev
  python3 tests/check.py --lines [--fix]    # longueur des lignes ajoutées seule (moins d'une seconde) ; --fix recoupe
  python3 tests/check.py --link-venv        # worktree : liens vers venv et les notes du dossier principal, hook
  python3 tests/check.py --map <nom> | --show <nom> | --uses <mot>   # situer, lire, chercher sans grep

Quand lancer quoi. Pendant le travail : le seul fichier touché (venv/bin/python -m unittest discover -s tests -p
test_x.py, ou --no-bench --ui tests/ui/x.test.mjs : seul check.py pose le délai par test et arrête Chrome et le banc,
jamais « node --test » nu) ; les fichiers d'interface concernés se trouvent par --uses ou grep. Avant la revue et
avant le commit : le contrôle complet (--ui si l'interface a changé) ; relancé sur un arbre identique aux mêmes
options, il ne repasse pas (« déjà vert sur cet état », avec les lignes à citer ; --force pour relancer). On cite la
dernière ligne telle quelle (« Ran N tests … », totaux de l'interface), jamais un compte de tête. Pas de commande
« timeout » sous macOS : les délais sont ceux de check.py (UI_TEST_TIMEOUT par test, UI_FILE_TIMEOUT par fichier) ou
de l'outil qui lance la commande. Le contrôle complet avec --ui prend quelques minutes (banc et interface en même
temps). Une vérification d'interface nouvelle devient un test de tests/ui/ (pilote driver.mjs), une vérification
ponctuelle passe par la sonde (tests/ui/probe.mjs), jamais par un script jetable ; une vue plus grande que le
téléphone cache des débordements : regarder aussi les captures (page.screenshot, tests/ui/planche.mjs). Le pilote
ouvre la vue du téléphone (chrome.phonePage), d'un PC à la souris ou d'une tablette tactile en hauteur et en largeur
(chrome.newPage(PC | TABLET | TABLET_WIDE), page.setView sans rechargement), appuie, maintient, répète et relâche
une touche avec modificateurs (page.press, keyDown, keyUp) et maintient un appui sur un élément (page.hold puis
page.release) ; la planche capture chaque vue au téléphone, à la tablette en hauteur et en largeur et au PC.

« Suivi » veut dire ici suivi par git, ou nouveau et pas encore ajouté (fichier non suivi que .gitignore n'exclut pas) :
un fichier créé passe les contrôles avant son premier commit.

1. compile chaque fichier .py suivi (sans écrire de .pyc) ;
2. passe à « node --check » chaque bloc <script> de tools/ui/index.html (un bloc sur une seule ligne compris) et chaque
   fichier .js ou .mjs suivi ; échoue si un bloc ouvert n'a pas été extrait ; refuse une adresse donnée à la main à
   une image des visionneuses, de la zone de résultat ou du dessin ($('vImg').src=…, IMAGE_IDS, dont chaque id doit
   exister) : elles passent par showImage ;
3. vérifie que les lignes ajoutées depuis la base (git merge-base HEAD origin/main, arbre de travail compris ; toutes
   celles d'un fichier nouveau) des fichiers .py, .md, .mjs et .js suivis ont 120 caractères au plus, hors tableaux et
   blocs de code Markdown ; base introuvable : un avis, et le contrôle passe ; --lines ne fait que ce contrôle,
   --lines --cached juge l'index (hook .githooks/pre-commit, posé par --link-venv), --lines --fix recoupe les seules
   lignes fautives qui peuvent l'être (Markdown, commentaires, docstrings) et --hook juge le fichier qu'une écriture de
   Claude Code vient de changer, ou après une commande Bash (script, heredoc) les fichiers changés depuis le dernier
   commit (hook PostToolUse de .claude/settings.json, moins d'une seconde) : il recoupe seul la prose trop longue,
   comme --fix, et signale le code trop long (sur stderr, code 2 : un fichier recoupé est à relire avant de l'éditer) ;
4. règles mécaniques de CODING_STANDARDS.md (tests/rules.py, liste à la fin de ce fichier, noms de la carte du code
   compris) : sur les lignes ajoutées, et sur des fichiers entiers pour celles du serveur, des imports et du tri,
   des pages, des aides du pilote et des préfixes de prompt des tests d'interface ;
   si l'un de ces quatre contrôles échoue, check.py s'arrête là, sans lancer le banc ni l'interface ;
5. lance le banc (unittest discover -s tests), recopie telles quelles sa ligne « Ran N tests … » et son verdict, et
   affiche sa durée ; seuls tests/test_public_repo.py et les modules qui lisent un fichier autre qu'un .py
   (bench_readers : l'interface, la carte du code, le README…) tournent quand les .py (suivis et nouveaux, tests
   compris) sont ceux du dernier banc entier vert (empreinte, à côté du journal ; la ligne « Ran N tests » de ce banc
   est citée avec sa date ; décision du 29/10/2026), ou avec --quick et aucun .py changé depuis le dernier commit
   (ticket_base : non suivis compris ; hors git, le banc tourne) ; jamais en CI (CI, GITHUB_ACTIONS : le banc entier,
   toujours), et --force le relance ;
6. avec --ui : les tests d'interface tests/ui/*.test.mjs, ou les seuls fichiers donnés (pilote Chrome, voir
   tests/ui/driver.mjs), UI_JOBS fichiers à la fois (3 par défaut, QWEN_UI_JOBS), chacun avec sa durée, en même
   temps que le banc : chacun son Chrome, et son serveur sur un port libre, depuis son propre dossier temporaire
   (bench.start()), avec l'interface dans un autre processus (tests/ui/serve.py) ; résultats dans l'ordre des
   fichiers ; --name <motif> ne lance que les tests dont le nom correspond (échec tout de suite si aucun, avec les
   titres proches), --repeat N passe chaque fichier N fois ; un test « todo » est compté « à faire », sans échec ; un
   fichier est arrêté à UI_FAIL_CAP tests en échec (5, QWEN_UI_FAIL_CAP ; 0 : sans plafond), et sa ligne le dit : un
   changement de sens fait tomber des dizaines de tests à 30 s chacun ;
   quand seuls des .md ont changé depuis le dernier contrôle vert aux mêmes options (empreinte de tout sauf les .md),
   ni le reste du banc ni l'interface ne repassent : les lignes, les règles et les modules de bench_readers, puis
   les lignes à citer du dernier contrôle qui les a lancés, datées (« (vert du …) ») ;
7. avis, sans échec, « zone sensible : passe bogues /code-review requise » quand une ligne ajoutée dans tools/ depuis
   le dernier commit (ticket_base : le ticket en cours, arbre de travail compris ; donc aucun avis en CI) touche
   l'espace privé ou la suppression de données (SENSITIVE) ; il nomme la fonction (ou la route) de chaque ligne, puis
   celles qui n'ont pas de preuve rouge au journal de tests/mutate.py depuis le dernier commit (un avis : rien ne
   bloque le commit, décision du 29/10/2026). Un indice : la ligne « Zone sensible » du ticket fait foi.

La sortie complète va aussi dans un journal (chemin imprimé à la fin ; les lignes de pile de Node n'y sont qu'à lui) ;
un passage en échec garde le sien sous un nom horodaté (FAILURES_DIR, les FAILURES_KEPT derniers). La dernière ligne
récapitule les fautes (fichier:ligne, test du banc, fichier d'interface), les lignes de résultat à citer et le journal
gardé, pour qu'une sortie coupée par tail les montre encore. Un contrôle vert enregistre l'empreinte de l'arbre et ses
options (green_record, à côté du journal).

Échec du banc ou de l'interface : en fin de passage, chaque fichier d'interface et chaque module du banc en échec
(REPLAY_MAX au plus, ni un fichier arrêté au plafond, ni avec --repeat) est rejoué seul, une fois ; sa faute porte
alors « (intermittent : vert seul) » ou « (reproductible) » dans la dernière ligne. Le contrôle reste en échec (un
test instable se comprend, il ne s'ignore pas), mais un intermittent n'appelle pas un nouveau contrôle complet : le
fichier seul, ou --failed, suffit. Le journal note la charge au départ et à la fin (moyennes de charge, Chrome sans
écran étrangers au contrôle, QWEN_UI_JOBS) ; chaque test rouge va aussi dans un journal persistant, commun aux
worktrees (FAILURE_LOG du dossier temporaire du système : date, dossier, fichier, test, verdict du rejeu, charge),
pour repérer les tests qui reviennent rouges. --failed rejoue seuls les tests rouges du dernier passage (titres des
tests d'interface, méthodes du banc), sans les contrôles statiques ni le rejeu ; il n'enregistre aucun vert.

--at <commit> --ui <fichiers> [--name <motif>] : rejoue des tests d'interface de l'arbre de travail contre l'interface
et le serveur d'un autre commit (comparer à la base, voir si un test aurait vu un bogue) : worktree temporaire du
commit, dossier tests/ de l'arbre de travail copié par-dessus (pilote, banc et tests actuels ; le pilote prend tools/
du worktree), contrôle de l'interface seul (ni contrôles statiques, ni banc ; son journal à part), puis le worktree
retiré, même sur un échec ou une interruption. Code de sortie de ce contrôle.

Le Python des contrôles est celui du venv du dépôt (venv/ à la racine, sinon celui du dossier principal quand on est
dans un worktree), sinon l'interpréteur qui lance ce script (cas de la CI) : check.py se relance de lui-même avec le
bon. Code de sortie non nul au moindre échec.
"""
import argparse, concurrent.futures, difflib, glob, hashlib, json, os, re, shutil, signal, subprocess, sys, tempfile
import threading, time

import rules                                          # tests/rules.py : règles mécaniques, index de la carte

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PY = os.path.join("Scripts", "python.exe") if os.name == "nt" else os.path.join("bin", "python")
SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.S | re.I)
LINE_MAX = 120                                       # caractères au plus par ligne ajoutée (CODING_STANDARDS.md)
LINE_FILES = ("*.py", "*.md", "*.mjs", "*.js")
# mots d'une ligne ajoutée qui demandent la passe bogues de /code-review : confidentialité (incognito, espace privé)
# et suppression de données (Jeter, Supprimer, effacement des fichiers d'une image)
SENSITIVE = ("localStorage", "incognito", "inPrivate", "privState", "asideInput", "secret(", "/api/private/",
             "private/", "/api/discard", "/api/delete", "discardItem", "commitDiscard", "sortTop", "deleteItem",
             "delete_output", "delete_extras", "remove_private_item")
# images de l'interface que seul showImage remplit (sinon l'image d'avant reste à l'écran jusqu'au chargement)
IMAGE_IDS = ("vImg", "vBg", "ivImg", "paintImg", "vBeforeImg")
IMAGE_SRC_RE = re.compile(r"\$\(\s*['\"](" + "|".join(IMAGE_IDS) + r")['\"]\s*\)\.src\s*=(?!=)")
# notes non suivies du dossier principal, reliées dans chaque worktree par --link-venv (et chaque fichier de
# docs/agents/, sauf la carte du code, qui est suivie)
NOTES = ("CLAUDE.md", "ETAT_DU_PROJET.md", "travail", "docs/specs")
AGENT_NOTES, CODE_MAP = "docs/agents", "carte-du-code.md"
HOOKS = ".githooks"                                  # hooks versionnés (core.hooksPath), posés par --link-venv
# fichiers que --map, --show indexent : ceux que la carte du code décrit, le pilote des tests d'interface et le banc
MAPPED = ("tools/launch.py", "tools/ui/index.html", "tests/ui/driver.mjs", "tests/bench.py")
UI_TESTS = "tests/ui/*.test.mjs"
DRIVER = "tests/ui/driver.mjs"                      # pilote des tests d'interface (ses aides)
USES_PLACES = ("tools", "tests", "README.md", f"{AGENT_NOTES}/{CODE_MAP}")   # où --uses cherche
# délais des tests d'interface : par test (ms, node --test-timeout ; QWEN_UI_TEST_TIMEOUT le change), par fichier (s)
UI_TEST_TIMEOUT = int(os.environ.get("QWEN_UI_TEST_TIMEOUT") or 180000)
UI_FILE_TIMEOUT = 1200
UI_WAIT_LOADED = 30000                               # attente par défaut du pilote quand le banc tourne en même temps
# fichiers d'interface lancés à la fois (chacun son Chrome, son banc, ses ports et son dossier temporaire ; QWEN_UI_JOBS
# le change) : un contrôle complet n'attend plus la somme des fichiers (décision du 24/10/2026)
UI_JOBS = max(1, int(os.environ.get("QWEN_UI_JOBS") or 3))
SHOWN_FAULTS = 12                                    # fautes nommées au plus par contrôle dans la dernière ligne
# lignes de résultat recopiées dans la dernière ligne, celles qu'on cite : « Ran N tests … », verdict, totaux
CITED_RE = re.compile(r"(Banc(?: \([^)]*\))? : (?:Ran |OK|FAILED)|Interface : \d+ fichier\(s\), )")
NODE_STACK_RE = re.compile(r"\s+at\s")             # ligne de pile de Node : dans le journal, pas à l'écran
# journaux des passages en échec, gardés à côté du journal (une cause intermittente ne se perd plus)
FAILURES_DIR, FAILURES_KEPT = "qwen-check-echecs", 10
# journal persistant des tests rouges, commun aux worktrees (fichier, test, date, charge, verdict du rejeu) : un test
# qui revient souvent rouge seul sous la charge se repère ; FAILURE_LOG_KEPT lignes au plus
FAILURE_LOG, FAILURE_LOG_KEPT = "qwen-check-echecs.jsonl", 1000
# échecs d'un fichier d'interface avant de l'arrêter (QWEN_UI_FAIL_CAP le change ; 0 : sans plafond) : un changement
# de sens fait tomber des dizaines de tests à 30 s chacun, les premiers suffisent à le voir
UI_FAIL_CAP = int(os.environ.get("QWEN_UI_FAIL_CAP") or 5)
REPLAY_MAX = 3                                       # fichiers ou modules en échec rejoués seuls au plus
# lignes du rapport spec de node --test : test réussi, test en échec (avant le résumé « ℹ tests ») ; arrêt au plafond
PASSED_TEST_RE = re.compile(r"^\s*✔ (.+) \([\d.]+m?s\)$")
FAILED_TEST_RE = re.compile(r"^\s*✖ (.+) \([\d.]+m?s\)$")
CAPPED_RE = re.compile(r"^fichier arrêté après (\d+) échecs", re.M)
# test du banc en échec (« FAIL: test_y (test_x.Classe.test_y) ») : nom de la méthode, identifiant complet
BENCH_FAULT_RE = re.compile(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)", re.M)


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
    relatif : chacun prend les siens) ; un autre réglage déjà posé est gardé, et dit actif s'il mène à un dossier qui
    contient le hook (celui du dossier principal, posé en chemin absolu)."""
    try:
        current = git("config", "--get", "core.hooksPath").strip()
    except subprocess.CalledProcessError:
        current = ""
    if current == HOOKS:
        return
    if current and os.path.isfile(os.path.join(ROOT, os.path.expanduser(current), "pre-commit")):
        print(f"hooks : pre-commit actif (core.hooksPath vaut « {current} », qui le contient)")
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
    for name in missing_image_ids(html):
        print(f"  tests/check.py : IMAGE_IDS cite « {name} », absent de index.html (id=\"{name}\")")
        bad.append(f"tests/check.py (IMAGE_IDS : {name})")
    bad = [b for b in bad if b]
    print(f"JavaScript : {len(blocks)} bloc(s) <script> de index.html et {len(files)} fichier(s) vérifiés"
          + (" : ÉCHEC" if bad else ""))
    return bad


def missing_image_ids(html):
    """Identifiants de IMAGE_IDS qu'aucun élément de html ne porte (la règle de showImage ne garderait plus rien)."""
    return [name for name in IMAGE_IDS if not re.search(rf"""\bid\s*=\s*["']{name}["']""", html)]


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


def long_lines(base, cached=False, paths=LINE_FILES):
    """Lignes ajoutées depuis base de plus de LINE_MAX caractères (pas octets), dans les .py, .md, .mjs et .js suivis
    (tools/ui/index.html n'en est pas ; paths : seuls ces chemins) ; hors tableaux Markdown (ligne qui commence par |)
    et blocs ``` d'un .md. cached : lignes de l'index (hook avant commit). [(fichier, ligne, longueur)]."""
    found = []
    for f, numbers in sorted(added_lines(base, *paths, cached=cached).items()):
        lines = file_lines(f, cached)
        if lines is None or not f.endswith(tuple(p[1:] for p in LINE_FILES)):
            continue
        fenced = False
        for k, text in enumerate(lines, 1):
            md = f.endswith(".md")
            if md and text.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if k in numbers and not (md and (fenced or text.lstrip().startswith("|"))) and len(text) > LINE_MAX:
                found.append((f, k, len(text)))
    return found


def check_line_length(base, cached=False):
    """Lignes trop longues (long_lines), affichées : liste des fautes (fichier:ligne)."""
    if not base:
        print(f"Lignes : avis : base introuvable (git merge-base HEAD origin/main), {LINE_MAX} caractères non vérifiés")
        return []
    bad = []
    for f, k, n in long_lines(base, cached):
        print(f"  {f}:{k} ({n} caractères)")
        bad.append(f"{f}:{k}")
    print(f"Lignes : {len(bad)} ligne(s) ajoutée(s) de plus de {LINE_MAX} caractères" + (" : ÉCHEC" if bad else ""))
    if bad:
        print("  python3 tests/check.py --lines --fix recoupe celles des Markdown, des commentaires et des docstrings")
    return bad


def fix_lines(base):
    """--lines --fix : recoupe les seules lignes trop longues ajoutées (long_lines), sans toucher au reste du
    paragraphe : Markdown par tests/rewrap.py (retrait, puces et citations gardés), commentaire seul sur sa ligne et
    docstring d'un .py, .mjs ou .js (rewrap.rewrap_code) ; puis le contrôle des lignes, qui nomme celles laissées
    (code, chaînes : à recouper à la main). Code de sortie du contrôle."""
    if not base:
        return 1 if check_line_length(base) else 0
    for message in recut(long_lines(base)):
        print(message)
    return 1 if check_line_length(base) else 0


def recut(found):
    """Recoupe les lignes trop longues found ([(fichier, ligne, longueur)], long_lines) qui peuvent l'être (Markdown,
    commentaires, docstrings) ; un fichier qui ne se lirait plus est rendu tel quel. Un message par fichier touché."""
    import rewrap                                     # ici : rewrap importe check
    by_file, messages = {}, []
    for f, k, _ in found:
        by_file.setdefault(f, set()).add(k)
    for f, numbers in sorted(by_file.items()):
        path = os.path.join(ROOT, f)
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        if f.endswith(".md"):
            new, cuts, left = rewrap.rewrap(text, numbers)
        else:
            new, cuts, left = rewrap.rewrap_code(f, text, numbers)
        if new != text:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            broken = fix_breaks(f, path, new)
            if broken:                                # garde-fou : un fichier qui ne se lit plus est rendu tel quel
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
                messages.append(f"{f} : recoupe annulée, le fichier ne se lisait plus ({broken}) : à recouper à la "
                                "main")
                continue
        messages.append(f"{f} : {cuts} ligne(s) recoupée(s)" + (f", {len(left)} à recouper à la main" if left else ""))
    return messages


def fix_breaks(f, path, text):
    """Raison pour laquelle le fichier recoupé ne se lit plus (Python compilé, JavaScript par node --check), ou None."""
    if f.endswith(".py"):
        try:
            compile(text, f, "exec")
        except SyntaxError as e:
            return f"ligne {e.lineno} : {e.msg}"
    elif f.endswith((".js", ".mjs")):
        try:
            r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        except OSError:                                # sans node : rien à vérifier
            return None
        if r.returncode:
            return (r.stderr or r.stdout).strip().splitlines()[0]
    return None


def hook_mark(data):
    """Fichier qui note l'instant où une commande Bash démarre (hook PreToolUse), propre à cet appel d'outil
    (tool_use_id, sinon la session) : le hook d'après n'en juge que les fichiers écrits depuis."""
    key = re.sub(r"[^\w-]", "", str(data.get("tool_use_id") or data.get("session_id") or "sans-id"))[:80]
    return os.path.join(tempfile.gettempdir(), f"qwen-hook-{key}.debut")


def hook_lines(stdin):
    """--hook (hooks de Claude Code, .claude/settings.json) : avant une commande Bash (PreToolUse), note l'instant
    (hook_mark) ; après Edit et Write, juge le seul fichier écrit (tool_input.file_path du JSON reçu) ; après une
    commande Bash (un script, un heredoc : sans file_path), les fichiers .py, .md, .mjs et .js changés depuis le dernier
    commit (non suivis compris) et écrits pendant la commande (date de modification depuis l'instant noté, sinon dans
    la dernière minute), du dépôt de son dossier (cwd du JSON, sinon CLAUDE_PROJECT_DIR) ; un worktree compris, rien
    hors d'un dépôt de ce projet. La prose trop longue (Markdown, commentaires, docstrings) est recoupée sur place
    (recut, comme --lines --fix), sauf pour un sous-agent (agent_id : il ne réécrit pas les fichiers d'un autre, il les
    signale), et le code trop long est signalé. Lignes recoupées et fautes restantes sur stderr avec le code 2 (que
    Claude Code montre : un fichier recoupé est à relire avant de l'éditer de nouveau), sinon 0 sans rien écrire."""
    global ROOT
    try:
        data = json.loads(stdin or "{}")
        given = data.get("tool_input", {}).get("file_path") or ""
        folder = os.path.dirname(os.path.abspath(given)) if given else (data.get("cwd")
                                                                       or os.environ.get("CLAUDE_PROJECT_DIR", ""))
    except (ValueError, AttributeError):
        return 0
    if data.get("hook_event_name") == "PreToolUse":
        try:
            with open(hook_mark(data), "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except OSError:
            pass
        return 0
    if not folder or not os.path.isdir(folder):
        return 0
    r = subprocess.run(["git", "-C", folder, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    root = r.stdout.strip()
    if r.returncode or not os.path.isfile(os.path.join(root, "tests", "check.py")):
        return 0
    ROOT = root
    base = merge_base()
    if not base:
        return 0
    if given:
        paths = [os.path.relpath(os.path.realpath(given), os.path.realpath(root)).replace(os.sep, "/")]
        if paths[0].startswith(".."):
            return 0
    else:                                             # commande Bash : ce qu'elle a écrit, depuis le dernier commit
        try:
            with open(hook_mark(data), encoding="utf-8") as f:
                started = float(f.read()) - 1
            os.remove(hook_mark(data))
        except (OSError, ValueError):
            started = time.time() - 60
        try:
            changed = set(git("diff", "--name-only", "HEAD", "--", *LINE_FILES).splitlines() + new_files(*LINE_FILES))
        except subprocess.CalledProcessError:         # pas encore de commit
            return 0
        paths = sorted(p for p in changed if os.path.exists(os.path.join(ROOT, p))
                       and os.path.getmtime(os.path.join(ROOT, p)) >= started)
    found = long_lines(base, paths=paths) if paths else []
    if not found:
        return 0
    messages = [] if data.get("agent_id") else [m for m in recut(found) if " : 0 ligne(s) recoupée(s)" not in m]
    left = long_lines(base, paths=paths)
    if messages:
        print("Lignes de plus de {} caractères recoupées par le hook (fichier à relire avant de l'éditer) :"
              .format(LINE_MAX), file=sys.stderr)
        for message in messages:
            print(f"  {message}", file=sys.stderr)
    if left:
        print(f"Lignes de plus de {LINE_MAX} caractères ajoutées, à recouper à la main (code, chaînes) :",
              file=sys.stderr)
        for f, k, n in left:
            print(f"  {f}:{k} ({n} caractères)", file=sys.stderr)
    return 2


def read(f):
    with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
        return fh.read()


def check_rules(base):
    """Règles mécaniques de CODING_STANDARDS.md (tests/rules.py) sur les lignes ajoutées depuis base : variable
    JavaScript qui porte l'id d'un élément (index.html), « .every( » ou « all( » sans test de longueur, promesse prise
    pour un booléen, HOLD=<nom> repris d'un fichier de test à l'autre, attente de « running » sans HOLD ni SLOW
    (tests) ; couleur écrite hors des jetons, @keyframes sans animation, adresse privée posée hors de showImage
    (index.html) ; attente fixe, aide ou attente recopiée d'un fichier à l'autre, espace privé fermé sans attendre son
    repos, entrée privée écrite à la main (tests d'interface). Sur des fichiers entiers : print qui dépend de secret(),
    route absente de la docstring, écriture sous PRIVATE_LOCK sans finish_rekey() (launch.py), import interne cassé
    (tous les .py) ; tri brut, flèche de tri ou verrou lu sans le pilote, page ouverte sans fermeture dans un finally,
    fermeture d'une page sans await, aide du pilote redéfinie, préfixe de prompt repris par un autre test (tests
    d'interface) ; chaque nom cité par la carte du code existe dans le code. Liste des fautes (fichier:ligne)."""
    bad = []

    def report(f, found):
        for k, why in found:
            print(f"  {f}:{k} : {why}")
            bad.append(f"{f}:{k}")

    ui_tests = {f: read(f) for f in checked_files(UI_TESTS)}
    if base:
        added = added_lines(base, "tools/ui/index.html", "tests/")
        html, ui_added = read("tools/ui/index.html"), added.get("tools/ui/index.html", set())
        report("tools/ui/index.html", rules.id_shadows(html, ui_added) + rules.private_src(html, ui_added)
               + rules.hardcoded_colors(html.splitlines(), ui_added)
               + rules.unused_keyframes(html.splitlines(), ui_added))
        for f in checked_files("tests/*.mjs"):           # pathspec git : « * » traverse les dossiers
            lines = read(f).splitlines()
            report(f, rules.unchecked_every(lines, added.get(f, set())) + rules.unawaited_then(lines,
                                                                                               added.get(f, set())))
        for f, text in ui_tests.items():
            lines, mine = text.splitlines(), added.get(f, set())
            report(f, rules.fixed_waits(lines, mine) + rules.unsettled_private_close(lines, mine)
                   + rules.private_entry_by_hand(lines, mine))
        ui_added = {f: added.get(f, set()) for f in ui_tests}
        for f, k, why in rules.copied_helpers(ui_tests, ui_added) + rules.copied_waits(ui_tests, ui_added):
            report(f, [(k, why)])
    driver = rules.driver_names(read(DRIVER))
    for f, text in ui_tests.items():                  # fichiers entiers
        lines = text.splitlines()
        report(f, rules.raw_sorts(lines) + rules.unclosed_pages(lines) + rules.unawaited_close(lines)
               + rules.driver_redefined(lines, driver) + rules.prefix_reuse(lines))
    if base:
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
    try:
        server = read("tools/launch.py")
        report("tools/launch.py", rules.secret_prints(server) + rules.undocumented_routes(server)
               + rules.private_lock_without_rekey(server))
    except SyntaxError:                                 # déjà signalé par le contrôle Python
        pass
    sources = {f: read(f) for f in checked_files("*.py")}
    for f, k, why in rules.broken_imports(sources):
        report(f, [(k, why)])
    code = "\n".join(read(f) for f in checked_files("*.py", "*.html", "*.mjs", "*.js"))
    report(f"{AGENT_NOTES}/{CODE_MAP}", rules.missing_map_names(read(f"{AGENT_NOTES}/{CODE_MAP}"), code))
    print(f"Règles : {len(bad)} faute(s) (CODING_STANDARDS.md, noms de la carte du code)" + (" : ÉCHEC" if bad else ""))
    return bad


def print_index(pattern):
    """Index des fonctions, classes et constantes de MAPPED (fichier:ligne nom), filtré par pattern (sous-chaîne)."""
    for f in (m for m in MAPPED if os.path.exists(os.path.join(ROOT, m))):
        for k, name in rules.code_index(f, read(f)):
            if pattern.lower() in name.lower():
                print(f"{f}:{k} {name}")
    return 0


def print_uses(word):
    """Usages de word (texte exact ; mot entier pour un identifiant) dans USES_PLACES, fichiers nouveaux compris :
    fichier:ligne:texte. 1 s'il n'y en a aucun."""
    whole = ["-w"] if re.fullmatch(r"[A-Za-z_$][\w$]*", word) else []
    try:
        out = git("grep", "-n", "-I", "-F", "--untracked", *whole, "-e", word, "--", *USES_PLACES)
    except subprocess.CalledProcessError:              # aucun usage : git grep sort en 1
        out = ""
    print(out.rstrip() or f"{word} : aucun usage dans {', '.join(USES_PLACES)}")
    return 0 if out.strip() else 1


def print_body(name):
    """Corps de chaque fonction ou classe name de MAPPED (là où --map la situe) : « fichier:ligne » puis ses lignes.
    1 si elle est introuvable."""
    found = False
    for f in (m for m in MAPPED if os.path.exists(os.path.join(ROOT, m))):
        text = read(f)
        lines = text.splitlines()
        for start, end in rules.function_spans(f, text, name):
            found = True
            print(f"{f}:{start}")
            print("\n".join(lines[start - 1:end]))
    if not found:
        print(f"{name} : introuvable dans {', '.join(MAPPED)} (--map {name} pour les noms approchants)")
    return 0 if found else 1


def ticket_base():
    """Base du travail du ticket en cours : le dernier commit (arbre de travail et fichiers nouveaux comptent ; décision
    du 25/10/2026), quelle que soit la branche. Sert à l'avis « zone sensible » et à --quick. Hors git, None."""
    try:
        return git("rev-parse", "HEAD").strip() or None
    except (OSError, subprocess.CalledProcessError):    # hors git, ou git absent
        return None


def sensitive_notice(base):
    """Avis (jamais un échec) quand une ligne ajoutée depuis base (ticket_base) dans le code de l'application (tools/,
    hors .md) touche une zone sensible (SENSITIVE) : le ticket demande peut-être la passe bogues de /code-review (la
    ligne « Zone sensible » du ticket fait foi). L'avis nomme, par fichier, la fonction (ou la route) de chaque ligne
    touchée et ses mots, puis celles qui n'ont pas de preuve rouge au journal de tests/mutate.py depuis le dernier
    commit (proved : même fichier, même fonction) : un avis, rien ne bloque (décision du 29/10/2026). Les tests, qui
    nomment ces zones pour les vérifier, ne déclenchent pas l'avis."""
    if not base:
        return
    parts, unproved, proofs = [], [], proved()
    for f, numbers in sorted(added_lines(base, "tools/", ":!*.md").items()):
        try:
            text = read(f)
        except (OSError, UnicodeDecodeError):           # image, fichier supprimé
            continue
        lines, where = text.splitlines(), {}
        for k in sorted(numbers):
            words = [w for w in SENSITIVE if k <= len(lines) and w in lines[k - 1]]
            if words:
                where.setdefault(rules.enclosing_name(f, text, k), set()).update(words)
        if where:
            parts.append(f"{f} : " + ", ".join(f"{name} ({', '.join(sorted(ws))})" for name, ws in where.items()))
            missing = [name for name in where if (f, name.split(" [")[0]) not in proofs]
            if missing:
                unproved.append(f"{f} : {', '.join(missing)}")
    if parts:
        print("Avis : zone sensible : passe bogues /code-review requise (" + " ; ".join(parts) + ")")
    if unproved:
        print("Avis : zone sensible : sans preuve rouge de tests/mutate.py depuis le dernier commit (" + " ; ".join(
            unproved) + ") : prouver chaque garde rouge, et le dire dans le message du commit")


def proved():
    """Fonctions prouvées rouges depuis le dernier commit au journal de tests/mutate.py : {(fichier, fonction)} ;
    vide sans journal ou hors git."""
    import mutate                                    # ici : mutate importe rules, comme check
    try:
        since = int(git("log", "-1", "--format=%ct", "HEAD").strip() or 0)
        with open(mutate.proofs_path(), encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError, subprocess.CalledProcessError):
        return set()
    return {(r.get("fichier"), str(r.get("fonction", "")).split(" [")[0]) for r in rows
            if r.get("t", 0) >= since and r.get("tests")}    # (une preuve sans test en échec ne compte pas)


# un module du banc qui lit un fichier du dépôt autre qu'un .py (l'interface, la carte du code, le README, un
# réglage) : il tourne même quand le banc est sauté sur des .py identiques, car son résultat dépend aussi de ce fichier
NON_PY_READ_RE = re.compile(r"index\.html|sw\.js|\.md\b|README|carte-du-code|prompt_types\.json|tools/config\.json"
                            r"|\.webmanifest|logo\.svg")


def bench_readers():
    """Modules du banc qui tournent quand le banc entier est sauté : tests/test_public_repo.py (dépôt public), puis
    ceux dont la source nomme un fichier autre qu'un .py (NON_PY_READ_RE), relus à chaque fois (aucune liste à
    tenir)."""
    found = ["test_public_repo.py"]
    for f in sorted(checked_files("tests/test_*.py")):
        name = f.rsplit("/", 1)[-1]
        if name not in found and NON_PY_READ_RE.search(read(f)):
            found.append(name)
    return found


def cited_from(source):
    """Lignes à citer d'un contrôle vert d'avant (source : {when, cited}), datées : « Banc (vert du …) : Ran … » ;
    celles du test du dépôt public, refait à chaque passage, sont laissées."""
    out = []
    for line in source.get("cited", []):
        label, sep, rest = line.partition(" : ")
        if sep and not label.startswith("Banc (test_public_repo.py"):
            out.append(f"{label} (vert du {source['when']}){sep}{rest}")
    return out


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


# tests rouges du passage en cours, notés par run_bench et run_ui : {"ui": {fichier : [titres]}, "bench": {module :
# [méthodes]}} ; un fichier sans titre (échec hors d'un test) se rejoue entier. Écrits pour --failed (red_record)
RED = {"ui": {}, "bench": {}}
CAPPED_FILES = set()                                 # fichiers d'interface arrêtés au plafond (pas rejoués)


def bench_fault(m):
    """Identifiant complet d'un test du banc en échec (BENCH_FAULT_RE) : « test_x.Classe.test_y »."""
    name, where = m.group(1), m.group(2)
    return where if where.endswith("." + name) else f"{where}.{name}"


def run_bench(pattern=None, names=(), modules=None):
    """Banc (unittest discover -s tests, ou les seuls fichiers pattern ; names : les seuls tests de ces noms, -k ;
    modules : ces seuls fichiers de tests/, nommés) : (réussi, lignes à afficher, fautes : identifiants des tests en
    échec, notés dans RED)."""
    start = time.monotonic()
    if modules:
        command = [sys.executable, "-m", "unittest", *[m[:-3] for m in modules]]
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [os.path.join(ROOT, "tests"),
                                                                        os.environ.get("PYTHONPATH")])))
    else:
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", *(["-p", pattern] if pattern
                                                                                  else []),
                   *[a for n in names for a in ("-k", n)]]
        env = None
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    out = r.stderr + r.stdout
    lines = out.strip().splitlines()
    ran = next((l for l in reversed(lines) if l.startswith("Ran ")), "Ran ? tests : ligne introuvable")
    verdict = next((l for l in reversed(lines) if l.startswith(("OK", "FAILED"))), "verdict introuvable")
    label = "Banc" + (f" ({', '.join(modules)})" if modules else f" ({pattern})" if pattern else "")
    shown = [out.rstrip()] if r.returncode else []
    faults = list(dict.fromkeys(bench_fault(m) for m in BENCH_FAULT_RE.finditer(out)))
    for m in BENCH_FAULT_RE.finditer(out):
        module = bench_fault(m).split(".")[0]
        if module == "unittest":                       # module qui ne s'importe pas : _FailedTest.<module>
            module = m.group(1)
        listed = RED["bench"].setdefault(module, [])
        if listed is not None and m.group(1).startswith("test"):
            if m.group(1) not in listed:              # (le rejeu le revoit rouge : une seule fois)
                listed.append(m.group(1))
        else:                                         # setUpClass, import… : le module entier
            RED["bench"][module] = None
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


def run_ui_file(f, flags, env, cap=None):
    """Un fichier d'interface dans son groupe de processus : (sortie, code de retour) ; il dépasse UI_FILE_TIMEOUT,
    atteint cap tests en échec (UI_FAIL_CAP ; la sortie le dit, CAPPED_RE), ou finit, et Chrome et le banc sont
    arrêtés dans tous les cas, même bloqués. node introuvable : OSError."""
    cap = UI_FAIL_CAP if cap is None else cap
    proc = subprocess.Popen(["node", "--test", *flags, f], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            start_new_session=os.name != "nt")
    lines, capped = [], threading.Event()

    def read():                                       # sortie lue au fil de l'eau : le plafond se voit tout de suite
        failures, summary = 0, False
        for line in proc.stdout:
            lines.append(line)
            summary = summary or line.startswith("ℹ tests")
            if not summary and FAILED_TEST_RE.match(line.rstrip("\n")):
                failures += 1
                if cap and failures >= cap:
                    capped.set()
                    return
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(UI_FILE_TIMEOUT)
    note = (f"\nfichier arrêté au bout de {seconds(UI_FILE_TIMEOUT)}" if reader.is_alive()
            else f"\nfichier arrêté après {cap} échecs (plafond QWEN_UI_FAIL_CAP : une cascade d'un même changement ; "
                 "le fichier seul, ou --name, pour la suite)" if capped.is_set() else "")
    stop_group(proc)                                  # restes du fichier (Chrome, banc) : arrêtés dans tous les cas
    reader.join(10)
    proc.wait()
    return ("".join(lines) + note).rstrip(), proc.returncode or (1 if note else 0)


def failed_titles(out):
    """Titres des tests en échec d'une sortie de node --test (lignes ✖ d'avant le résumé, qui les répète)."""
    head = out.split("\nℹ tests", 1)[0]
    return [m.group(1) for line in head.splitlines() if (m := FAILED_TEST_RE.match(line))]


def run_ui(files, name=None, wait=None, jobs=None, repeat=1):
    """Tests d'interface (tous, ou les seuls files ; name : motif des noms de tests, --test-name-pattern), jobs fichiers
    à la fois (UI_JOBS ; chacun son Chrome et son banc, sur des ports libres et des dossiers temporaires distincts),
    chacun dans son groupe de processus : un test dépasse UI_TEST_TIMEOUT, un fichier UI_FILE_TIMEOUT. wait : délai
    par défaut des attentes du pilote (QWEN_UI_WAIT ; allongé par l'appelant quand la machine est chargée). Lignes et
    totaux dans l'ordre des fichiers. repeat : chaque fichier passe autant de fois (« (passage k/N) » dans ses lignes,
    pour montrer un échec intermittent). Renvoie (réussi, lignes à afficher, fautes : fichiers en échec)."""
    files = ui_files(files)
    runs = [(f, f if repeat == 1 else f"{f} (passage {k}/{repeat})") for k in range(1, repeat + 1) for f in files]
    env = dict(os.environ, PYTHON=sys.executable, **({"QWEN_UI_WAIT": str(wait)} if wait else {}))
    env.pop("NODE_TEST_CONTEXT", None)                # lancé depuis un test node : sinon node --test ne lance rien
    flags = ["--test-concurrency=1", "--test-reporter=spec", f"--test-timeout={UI_TEST_TIMEOUT}", "--test-force-exit",
             *([f"--test-name-pattern={name}"] if name else [])]
    shown, faults, total, start = [], [], {}, time.monotonic()

    def one(run):
        began = time.monotonic()
        return (*run_ui_file(run[0], flags, env), time.monotonic() - began)
    try:
        with concurrent.futures.ThreadPoolExecutor(min(jobs or UI_JOBS, len(runs) or 1)) as pool:
            results = list(pool.map(one, runs))
    except OSError:
        return False, ["Interface : node introuvable"], ["node introuvable"]
    for (file, f), (out, code, took) in zip(runs, results):
        counts = ui_counts(out)
        capped = CAPPED_RE.search(out)
        if capped:
            CAPPED_FILES.add(file)
        if capped and not counts.get("tests"):       # arrêté au plafond : pas de résumé, comptes de ses lignes
            passed = sum(1 for line in out.splitlines() if PASSED_TEST_RE.match(line))
            counts = {"tests": passed + int(capped.group(1)), "pass": passed, "fail": int(capped.group(1))}
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
        if code or not counts.get("tests"):           # aucun test lancé : pas une réussite
            faults.append(f)
            shown.append(out)
            RED["ui"].setdefault(file, [])
            RED["ui"][file] = list(dict.fromkeys(RED["ui"][file] + failed_titles(out)))
        failed = counts.get("fail", 0) + counts.get("cancelled", 0)
        todo = f", {counts['todo']} à faire" if counts.get("todo") else ""      # test « todo » : compté, sans échec
        cap_note = f", arrêté au plafond de {capped.group(1)} échecs" if capped else ""
        shown.append(f"Interface : {f} : {counts.get('tests', '?')} tests, {failed} en échec{todo}{cap_note} "
                     f"({seconds(took)})")
    failed = total.get("fail", 0) + total.get("cancelled", 0)
    todo = f", {total['todo']} à faire" if total.get("todo") else ""
    shown.append(f"Interface : {len(runs)} fichier(s), {total.get('tests', 0)} tests, {total.get('pass', 0)} "
                 f"réussis, {failed} en échec{todo} ({seconds(time.monotonic() - start)})")
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
    """Sortie écrite à la fois à l'écran et dans le journal ; les lignes de pile de Node (NODE_STACK_RE) ne vont que
    dans le journal (hidden : leur nombre)."""
    def __init__(self, screen, log):
        self.screen, self.log, self.hidden = screen, log, 0

    def write(self, text):
        self.log.write(text)
        lines = text.splitlines(keepends=True)
        shown = [l for l in lines if not NODE_STACK_RE.match(l)]
        self.hidden += len(lines) - len(shown)
        self.screen.write("".join(shown))
        return len(text)

    def flush(self):
        self.screen.flush()
        self.log.flush()


def journal_path():
    """Journal de la sortie complète : QWEN_CHECK_JOURNAL, sinon dans le dossier temporaire du système, un par dossier
    de travail."""
    return os.environ.get("QWEN_CHECK_JOURNAL") or os.path.join(tempfile.gettempdir(),
                                                                f"qwen-check-{os.path.basename(ROOT)}.log")


def kept_journal_path(journal):
    """Chemin où garder le journal d'un passage en échec : FAILURES_DIR à côté du journal, nom horodaté. Les plus
    vieux au-delà de FAILURES_KEPT sont retirés."""
    folder = os.path.join(os.path.dirname(journal), FAILURES_DIR)
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(journal))[0]
    old = sorted(n for n in os.listdir(folder) if n.startswith(stem + "-"))
    for name in old[:max(0, len(old) - FAILURES_KEPT + 1)]:
        os.remove(os.path.join(folder, name))
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 10 ** 9:09d}"
    return os.path.join(folder, f"{stem}-{stamp}.log")


def summary(failed, cited=(), kept=None):
    """Dernière ligne de la sortie : OK, ou chaque contrôle en échec avec ses fautes (SHOWN_FAULTS au plus) ; puis les
    lignes de résultat à citer (cited : « Ran N tests … », totaux de l'interface) et le journal gardé d'un échec."""
    counts = f" ({' ; '.join(cited)})" if cited else ""
    if not failed:
        return "Contrôles : OK" + counts
    parts = []
    for name, faults in failed.items():
        more = f" et {len(faults) - SHOWN_FAULTS} autre(s)" if len(faults) > SHOWN_FAULTS else ""
        parts.append(f"{name} : {', '.join(faults[:SHOWN_FAULTS])}{more}")
    return "Contrôles : ÉCHEC : " + " ; ".join(parts) + counts + (f" (journal gardé : {kept})" if kept else "")


def tree_fingerprint():
    """Empreinte de l'état du dépôt : arbre de travail entier (fichiers suivis et nouveaux non ignorés), écrit dans un
    index temporaire (l'index réel n'est pas touché) ; None hors git."""
    with tempfile.TemporaryDirectory(prefix="qwen-check-index-") as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
        try:
            for args in (("read-tree", "HEAD"), ("add", "-A", "--", ".")):
                subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True, check=True)
            return subprocess.run(["git", "write-tree"], cwd=ROOT, env=env, capture_output=True, text=True,
                                  check=True).stdout.strip() or None
        except (OSError, subprocess.CalledProcessError):
            return None


def tree_state():
    """Empreintes de l'état du dépôt (tree_fingerprint) : arbre entier (tree), ses seuls .py (py : le banc n'a pas à
    repasser sur des .py identiques) et tout sauf les .md (code : un .md seul ne relance ni banc ni interface) ;
    None hors git."""
    tree = tree_fingerprint()
    if not tree:
        return None
    entries = [e for e in git("ls-tree", "-r", "-z", tree).split("\0") if e]

    def digest(keep):
        return hashlib.sha256("\n".join(e for e in entries if keep(e.split("\t", 1)[-1])).encode()).hexdigest()
    return {"tree": tree, "py": digest(lambda p: p.endswith(".py")), "code": digest(lambda p: not p.endswith(".md"))}


def run_options(args):
    """Options qui changent ce qu'un contrôle complet lance (clé de green_record)."""
    return {k: getattr(args, k, None) for k in ("no_bench", "quick", "ui", "name", "repeat")}


def state_key(args, state=None):
    """Clé d'un contrôle complet : empreinte de l'arbre (state : tree_state, calculé sinon), dernier commit et base
    (--quick, l'avis, les lignes et les règles en dépendent), options qui changent ce qui tourne ; None hors git."""
    state = state or tree_state()
    options = run_options(args)
    return f"{state['tree']} {ticket_base()} {merge_base()} {json.dumps(options, sort_keys=True)}" if state else None


def green_record(journal):
    """Fichier du dernier contrôle vert (clé, empreintes, options, date, lignes à citer), à côté du journal."""
    return journal + ".vert.json"


def bench_record(journal):
    """Fichier du dernier banc entier vert (empreinte des .py, date, ligne « Ran N tests »), à côté du journal."""
    return journal + ".banc.json"


def red_record(journal):
    """Fichier des tests rouges du dernier passage (RED), relu par --failed, à côté du journal."""
    return journal + ".rouge.json"


def read_json(path):
    """Contenu JSON de path, ou None (absent, illisible)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, value):
    """value écrit dans path d'un coup (fichier temporaire, puis os.replace) : un contrôle coupé ne laisse rien
    d'illisible."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(tmp, path)


def in_ci():
    """Vrai dans la CI (GitHub Actions) : le banc y passe entier, sans rien sauter."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def md_only(args, state, record):
    """Dernier contrôle vert (record : green_record lu) si seuls des .md ont changé depuis, aux mêmes options : son
    empreinte « code » (tout sauf les .md) est celle de l'arbre. Sinon None (et toujours avec --force, en CI)."""
    if args.force or in_ci() or not state or not record:
        return None
    if record.get("code") != state["code"] or record.get("options") != run_options(args):
        return None
    return record


def foreign_chromes():
    """Nombre de Chrome sans écran (processus principaux) qui ne descendent pas de ce contrôle : d'autres sessions,
    d'autres contrôles ; None si ps ne répond pas (Windows)."""
    try:
        out = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    parent, chromes = {}, []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            parent[int(parts[0])] = int(parts[1])
            if "--headless" in parts[2] and "--type=" not in parts[2]:
                chromes.append(int(parts[0]))

    def mine(pid):
        for _ in range(64):
            if pid == os.getpid():
                return True
            if pid not in parent or pid <= 1:
                return False
            pid = parent[pid]
        return False
    return sum(1 for pid in chromes if not mine(pid))


def load_info():
    """Charge du poste : moyennes de charge (1, 5, 15 min), Chrome sans écran étrangers au contrôle, QWEN_UI_JOBS."""
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):                  # Windows
        load = None
    return {"load": load, "chromes": foreign_chromes(), "jobs": UI_JOBS,
            "jobs_set": bool(os.environ.get("QWEN_UI_JOBS"))}


def load_line(info):
    """Ligne du journal qui dit la charge (load_info)."""
    load = " / ".join(str(x) for x in info["load"]) if info["load"] else "inconnue"
    chromes = "?" if info["chromes"] is None else info["chromes"]
    return (f"charge moyenne {load} ; {chromes} Chrome sans écran hors de ce contrôle ; QWEN_UI_JOBS "
            f"{info['jobs']}{'' if info['jobs_set'] else ' (défaut)'}")


def replay(failed, args):
    """Rejoue seuls, une fois, les fichiers d'interface et les modules du banc en échec (REPLAY_MAX au plus, ni ceux
    arrêtés au plafond, ni avec --repeat) : chaque faute de failed porte ensuite « (intermittent : vert seul) » ou
    « (reproductible) ». Une faute verte seule a sans doute tenu à la charge : le contrôle reste en échec (un test
    instable est à comprendre), mais le rejeu du fichier seul, ou --failed, suffit à le revoir. Renvoie {faute :
    verdict}."""
    files = [f for f in failed.get("Interface", []) if f.endswith(".test.mjs") and f not in CAPPED_FILES]
    modules = list(dict.fromkeys(f.split(".")[0] for f in failed.get("Banc", []) if f != "banc"))
    if args.repeat > 1 or not files + modules:
        return {}
    if len(files) + len(modules) > REPLAY_MAX:
        print(f"Rejeu : pas de rejeu ({len(files) + len(modules)} fichiers ou modules en échec, plus de {REPLAY_MAX} : "
              "sans doute un changement de sens, pas la charge)")
        return {}
    verdicts = {}
    for f in files:
        ok, lines, _ = run_ui([f], args.name, jobs=1)
        verdicts[f] = "intermittent : vert seul" if ok else "reproductible"
        print(f"Rejeu seul : {f} : {verdicts[f]} ({lines[-2].split(' fichier(s), ', 1)[-1]})")
    for module in modules:
        ok, lines, _ = run_bench(f"{module}.py")
        verdicts[module] = "intermittent : vert seul" if ok else "reproductible"
        print(f"Rejeu seul : {module}.py : {verdicts[module]} ({lines[-3].split(' : ', 1)[-1]})")
    for name, key in (("Interface", lambda f: f), ("Banc", lambda f: f.split(".")[0])):
        if name in failed:
            failed[name] = [f"{f} ({verdicts[key(f)]})" if key(f) in verdicts else f for f in failed[name]]
    return verdicts


def failure_log_path():
    """Journal persistant des tests rouges (FAILURE_LOG), dans le dossier temporaire du système."""
    return os.path.join(tempfile.gettempdir(), FAILURE_LOG)


def log_failures(info, verdicts):
    """Tests rouges du passage (RED) ajoutés au journal persistant (FAILURE_LOG, dossier temporaire du système,
    commun aux worktrees) : date, worktree, fichier, test, verdict du rejeu, charge ; FAILURE_LOG_KEPT lignes au
    plus. Plusieurs contrôles peuvent finir ensemble : les lignes s'ajoutent en fin de fichier, sous un verrou du
    fichier (fcntl ; sans lui, sous Windows, l'ajout seul), et le fichier n'est raccourci que sous ce verrou."""
    path = failure_log_path()
    when = time.strftime("%Y-%m-%d %H:%M:%S")
    rows = [{"date": when, "dossier": os.path.basename(ROOT), "fichier": f, "test": t, "rejeu": verdicts.get(f),
             **info} for f, titles in RED["ui"].items() for t in (titles or [None])]
    rows += [{"date": when, "dossier": os.path.basename(ROOT), "fichier": f"tests/{m}.py", "test": t,
              "rejeu": verdicts.get(m), **info} for m, names in RED["bench"].items() for t in (names or [None])]
    if not rows:
        return
    try:
        import fcntl
    except ImportError:                                # Windows
        fcntl = None
    with open(path, "a+", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        f.flush()
        if fcntl:
            f.seek(0)
            lines = f.read().splitlines(keepends=True)
            if len(lines) > FAILURE_LOG_KEPT:
                f.seek(0)
                f.truncate()
                f.write("".join(lines[-FAILURE_LOG_KEPT:]))
    print(f"Journal des échecs : {path} ({len(rows)} ligne(s) ajoutée(s))")


def run_checks(args, state=None, green=None):
    """Contrôles statiques, puis banc et interface s'ils passent : ({contrôle : fautes} des contrôles en échec, lignes
    de résultat à citer : « Ran N tests … », verdict du banc, totaux de l'interface). state : tree_state (calculé
    sinon) ; green : dernier contrôle vert quand seuls des .md ont changé depuis (md_only) : seules les lignes, les
    règles et le test du dépôt public tournent. Le banc entier est sauté quand les .py sont ceux du dernier banc vert
    (bench_record ; jamais en CI ni avec --force). Une faute du banc ou de l'interface est rejouée seule (replay)."""
    state = state or tree_state()
    base = merge_base()
    failed = {}
    statics = (("Python", check_python), ("JavaScript", check_js),
               ("Lignes", lambda: check_line_length(base)), ("Règles", lambda: check_rules(base)))
    if os.environ.get("QWEN_CHECK_AT"):               # --at : les tests actuels sur un autre commit, interface seule
        print(f"Contrôles statiques : sautés (--at {os.environ['QWEN_CHECK_AT']})")
        statics = ()
    for name, check in statics[2:] if green else statics:
        faults = check()
        if faults:
            failed[name] = faults
    if failed:
        print("Banc et interface : pas lancés (contrôles ci-dessus en échec : les corriger d'abord)")
        return failed, []
    if green:
        source = green.get("source") or green
        print(f"Banc et interface : pas relancés : seuls des .md ont changé depuis le contrôle vert du "
              f"{source['when']} (mêmes options ; --force les relance) ; seuls tournent le test du dépôt public et "
              "les tests qui lisent d'autres fichiers que des .py")
        ok, lines, faults = run_bench(modules=bench_readers())
        print("\n".join(lines))
        if not ok:
            return {"Banc": faults}, []
        return failed, [l for l in lines if CITED_RE.match(l)] + cited_from(source)
    if args.ui is not None and args.name:
        titles = ui_titles(ui_files(args.ui))
        try:
            found = any(re.search(args.name, t) for t in titles)
        except re.error:                           # syntaxe propre à JavaScript : node jugera le motif
            found = True
        if not found:
            print(f"Interface : aucun test ne correspond au motif « {args.name} » : rien n'est lancé")
            near = close_titles(args.name, titles)
            if near:
                print("  titres proches :\n" + "\n".join(f"    {t}" for t in near))
            return {"Interface": [f"motif « {args.name} » sans test"]}, []
    jobs, cited = [], []                              # banc et interface : en parallèle (bancs indépendants)
    bench_green = read_json(bench_record(journal_path())) or {}
    if args.no_bench:
        pass
    elif args.quick and not py_changed(ticket_base()):
        print("Banc : sauté (--quick, aucun .py changé depuis le dernier commit) ; seuls tournent le test du dépôt "
              "public et les tests qui lisent d'autres fichiers que des .py")
        jobs.append(("Banc", lambda: run_bench(modules=bench_readers())))
    elif state and not args.force and not in_ci() and bench_green.get("py") == state["py"]:
        print(f"Banc : sauté (mêmes .py que le banc vert du {bench_green['when']} ; --force le relance) ; seuls "
              "tournent le test du dépôt public et les tests qui lisent d'autres fichiers que des .py")
        jobs.append(("Banc", lambda: run_bench(modules=bench_readers())))
        cited.append(f"Banc (vert du {bench_green['when']}, mêmes .py) : {bench_green['ran']}")
    else:
        jobs.append(("Banc", run_bench))
    if args.ui is not None:                           # banc ou plusieurs Chrome en même temps : attentes allongées
        wait = UI_WAIT_LOADED if jobs or min(UI_JOBS, len(ui_files(args.ui))) > 1 else None
        jobs.append(("Interface", lambda: run_ui(args.ui, args.name, wait, repeat=args.repeat)))
    RED["ui"].clear(), RED["bench"].clear(), CAPPED_FILES.clear()
    info = load_info()
    print(f"Charge au départ : {load_line(info)}")
    with concurrent.futures.ThreadPoolExecutor(max(len(jobs), 1)) as pool:
        futures = [(name, job, pool.submit(job)) for name, job in jobs]
        for name, job, future in futures:
            ok, lines, faults = future.result()
            print("\n".join(lines))
            cited += [l for l in lines if CITED_RE.match(l)]
            if not ok:
                failed[name] = faults
            elif name == "Banc" and job is run_bench and state:   # banc entier vert : ses .py sont retenus
                ran = next((l.split(" : ", 1)[1] for l in lines if l.startswith("Banc : Ran ")), None)
                if ran:
                    write_json(bench_record(journal_path()), {"py": state["py"], "ran": ran,
                                                              "when": time.strftime("%d/%m/%Y %H:%M")})
    if failed.get("Interface") or failed.get("Banc"):
        print(f"Charge à la fin : {load_line(load_info())}")
        verdicts = replay(failed, args)
        log_failures(info, verdicts)
    write_red()
    sensitive_notice(ticket_base())
    return failed, cited


def close_titles(pattern, titles, n=8):
    """Titres de tests proches d'un motif sans test : ceux qui contiennent un de ses mots (sans la casse), puis les
    plus ressemblants (difflib)."""
    words = re.findall(r"\w{4,}", pattern.lower())
    near = [t for t in titles if any(w in t.lower() for w in words)]
    near += difflib.get_close_matches(pattern, titles, n=n, cutoff=0.3)
    return list(dict.fromkeys(near))[:n]


def write_red():
    """Tests rouges du passage (RED) écrits pour --failed (red_record) ; aucun : le fichier est retiré."""
    path = red_record(journal_path())
    if RED["ui"] or RED["bench"]:
        write_json(path, {"when": time.strftime("%d/%m/%Y %H:%M"), **RED})
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def run_at(args):
    """--at : les tests d'interface donnés (args.ui), de l'arbre de travail, contre tools/ du commit args.at, dans un
    worktree temporaire (tests/ copié par-dessus), retiré à la fin quoi qu'il arrive. Code de sortie du contrôle."""
    if not args.ui:
        print("--at : donner les fichiers d'interface à rejouer (--ui tests/ui/x.test.mjs)", file=sys.stderr)
        return 2
    tree = tempfile.mkdtemp(prefix="qwen-check-at-")
    try:
        git("worktree", "add", "--detach", tree, args.at)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(tree, ignore_errors=True)
        print(f"--at : worktree de « {args.at} » impossible : {e.stderr.strip()}", file=sys.stderr)
        return 2
    try:
        shutil.rmtree(os.path.join(tree, "tests"), ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "tests"), os.path.join(tree, "tests"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        commit = git("rev-parse", "--short", args.at).strip()
        print(f"--at : tests de l'arbre de travail, interface et serveur de {args.at} ({commit}), dans {tree}")
        journal = os.path.join(tempfile.gettempdir(), f"qwen-check-at-{commit}.log")
        sys.stdout.flush()
        command = [sys.executable, os.path.join(tree, "tests", "check.py"), "--no-bench", "--force", "--ui",
                   *args.ui, *(["--name", args.name] if args.name else [])]
        return subprocess.run(command, cwd=tree, env=dict(os.environ, QWEN_CHECK_AT=commit,
                                                          QWEN_CHECK_JOURNAL=journal)).returncode
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tree], cwd=ROOT, capture_output=True)
        shutil.rmtree(tree, ignore_errors=True)
        subprocess.run(["git", "worktree", "prune"], cwd=ROOT, capture_output=True)


def run_failed(args):
    """--failed : rejoue seuls les tests rouges du dernier passage (red_record : ses titres, ou tout un fichier qui
    a échoué hors d'un test), sans contrôles statiques ; le passage ne compte pas pour « déjà vert », et ses propres
    rouges remplacent la liste. Même retour que run_checks."""
    red = read_json(red_record(journal_path()))
    if not red or not (red.get("ui") or red.get("bench")):
        print("--failed : aucun test rouge noté au dernier passage : rien à rejouer")
        return {}, []
    print(f"--failed : tests rouges du passage du {red['when']}")
    RED["ui"].clear(), RED["bench"].clear(), CAPPED_FILES.clear()
    failed, cited = {}, []
    for module, names in red.get("bench", {}).items():
        ok, lines, faults = run_bench(f"{module}.py", names or ())
        print("\n".join(lines))
        cited += [l for l in lines if CITED_RE.match(l)]
        if not ok:
            failed.setdefault("Banc", []).extend(faults)
    for f, titles in red.get("ui", {}).items():
        name = "^(?:" + "|".join(re.escape(t) for t in titles) + ")$" if titles else None
        ok, lines, faults = run_ui([f], name, jobs=1)
        print("\n".join(lines))
        cited += [l for l in lines if CITED_RE.match(l)]
        if not ok:
            failed.setdefault("Interface", []).extend(faults)
    write_red()
    return failed, cited


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-bench", action="store_true", help="sauter le banc de test")
    ap.add_argument("--quick", action="store_true",
                    help="sauter le banc si aucun .py n'a changé depuis le dernier commit (test du dépôt public lancé)")
    ap.add_argument("--ui", nargs="*", metavar="FICHIER",
                    help="lancer aussi les tests d'interface (Chrome, en local), tous ou les seuls fichiers donnés")
    ap.add_argument("--name", metavar="MOTIF", help="avec --ui : seuls les tests dont le nom correspond (expression "
                    "régulière) ; échoue tout de suite si aucun ne correspond")
    ap.add_argument("--repeat", type=int, default=1, metavar="N", help="avec --ui : passer N fois chaque fichier "
                    "d'interface (échec intermittent)")
    ap.add_argument("--force", action="store_true",
                    help="relancer même si un contrôle identique est déjà vert sur cet état de l'arbre, ou si seuls "
                    "des .md ont changé, et lancer le banc entier même sur les .py du dernier banc vert")
    ap.add_argument("--at", metavar="COMMIT", help="avec --ui : rejouer ces tests d'interface (de l'arbre de travail) "
                    "contre tools/ de ce commit, dans un worktree temporaire retiré ensuite")
    ap.add_argument("--failed", action="store_true", help="rejouer seuls les tests rouges du dernier passage (banc et "
                    "interface), sans les contrôles statiques")
    ap.add_argument("--lines", action="store_true",
                    help=f"seulement la longueur des lignes ajoutées depuis la base ({LINE_MAX} caractères)")
    ap.add_argument("--cached", action="store_true", help="avec --lines : juger l'index (hook avant commit)")
    ap.add_argument("--fix", action="store_true", help="avec --lines : recouper les lignes trop longues qui peuvent "
                    "l'être sans risque (Markdown, commentaires, docstrings), puis vérifier")
    ap.add_argument("--hook", action="store_true", help="hooks de Claude Code (JSON sur l'entrée) : juge le "
                    "fichier écrit par Edit ou Write, ou ceux qu'une commande Bash a écrits ; recoupe la prose trop "
                    "longue, signale le code trop long ; sur stderr, code 2")
    ap.add_argument("--link-venv", action="store_true",
                    help="worktree : liens vers venv et les notes du dossier principal ; hook avant commit")
    ap.add_argument("--map", nargs="?", const="", metavar="NOM",
                    help="index fonction → ligne de launch.py, index.html, du pilote driver.mjs et du banc bench.py "
                    "(les noms qui contiennent NOM)")
    ap.add_argument("--uses", metavar="MOT", help="usages de MOT dans tools/, tests/, le README et la carte du code")
    ap.add_argument("--show", metavar="NOM", help="corps de la fonction NOM de launch.py, index.html, driver.mjs ou "
                    "bench.py (aide du pilote comprise : page.keepPile → --show keepPile)")
    return ap.parse_args(argv)


def already_green(record, key):
    """Lignes à imprimer si le dernier contrôle vert (record) avait la même clé, sinon None."""
    try:
        with open(record, encoding="utf-8") as f:
            green = json.load(f)
    except (OSError, ValueError):
        return None
    if not key or green.get("key") != key:
        return None
    return [f"Contrôles : déjà vert sur cet état (passage du {green['when']}) : pas relancé (--force pour relancer)",
            *green.get("lines", []), summary({}, green.get("cited", []))]


def main(argv=None):
    args = parse_args(argv)
    if args.link_venv:
        return link_venv()
    if args.map is not None:
        return print_index(args.map)
    if args.uses:
        return print_uses(args.uses)
    if args.show:
        return print_body(args.show)
    if args.hook:                                     # bibliothèque standard seulement : pas de relance dans le venv
        return hook_lines(sys.stdin.read())
    if args.at:
        return run_at(args)
    if args.lines and args.fix:
        return fix_lines(merge_base())
    if args.lines:
        return 1 if check_line_length(merge_base(), cached=args.cached) else 0
    reexec_in_venv()
    path, screen = journal_path(), sys.stdout
    state = None if args.failed else tree_state()
    key = state_key(args, state) if state else None
    shown = None if args.force or args.failed else already_green(green_record(path), key)
    if shown:
        print("\n".join(shown[:-1]))
        sensitive_notice(ticket_base())                # l'avis n'est pas gardé : refait (rapide)
        print(shown[-1])
        return 0
    green = None if args.failed else md_only(args, state, read_json(green_record(path)))
    kept = None
    with open(path, "w", encoding="utf-8") as log:
        sys.stdout = tee = Tee(screen, log)
        try:
            failed, cited = run_failed(args) if args.failed else run_checks(args, state, green)
            if tee.hidden:
                print(f"({tee.hidden} ligne(s) de pile Node masquée(s) : dans le journal)")
            print(f"Journal complet : {path}")
            kept = kept_journal_path(path) if failed else None
            print(summary(failed, cited, kept))
        finally:
            sys.stdout = screen
    if kept:
        shutil.copyfile(path, kept)
        try:                                          # un échec efface le vert d'avant, même sur un arbre identique
            os.remove(green_record(path))
        except FileNotFoundError:
            pass
    elif key:                                         # (un passage --failed, partiel, n'a pas de clé)
        now = time.strftime("%d/%m/%Y %H:%M")
        # source : le dernier contrôle qui a lancé banc et interface, cité daté par les passages « .md seuls »
        source = (green.get("source") or green) if green else {"when": now, "cited": cited}
        write_json(green_record(path), {"key": key, "code": state["code"], "options": run_options(args), "when": now,
                                        "cited": cited, "source": {"when": source["when"], "cited": source["cited"]},
                                        "lines": [f"Journal du passage : {path}"]})
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
