r"""macOS : lance l'interface à l'ouverture de session, sans fenêtre, accessible depuis le Wi-Fi (launch.py --lan).

  venv/bin/python tools/make_service.py            # installe le service et le démarre
  venv/bin/python tools/make_service.py --remove   # l'arrête et le retire

Le service est un LaunchAgent (~/Library/LaunchAgents/com.matwi5.qwen-image-local.plist) : macOS le démarre à chaque
ouverture de session et le relance s'il s'arrête sur une erreur. Journal : logs/service.log. Le Mac reste éveillé tant
qu'il tourne (caffeinate, voir launch.py) ; le code d'accès du téléphone est dans tools/access_code.txt et s'affiche
en haut de l'interface ouverte sur le Mac.
"""
import os, plistlib, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL = "com.matwi5.qwen-image-local"
PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
DOMAIN = f"gui/{os.getuid()}"


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def remove():
    launchctl("bootout", f"{DOMAIN}/{LABEL}")          # sans erreur si le service ne tourne pas
    if os.path.exists(PLIST):
        os.remove(PLIST)
    print("service retiré : l'interface ne démarre plus avec la session")


def install():
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    log = os.path.join(ROOT, "logs", "service.log")
    spec = {
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
    }
    launchctl("bootout", f"{DOMAIN}/{LABEL}")               # remplace une version déjà installée
    with open(PLIST, "wb") as f:
        plistlib.dump(spec, f)
    r = launchctl("bootstrap", DOMAIN, PLIST)
    if r.returncode:
        sys.exit(f"échec du démarrage du service : {r.stderr.strip() or r.stdout.strip()}")
    print(f"service installé et démarré : {PLIST}")
    print("interface : http://127.0.0.1:7860/ sur le Mac ; adresse et code du téléphone affichés en haut de la page")


if __name__ == "__main__":
    if sys.platform != "darwin":
        sys.exit("ce script ne sert que sur macOS")
    remove() if "--remove" in sys.argv[1:] else install()
