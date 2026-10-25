"""Preuve rouge d'une garde (CODING_STANDARDS.md) sans script jetable ni arbre modifié à la main (bibliothèque standard
seulement) :

  venv/bin/python tests/mutate.py tools/launch.py --old '<ligne de la garde>' --new '<ligne sans la garde>' -- \\
      venv/bin/python -m unittest discover -s tests -p test_x.py

Remplace dans le fichier le texte --old (présent une seule fois, sinon rien n'est lancé : code 2) par --new, lance la
commande, puis rend toujours le fichier tel qu'il était : commande finie, en échec, ou interrompue (SIGINT, SIGTERM :
le fichier est rendu, puis le script s'arrête). Code 0 si la commande échoue avec la mutation (la garde est prouvée
rouge), 1 si elle passe quand même (la mutation n'est pas vue : test à revoir). Un arrêt brutal (SIGKILL) ne laisse
pas le temps de rendre le fichier : « git checkout -- <fichier> » le remet. La commande voit le fichier muté sur le
disque : ne pas lancer de relecture sur le même arbre en même temps.
"""
import argparse, signal, subprocess, sys


class Interrupted(Exception):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="Applique une mutation le temps d'une commande, puis rend le fichier")
    ap.add_argument("file")
    ap.add_argument("--old", required=True, help="texte à remplacer (une seule occurrence)")
    ap.add_argument("--new", required=True, help="texte qui le remplace")
    argv = sys.argv[1:] if argv is None else argv
    cut = argv.index("--") if "--" in argv else len(argv)       # la commande, après --, garde ses options
    args, command = ap.parse_args(argv[:cut]), argv[cut + 1:]
    if not command:
        print("mutate : donner la commande après --", file=sys.stderr)
        return 2
    with open(args.file, encoding="utf-8", newline="") as f:
        original = f.read()
    count = original.count(args.old)
    if count != 1:
        print(f"mutate : --old {'absent' if not count else f'présent {count} fois'} dans {args.file} : rien n'est "
              "lancé", file=sys.stderr)
        return 2

    def interrupt(signum, frame):
        raise Interrupted(signal.Signals(signum).name)
    previous = {s: signal.signal(s, interrupt) for s in (signal.SIGINT, signal.SIGTERM)}
    proc = None
    try:
        with open(args.file, "w", encoding="utf-8", newline="") as f:
            f.write(original.replace(args.old, args.new))
        proc = subprocess.Popen(command)
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
        with open(args.file, "w", encoding="utf-8", newline="") as f:
            f.write(original)
        for s, handler in previous.items():
            signal.signal(s, handler)
    if code:
        print(f"mutate : la commande échoue avec la mutation (code {code}) : garde prouvée ; {args.file} rendu")
        return 0
    print(f"mutate : la commande passe malgré la mutation : elle ne la voit pas ; {args.file} rendu")
    return 1


if __name__ == "__main__":
    sys.exit(main())
