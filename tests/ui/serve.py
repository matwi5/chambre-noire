"""Serveur du banc pour les tests d'interface : lancé par driver.mjs (startBench), jamais à la main en temps normal.

Démarre bench.start() (serveur sur un port libre, dossier temporaire, faux moteur), écrit son adresse sur une ligne
JSON ({"url": …, "hold": dossier des libérations du faux moteur, voir HOLD dans fake_sdcli.py}), puis tourne
jusqu'à la fermeture de son entrée standard (fin du test, ou test tué) : le banc supprime alors son dossier
temporaire.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tests/, pour importer bench
import bench  # noqa: E402

print(json.dumps({"url": bench.start(), "hold": bench.hold_dir()}), flush=True)
sys.stdin.read()
