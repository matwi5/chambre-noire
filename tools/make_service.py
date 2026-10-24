r"""macOS : lance l'interface à l'ouverture de session, sans fenêtre, accessible depuis le Wi-Fi (launch.py --lan).

  venv/bin/python tools/make_service.py            # installe le service et le démarre
  venv/bin/python tools/make_service.py --remove   # l'arrête et le retire

Le service est un LaunchAgent (~/Library/LaunchAgents/com.matwi5.chambre-noire.plist) : macOS le démarre à chaque
ouverture de session et le relance s'il s'arrête sur une erreur. Journal : logs/service.log, lisible par le seul
compte (masque Umask du service, et droits remis à un journal déjà là). Le Mac reste éveillé tant
qu'il tourne (caffeinate, voir launch.py). Le code d'accès est demandé à tout appareil, le Mac compris : il est dans
tools/access_code.txt, et sur le Mac la feuille de la lampe d'état (« Ouvrir depuis le téléphone ») l'affiche.
"""
import os, plistlib, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL = "com.matwi5.chambre-noire"
OLD_LABEL = "com.matwi5.qwen-image-local"   # service de l'ancien nom de l'application, retiré à chaque appel


def plist_path(label):
    return os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")


PLIST = plist_path(LABEL)
DOMAIN = f"gui/{os.getuid()}"


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def unload(label):
    launchctl("bootout", f"{DOMAIN}/{label}")          # sans erreur si le service ne tourne pas
    plist = plist_path(label)
    if os.path.exists(plist):
        os.remove(plist)


def remove():
    unload(OLD_LABEL)
    unload(LABEL)
    print("service retiré : l'interface ne démarre plus avec la session")


def service_spec():
    """Définition du LaunchAgent."""
    log = os.path.join(ROOT, "logs", "service.log")
    return {
        "Label": LABEL,
        "ProgramArguments": [os.path.join(ROOT, "venv", "bin", "python"), os.path.join(ROOT, "tools", "launch.py"),
                             "--no-browser", "--lan"],
        "WorkingDirectory": ROOT,
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},             # relancé s'il plante, pas s'il est arrêté proprement
        "ProcessType": "Interactive",                        # pas de bridage du processeur pour un service d'arrière-plan
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "StandardOutPath": log,
        "StandardErrorPath": log,
        # masque de création posé par launchd avant d'ouvrir le journal (nom réseau et adresses du Mac) : lisible par le
        # seul compte (63 = 0o077 ; un plist n'écrit pas l'octal ; décision du 23/10/2026)
        "Umask": 0o077,
    }


def install():
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    spec = service_spec()
    if os.path.exists(spec["StandardOutPath"]):          # Umask ne vaut qu'à la création : journal d'avant fermé
        os.chmod(spec["StandardOutPath"], 0o600)
    unload(OLD_LABEL)
    launchctl("bootout", f"{DOMAIN}/{LABEL}")               # remplace une version déjà installée
    with open(PLIST, "wb") as f:
        plistlib.dump(spec, f)
    r = launchctl("bootstrap", DOMAIN, PLIST)
    if r.returncode:
        sys.exit(f"échec du démarrage du service : {r.stderr.strip() or r.stdout.strip()}")
    print(f"service installé et démarré : {PLIST}")
    print("interface : http://127.0.0.1:7860/ sur le Mac (code d'accès dans tools/access_code.txt) ; adresse et code "
          "du téléphone dans la feuille de la lampe d'état, « Ouvrir depuis le téléphone »")


if __name__ == "__main__":
    if sys.platform != "darwin":
        sys.exit("ce script ne sert que sur macOS")
    remove() if "--remove" in sys.argv[1:] else install()
