"""Preuve rouge d'une garde (CODING_STANDARDS.md) sans script jetable ni arbre modifié à la main (bibliothèque standard
seulement) :

  venv/bin/python tests/mutate.py tools/launch.py --old '<ligne de la garde>' --new '<ligne sans la garde>' -- \\
      venv/bin/python -m unittest discover -s tests -p test_x.py
  venv/bin/python tests/mutate.py tools/ui/index.html --old 'a' --new 'b' --old 'c' --new 'd' -- \\
      venv/bin/python tests/check.py --no-bench --ui tests/ui/x.test.mjs --name '<titre>'

Remplace dans le fichier chaque texte --old (présent une seule fois, sinon rien n'est lancé : code 2) par le --new de
même rang (plusieurs paires : une garde en plusieurs endroits), lance la commande, puis rend toujours le fichier tel
qu'il était : commande finie, en échec, ou interrompue (SIGINT, SIGTERM : le fichier est rendu, puis le script
s'arrête). Code 0 si la commande échoue avec la mutation (la garde est prouvée rouge), 1 si elle passe quand même (la
mutation n'est pas vue : test à revoir). La sortie de la commande passe telle quelle, puis mutate nomme chaque test en
échec avec le premier message de son assertion (node --test et unittest) : l'échec doit venir de l'assertion qui
porte le titre du test, pas d'une autre ni d'une erreur de la page. Une preuve réussie va au journal des preuves
(proofs_path : dossier temporaire du système, un par dossier de travail ; QWEN_MUTATE_JOURNAL le change) : date,
commit, fichier, fonction de chaque texte muté (rules.enclosing_name), tests en échec ; l'avis « zone sensible » de
check.py y cherche les fonctions sensibles touchées depuis le dernier commit. Un arrêt brutal (SIGKILL) ne laisse
pas le temps de rendre le fichier : « git checkout -- <fichier> » le remet. La commande voit le fichier muté sur le
disque : ne pas lancer de relecture sur le même arbre en même temps.
"""
import argparse, json, os, re, signal, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules  # noqa: E402  (tests/rules.py : fonction qui contient une ligne)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# échec d'un test : unittest (« FAIL: test_y (mod.Classe.test_y) », un éventuel sous-test « (cas=…) » ou « [msg] »,
# la première ligne de sa docstring, puis sa trace), node --test (« ✖ titre (12ms) », puis son message dans le résumé
# « ✖ failing tests: » ; sans résumé, fichier arrêté au plafond ou au délai de check.py : la ligne ✖ seule)
UNITTEST_RE = re.compile(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)[^\n]*\n(?:(?!-{20,})[^\n]*\n)?-{20,}\n(.*?)"
                         r"(?=^={20,}|^-{20,}\nRan |\Z)", re.M | re.S)
NODE_FAIL_RE = re.compile(r"^\s*✖ (.+) \([\d.]+m?s\)$")


class Interrupted(Exception):
    pass


def proofs_path():
    """Journal des preuves rouges de ce dossier de travail (QWEN_MUTATE_JOURNAL, sinon le dossier temporaire)."""
    return os.environ.get("QWEN_MUTATE_JOURNAL") or os.path.join(tempfile.gettempdir(),
                                                                  f"qwen-preuves-{os.path.basename(ROOT)}.jsonl")


def write_whole(path, text):
    """Écrit text dans path d'un coup : fichier temporaire du même dossier, puis os.replace (droits gardés)."""
    mode = os.stat(path).st_mode & 0o777
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), prefix=".mutate-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def failures(out):
    """Tests en échec d'une sortie de unittest ou de node --test, chacun avec le premier message de son assertion :
    [(test, message)]."""
    found = []
    for m in UNITTEST_RE.finditer(out):
        if m.group(2).startswith("unittest.loader._FailedTest"):   # module qui ne s'importe plus : pas un test
            continue
        lines = [l.strip() for l in m.group(3).splitlines() if l.strip()]
        message = next((l for l in lines if re.match(r"\w*(?:Error|Exception)\b", l)), lines[-1] if lines else "")
        found.append((m.group(2), message))
    head, _, tail = out.partition("✖ failing tests:")
    lines = tail.splitlines()
    summary = {}                                       # titre → premier message, lus dans le résumé
    for k, line in enumerate(lines):
        m = NODE_FAIL_RE.match(line)
        if m:
            summary.setdefault(m.group(1), next((l.strip() for l in lines[k + 1:] if l.strip()), ""))
    for line in head.splitlines():                     # l'arbre : aussi un fichier arrêté avant son résumé
        m = NODE_FAIL_RE.match(line)
        if m and m.group(1).endswith((".mjs", ".js")):   # fichier tombé au chargement : pas un test
            continue
        if m and not line.lstrip().startswith("✖ failing tests"):
            found.append((m.group(1), summary.get(m.group(1), "(message dans le journal : fichier arrêté avant)")))
    found += [(t, msg) for t, msg in summary.items()
              if not t.endswith((".mjs", ".js")) and not any(t == f for f, _ in found)]
    return list(dict.fromkeys(found))


def record(path, original, olds, failed):
    """Preuve réussie ajoutée au journal des preuves : une ligne par texte muté (sa fonction), avec les tests en
    échec."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(ROOT)).replace(os.sep, "/")
    when = time.time()
    rows = []
    for old in olds:
        k = original.count("\n", 0, original.index(old)) + 1
        rows.append({"date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when)), "t": when, "commit": commit,
                     "fichier": rel, "fonction": rules.enclosing_name(rel, original, k), "ligne": k,
                     "tests": [t for t, _ in failed], "messages": [m for _, m in failed]})
    with open(proofs_path(), "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Applique une mutation le temps d'une commande, puis rend le fichier")
    ap.add_argument("file")
    ap.add_argument("--old", required=True, action="append", help="texte à remplacer (une seule occurrence) ; "
                    "répétable, avec autant de --new")
    ap.add_argument("--new", required=True, action="append", help="texte qui remplace le --old de même rang")
    argv = sys.argv[1:] if argv is None else argv
    cut = argv.index("--") if "--" in argv else len(argv)       # la commande, après --, garde ses options
    args, command = ap.parse_args(argv[:cut]), argv[cut + 1:]
    if not command:
        print("mutate : donner la commande après --", file=sys.stderr)
        return 2
    if len(args.old) != len(args.new):
        print(f"mutate : {len(args.old)} --old pour {len(args.new)} --new : autant de chaque", file=sys.stderr)
        return 2
    with open(args.file, encoding="utf-8", newline="") as f:
        original = f.read()
    mutated = original
    for old, new in zip(args.old, args.new):
        count = original.count(old)
        if count != 1:
            print(f"mutate : --old {'absent' if not count else f'présent {count} fois'} dans {args.file} : rien "
                  f"n'est lancé ({old[:60]})", file=sys.stderr)
            return 2
        mutated = mutated.replace(old, new)

    def interrupt(signum, frame):
        raise Interrupted(signal.Signals(signum).name)
    previous = {s: signal.signal(s, interrupt) for s in (signal.SIGINT, signal.SIGTERM)}
    proc, out = None, []
    try:
        write_whole(args.file, mutated)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=dict(os.environ, QWEN_MUTATING="1"))
        for line in proc.stdout:                       # la sortie passe telle quelle, et reste lue pour la fin
            sys.stdout.write(line)
            out.append(line)
        code = proc.wait()
    except Interrupted as e:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
        print(f"mutate : interrompue ({e}) : {args.file} rendu tel qu'il était")
        return 130
    finally:
        # un second Ctrl-C pendant la remise ne l'interrompt pas, et le fichier est remplacé d'un coup (jamais vide)
        for s in previous:
            signal.signal(s, signal.SIG_IGN)
        write_whole(args.file, original)
        for s, handler in previous.items():
            signal.signal(s, handler)
    if code:
        failed = failures("".join(out))
        print(f"mutate : la commande échoue avec la mutation (code {code}) : garde prouvée ; {args.file} rendu")
        for test, message in failed:
            print(f"mutate : en échec : {test} : {message}")
        if not failed:                                 # (une règle, une compilation, une erreur : pas une preuve)
            print("mutate : aucun test en échec lu dans la sortie : preuve non notée ; vérifier que l'échec vient "
                  "bien de l'assertion du test")
            return 0
        rows = record(args.file, original, args.old, failed)
        print(f"mutate : preuve notée ({', '.join(sorted({r['fonction'] for r in rows}))}) : {proofs_path()}")
        return 0
    print(f"mutate : la commande passe malgré la mutation : elle ne la voit pas ; {args.file} rendu")
    return 1


if __name__ == "__main__":
    sys.exit(main())
