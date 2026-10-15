"""Dépôt public : aucun fichier suivi (ou prêt à l'être) ne contient un repère propre à une machine.

  venv/bin/python -m unittest discover -s tests -p test_public_repo.py

Motifs génériques, sans aucun nom réel : un chemin de dossier personnel macOS, une adresse IPv4 privée ou du partage
d'adresses de Tailscale (10/8, 172.16/12, 192.168/16, 100.64/10), un nom en .ts.net autre que les noms fictifs en
.example.ts.net du banc. Les adresses de documentation (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) ne sont pas
privées : elles passent. Ce fichier lui-même n'est pas balayé (il cite les plages). Pas besoin du serveur du banc.
"""
import os, re, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
PATTERNS = {
    "chemin /Users/<nom>": re.compile(r"/Users/[A-Za-z0-9._-]"),
    "adresse IP privée": re.compile(r"(?<![\d.])(?:10\.{o}|172\.(?:1[6-9]|2\d|3[01])|192\.168|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))"
                                    r"\.{o}\.{o}(?![\d.]*\d)".replace("{o}", OCTET)),
    "nom Tailscale (.ts.net)": re.compile(r"(?<![\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b", re.I),
}
FICTITIOUS_TS = re.compile(r"\.example\.ts\.net$", re.I)       # noms fictifs du banc (domaine réservé « example »)


def candidate_files():
    """Fichiers suivis, plus ceux qui ne sont ni suivis ni ignorés (ils partiront au prochain commit)."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return sorted({f for f in out.decode().split("\0") if f})


class PublicRepoTest(unittest.TestCase):
    def test_no_machine_specific_detail_in_the_repository(self):
        try:
            files = candidate_files()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git indisponible ou hors d'un dépôt")
        me = os.path.relpath(os.path.abspath(__file__), ROOT).replace(os.sep, "/")
        found = []
        for name in files:
            path = os.path.join(ROOT, name)
            if name == me or not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):          # images et autres fichiers binaires
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for label, rx in PATTERNS.items():
                    for m in rx.finditer(line):
                        if label.startswith("nom Tailscale") and FICTITIOUS_TS.search(m.group(0)):
                            continue
                        found.append(f"{name}:{n}: {label}")   # la valeur trouvée n'est pas recopiée
        self.assertEqual(found, [], "repères propres à une machine dans le dépôt public :\n" + "\n".join(found))

    def test_patterns_catch_what_they_should(self):
        hits = lambda text: [label for label, rx in PATTERNS.items() for m in rx.finditer(text)
                             if not (label.startswith("nom Tailscale") and FICTITIOUS_TS.search(m.group(0)))]
        for text in ("/Users/x/projet", "http://192.168.1.20:7860", "10.0.0.1", "172.20.3.4", "100.101.102.103",
                     "mac.tail1234.ts.net"):
            self.assertEqual(len(hits(text)), 1, text)
        for text in ("chemins `/Users/…`", "192.0.2.10", "198.51.100.7", "203.0.113.9", "172.32.0.1", "100.128.0.1",
                     "version 10.0.1", "1.10.0.2.3", "qwen-banc.example.ts.net", "<machine>.<tailnet>.ts.net"):
            self.assertEqual(hits(text), [], text)


if __name__ == "__main__":
    unittest.main()
