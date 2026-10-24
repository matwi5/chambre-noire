"""Serveur du banc pour les tests d'interface : lancé par driver.mjs (startBench), jamais à la main en temps normal.

Démarre bench.start() (serveur sur un port libre, dossier temporaire, faux moteur), écrit son adresse sur une ligne
JSON ({"url": …, "hold": dossier des libérations du faux moteur, voir HOLD dans fake_sdcli.py, "https" : nom HTTPS de
« tailscale serve », pour tests/ui/relay.py, "cookie" : cookie d'accès du banc, que le serveur demande à toute
requête, le Mac compris}), puis tourne jusqu'à la fermeture de son entrée standard (fin du test, ou test tué) : le
banc supprime alors son dossier temporaire.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tests/, pour importer bench
import bench  # noqa: E402

url = bench.start()
print(json.dumps({"url": url, "hold": bench.hold_dir(), "https": bench.HTTPS_HOST,
                  "cookie": {"name": bench.launch.ACCESS_COOKIE, "value": bench.S.access_token}}), flush=True)
sys.stdin.read()
