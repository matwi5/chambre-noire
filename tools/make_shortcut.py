"""Crée le raccourci Windows « Qwen-Image.lnk » à la racine (contourne le blocage AppLocker des .cmd)."""
import os, win32com.client
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sh = win32com.client.Dispatch("WScript.Shell")
lnk = sh.CreateShortCut(os.path.join(root, "Qwen-Image.lnk"))
lnk.TargetPath = os.path.join(root, "venv", "Scripts", "python.exe")
lnk.Arguments = '"' + os.path.join(root, "tools", "launch.py") + '"'
lnk.WorkingDirectory = root
lnk.Description = "Qwen-Image 2.1 local : interface sur http://127.0.0.1:7860/"
lnk.IconLocation = os.path.join(root, "venv", "Scripts", "python.exe") + ",0"
lnk.Save()
print("raccourci écrit :", os.path.join(root, "Qwen-Image.lnk"))
