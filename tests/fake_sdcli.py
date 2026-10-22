"""Faux sd-cli du banc de test (tests/bench.py) : imite la sortie du vrai moteur sans GPU ni modèle.

Il lit les options utiles de la ligne de commande construite par tools/launch.py (-p, -W, -H, --steps, -o,
--preview-path, --preview-interval), imprime les lignes que le serveur analyse (progression « k/N - x.xxs/it » et
lignes « … completed, taking x.xxs »), écrit les aperçus et l'image finale en PNG. Comme le vrai moteur (stb_image),
il refuse avant tout calcul une image d'entrée (-r, -i, --mask) qui n'est ni PNG, ni JPEG, ni BMP, ni GIF (WebP, AVIF,
TIFF…), avec le même message d'erreur.

Commandes glissées dans le prompt, pour un test :
- FAIL (mot entier) : échoue après la première étape (ligne [ERROR], code de sortie 1, aucune image) ;
- FAILSEED=<n> : échoue de même si la graine (-s) vaut n, pour faire échouer une seule image d'un lot ;
- SLOW ou SLOW=<s> (mot entier) : chaque étape dure <s> secondes (0,3 s pour SLOW seul ; 0,01 s sans commande) ;
- HOLD ou HOLD=<nom> : attend, avant la première étape, que le banc libère ce nom (bench.release(nom), « hold » par
  défaut ; release() du pilote des tests d'interface) : la génération reste en cours, et les suivantes en file, sans
  dépendre du temps. La libération est un fichier <nom> du dossier QWEN_FAKE_HOLD (posé par le banc dans le script
  sd-cli) ; elle vaut pour toutes les générations de ce nom jusqu'au test suivant (BenchCase.setUp vide le dossier,
  après avoir tout libéré par le fichier ALL), et jusqu'à la fin du banc pour les tests d'interface : un nom par test.
  Sans libération après HOLD_LIMIT secondes, échec comme FAIL.
"""
import os, re, struct, sys, time, zlib

HOLD_LIMIT = 120
READABLE = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"BM", b"GIF8")   # en-têtes que stb_image sait lire
ALL = "ALL"                                     # fichier qui libère tous les noms (ménage du banc)


def hold(name):
    """Attend que le banc libère name ; False si rien ne vient avant HOLD_LIMIT secondes."""
    d = os.environ.get("QWEN_FAKE_HOLD", "")
    end = time.time() + HOLD_LIMIT
    while not (os.path.exists(os.path.join(d, name)) or os.path.exists(os.path.join(d, ALL))):
        if time.time() > end:
            return False
        time.sleep(0.02)
    return True


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def png(path, w, h, row):
    """PNG RGB de w×h, ligne y remplie par row(y) (octets d'une ligne, 3 par pixel)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + row(y) for y in range(h))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def unreadable_inputs(argv):
    """Images d'entrée de la ligne de commande que le vrai moteur ne saurait pas lire."""
    paths = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a in ("-r", "-i", "--mask")]
    bad = []
    for p in paths:
        with open(p, "rb") as f:
            if not f.read(8).startswith(READABLE):
                bad.append(p)
    return bad


def main(argv):
    prompt = arg(argv, "-p", "")
    w, h, steps = int(arg(argv, "-W", 512)), int(arg(argv, "-H", 512)), int(arg(argv, "--steps", 8))
    out, preview, every = arg(argv, "-o"), arg(argv, "--preview-path"), int(arg(argv, "--preview-interval", 0) or 0)
    fail_seed = re.search(r"\bFAILSEED=(-?\d+)\b", prompt)
    fail = re.search(r"\bFAIL\b", prompt) or (fail_seed and fail_seed.group(1) == arg(argv, "-s"))
    slow = re.search(r"\bSLOW(?:=(\d+(?:\.\d+)?))?\b", prompt)
    delay = float(slow.group(1) or 0.3) if slow else 0.01
    held = re.search(r"\bHOLD(?:=([\w-]+))?(?![\w=-])", prompt)
    print("Version: faux sd-cli du banc de test", flush=True)
    for p in unreadable_inputs(argv):
        print(f"[E] load image from '{p}' failed --- media_io.cpp:543", flush=True)
        return 1
    print("loading diffusion model", flush=True)
    if held and not hold(held.group(1) or "hold"):
        print(f"[ERROR] faux moteur jamais libéré (HOLD, {HOLD_LIMIT} s)", flush=True)
        return 1
    print("get_learned_condition completed, taking 0.50s", flush=True)
    for k in range(1, steps + 1):
        time.sleep(delay)
        print(f"  |{'=' * k}| {k}/{steps} - {max(delay, 0.01):.2f}s/it", flush=True)
        if fail:
            print("[ERROR] panne simulée par le banc de test", flush=True)
            return 1
        if preview and every and k % every == 0:
            # bruit : un aperçu de moins de 1000 octets serait ignoré par le serveur
            png(preview % k if "%" in preview else preview, 48, 48, lambda y: os.urandom(48 * 3))
    print(f"sampling completed, taking {steps * delay:.2f}s", flush=True)
    png(out, w, h, lambda y: bytes((40 + 160 * y // h, 60, 200 - 120 * y // h)) * w)
    print("decode_first_stage completed, taking 0.20s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
