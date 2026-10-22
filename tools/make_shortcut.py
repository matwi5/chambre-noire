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


if os.name == "nt":
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
elif sys.platform == "darwin":
    path = os.path.join(root, "Chambre noire.command")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/bin/zsh\n"
                "# Chambre noire : interface sur http://127.0.0.1:7860/ (fermer la fenêtre pour arrêter)\n"
                'cd "$(dirname "$0")"\n'
                "# interface déjà lancée (service de tools/make_service.py, ou autre fenêtre) : l'ouvrir simplement\n"
                'if curl -s -o /dev/null --max-time 2 http://127.0.0.1:7860/api/status; then open http://127.0.0.1:7860/; exit 0; fi\n'
                'exec venv/bin/python tools/launch.py "$@"\n')
    os.chmod(path, 0o755)
    drop_old()
    print("raccourci écrit :", path)
else:
    sys.exit("raccourci non géré sur ce système : lancez venv/bin/python tools/launch.py")
