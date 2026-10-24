"""Crée le raccourci de lancement à la racine.

- Windows : « Chambre noire.lnk » (contourne le blocage AppLocker des .cmd).
- macOS : « Chambre noire.command », qui s'ouvre dans le Terminal par double-clic dans le Finder.
Retire le raccourci de l'ancien nom de l'application (« Qwen-Image »), s'il reste.
"""
import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def drop_old():
    """Retire le raccourci de l'ancien nom, laissé par une installation antérieure, une fois le nouveau écrit."""
    for old in ("Qwen-Image.lnk", "Qwen-Image.command"):
        if os.path.isfile(os.path.join(root, old)):
            os.remove(os.path.join(root, old))


def mac_command():
    """Texte de « Chambre noire.command » (macOS)."""
    return ("#!/bin/zsh\n"
            "# Chambre noire : interface sur http://127.0.0.1:7860/ (fermer la fenêtre pour arrêter)\n"
            'cd "$(dirname "$0")"\n'
            "# interface déjà lancée (service de tools/make_service.py, ou autre fenêtre) : y entrer par un jeton à\n"
            "# usage unique, sans taper le code d'accès (curl répond 0 dès que le serveur répond, même 401)\n"
            "# (sans exec : si l'entrée échoue, l'adresse simple s'ouvre, où le code est demandé)\n"
            "if curl -s -o /dev/null --max-time 2 http://127.0.0.1:7860/api/status; then\n"
            "  venv/bin/python tools/launch.py --enter || open http://127.0.0.1:7860/\n"
            "  exit 0\n"
            "fi\n"
            'exec venv/bin/python tools/launch.py "$@"\n')


def windows():
    import win32com.client
    sh = win32com.client.Dispatch("WScript.Shell")
    lnk = sh.CreateShortCut(os.path.join(root, "Chambre noire.lnk"))
    lnk.TargetPath = os.path.join(root, "venv", "Scripts", "python.exe")
    lnk.Arguments = '"' + os.path.join(root, "tools", "launch.py") + '"'
    lnk.WorkingDirectory = root
    lnk.Description = "Chambre noire : interface sur http://127.0.0.1:7860/"
    lnk.IconLocation = os.path.join(root, "venv", "Scripts", "python.exe") + ",0"
    lnk.Save()
    drop_old()
    print("raccourci écrit :", os.path.join(root, "Chambre noire.lnk"))


def mac():
    path = os.path.join(root, "Chambre noire.command")
    with open(path, "w", encoding="utf-8") as f:
        f.write(mac_command())
    os.chmod(path, 0o755)
    drop_old()
    print("raccourci écrit :", path)


if __name__ == "__main__":
    if os.name == "nt":
        windows()
    elif sys.platform == "darwin":
        mac()
    else:
        sys.exit("raccourci non géré sur ce système : lancez venv/bin/python tools/launch.py")
