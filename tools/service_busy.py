"""Une génération tourne-t-elle sur l'interface lancée ? À demander avant de relancer le service (un changement de
tools/launch.py), depuis le dossier principal, dont le code d'accès existe :

  venv/bin/python tools/service_busy.py [--port 7860]     # imprime True ou False, rien d'autre

Le cookie d'accès est calculé à partir de tools/access_code.txt (read_access_code : rien n'est créé), sans jamais
afficher le code ni la réponse de /api/status (qui les contient pour le Mac). Codes de sortie : 0 (réponse lue), 1
(service injoignable ou réponse illisible), 2 (code d'accès introuvable).
"""
import argparse, json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch  # noqa: E402


class NoAccessCode(Exception):
    """tools/access_code.txt absent ou trop court (pas une KeyError : une réponse sans « busy » en est une)."""


def busy(port=7860):
    """Vrai si une génération tourne sur l'interface de ce port (busy de /api/status, demandé par le Mac lui-même) ;
    NoAccessCode sans code d'accès."""
    code = launch.read_access_code()
    if not code:
        raise NoAccessCode("code d'accès introuvable (tools/access_code.txt) : lancer depuis le dossier principal")
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/status",
                                     headers={"Cookie": f"{launch.ACCESS_COOKIE}={launch.access_token(code)}"})
    with urllib.request.urlopen(request, timeout=10) as r:
        return bool(json.load(r)["busy"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Imprime True si une génération tourne sur l'interface, sinon False")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args(argv)
    try:
        print(busy(args.port))
    except NoAccessCode as e:
        print(e, file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as e:   # ni la réponse ni l'erreur complète : le type seul
        print(f"service injoignable ou réponse illisible ({type(e).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
