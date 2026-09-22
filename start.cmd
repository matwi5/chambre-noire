@echo off
rem Demarre Qwen-Image-2.1 : sd-server (moteur) + interface locale sur http://127.0.0.1:7860/
rem Fermer la fenetre ou Ctrl+C pour arreter. Options : --backend cpu, --port 7860, --no-browser
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0tools\launch.py" %*
