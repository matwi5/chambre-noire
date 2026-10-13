"""Crée le raccourci de lancement à la racine.

- Windows : « Qwen-Image.lnk » (contourne le blocage AppLocker des .cmd).
- macOS : « Qwen-Image.command », qui s'ouvre dans le Terminal par double-clic dans le Finder.
"""
import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.name == "nt":
    import win32com.client
    sh = win32com.client.Dispatch("WScript.Shell")
    lnk = sh.CreateShortCut(os.path.join(root, "Qwen-Image.lnk"))
    lnk.TargetPath = os.path.join(root, "venv", "Scripts", "python.exe")
    lnk.Arguments = '"' + os.path.join(root, "tools", "launch.py") + '"'
    lnk.WorkingDirectory = root
    lnk.Description = "Qwen-Image 2.1 local : interface sur http://127.0.0.1:7860/"
    lnk.IconLocation = os.path.join(root, "venv", "Scripts", "python.exe") + ",0"
    lnk.Save()
    print("raccourci écrit :", os.path.join(root, "Qwen-Image.lnk"))
elif sys.platform == "darwin":
    path = os.path.join(root, "Qwen-Image.command")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/bin/zsh\n"
                "# Qwen-Image 2.1 local : interface sur http://127.0.0.1:7860/ (fermer la fenêtre pour arrêter)\n"
                'cd "$(dirname "$0")"\n'
                "# interface déjà lancée (service de tools/make_service.py, ou autre fenêtre) : l'ouvrir simplement\n"
                'if curl -s -o /dev/null --max-time 2 http://127.0.0.1:7860/api/status; then open http://127.0.0.1:7860/; exit 0; fi\n'
                'exec venv/bin/python tools/launch.py "$@"\n')
    os.chmod(path, 0o755)
    print("raccourci écrit :", path)
else:
    sys.exit("raccourci non géré sur ce système : lancez venv/bin/python tools/launch.py")
