"""Faux sd-cli du banc de test (tests/bench.py) : imite la sortie du vrai moteur sans GPU ni modèle.

Il lit les options utiles de la ligne de commande construite par tools/launch.py (-p, -W, -H, --steps, -o,
--preview-path, --preview-interval), imprime les lignes que le serveur analyse (progression « k/N - x.xxs/it » et
lignes « … completed, taking x.xxs »), écrit les aperçus en PNG et l'image finale en PNG, ou en WebP animé quand -o
finit par .webp (sortie d'une vidéo, images de teintes différentes : webp). Comme le vrai moteur, il échoue (ligne
[ERROR], code 1) quand un fichier de modèle de sa ligne de commande (MODEL_FLAGS) n'existe pas, et il refuse avant tout
calcul une image d'entrée (-r, -i, --mask) qui n'est ni PNG, ni JPEG, ni BMP, ni GIF (WebP, AVIF, TIFF…), avec le même
message d'erreur que stb_image.

Commandes glissées dans le prompt, pour un test :
- FAIL (mot entier) : échoue après la première étape (ligne [ERROR], code de sortie 1, aucune image) ;
- FAILSEED=<n> : échoue de même si la graine (-s) vaut n, pour faire échouer une seule image d'un lot ;
- SLOW ou SLOW=<s> (mot entier) : chaque étape dure <s> secondes (0,3 s pour SLOW seul ; 0,01 s sans commande) ;
- NOISE (mot entier) : barres d'avancement qui ne sont pas des étapes, à 99 s/it, de totaux 25 et --steps, comme
  celles de MiniMax H3 et de la vidéo : avant l'encodage du prompt (lecture d'une image d'entrée, suivie de
  « encode_first_stage completed ») et après l'échantillonnage (décodage) ; et, au début de l'échantillonnage, des
  barres de total 25 seul, qu'aucun moteur connu n'imprime là (pour éprouver la règle du total) ;
- OOM (mot entier) : échoue au début de l'échantillonnage comme le vrai moteur quand la mémoire Metal manque (lignes
  [W] et [E] d'un échec réel de MiniMax H3, 15/11/2026), code de sortie 1, aucune image ;
- PREVIEW_OOM (mot entier) : après chaque étape, l'aperçu manque de mémoire comme dans un vrai journal (13/10/2026 :
  lignes [W] et [E], « preview decode failed »), sans arrêter la génération ;
- FEWER=<n> : n étapes calculées au lieu de --steps, comme le vrai moteur pour une image d'origine retouchée à
  --strength moins de 1 (« 1/1 » pour 0,05 sur 25 étapes) ;
- HOLD ou HOLD=<nom> : attend, avant la première étape, que le banc libère ce nom (bench.release(nom), « hold » par
  défaut ; release() du pilote des tests d'interface) : la génération reste en cours, et les suivantes en file, sans
  dépendre du temps. La libération est un fichier <nom> du dossier QWEN_FAKE_HOLD (posé par le banc dans le script
  sd-cli) ; elle vaut pour toutes les générations de ce nom jusqu'au test suivant (BenchCase.setUp vide le dossier,
  après avoir tout libéré par le fichier ALL), et jusqu'à la fin du banc pour les tests d'interface : un nom par test.
  Sans libération après HOLD_LIMIT secondes, échec comme FAIL. HOLD=<nom>@<k> attend de même, mais une fois l'étape
  k annoncée : la génération reste en cours, avec les aperçus des étapes d'avant (le serveur lit le dernier aperçu à
  chaque étape annoncée).
"""
import os, re, struct, sys, time, zlib

HOLD_LIMIT = 120
READABLE = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"BM", b"GIF8")   # en-têtes que stb_image sait lire
MODEL_FLAGS = ("--model", "--diffusion-model", "--vae", "--llm", "--llm_vision")   # fichiers de modèle à charger
ALL = "ALL"                                     # fichier qui libère tous les noms (ménage du banc)
OOM_LINES = (                                   # échec réel de MiniMax H3 Q8, 1280×1888 et 4 références (15/11/2026)
    "[W] model manager memory on MTL0: reported free 3706.17 MB / total 25559.05 MB, tracked weights 21568.03 MB / "
    "other runtime 0.00 MB / current runtime 127.93 MB --- model_manager.cpp:1817",
    "[W] execution engine cannot make enough memory available on MTL0: need 4641.83 MB device / 4257.76 MB budget, "
    "available 3706.17 MB device / unlimited budget --- execution_engine.cpp:942",
    "[E] minimax_h3 segment 4/54 (minimax_h3.blocks.0) failed during weight preparation --- execution_engine.cpp:591",
    "[E] diffusion model compute failed --- diffusion_engine.cpp:2683",
    "[E] Diffusion model sampling failed --- diffusion_engine.cpp:2917",
    "[E] sampling for image 1/1 failed after 7.38s --- image.cpp:1045",
    "[E] generate failed --- main.cpp:1007",
)
PREVIEW_OOM_LINES = (                           # aperçu sauté, génération menée à son terme (13/10/2026)
    "[W] model manager cannot make enough memory available on MTL0: need 31068.38 MB device / 30556.38 MB budget, "
    "available 13546.48 MB device / unlimited budget --- model_manager.cpp:1962",
    "[E] wan_vae segment 1/1 (graph) failed during weight preparation --- ggml_runner.cpp:899",
    "[E] vae decode compute failed --- vae.hpp:377",
)


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


def webp(path, w, h, frames=4):
    """WebP animé de w×h comme celui de la vidéo du vrai moteur : frames images de teintes différentes (la première,
    rouge, est celle de la vignette), en boucle. Pillow seulement ici : le reste du faux moteur s'en passe."""
    from PIL import Image
    images = [Image.new("RGB", (w, h), (220 - 60 * k, 40, 40 + 60 * k)) for k in range(frames)]
    images[0].save(path, "WEBP", save_all=True, append_images=images[1:], duration=42, loop=0, lossless=True)


def noise(*totals):
    """Barres d'avancement qui ne sont pas des étapes (NOISE), de ces totaux, à 99 s/it."""
    for total in totals:
        for k in range(1, total + 1):
            print(f"  |{'#' * k}| {k}/{total} - 99.00s/it", flush=True)


def missing_models(argv):
    """Fichiers de modèle de la ligne de commande qui n'existent pas."""
    return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a in MODEL_FLAGS and not os.path.exists(argv[i + 1])]


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
    held = re.search(r"\bHOLD(?:=([\w-]+))?(?:@(\d+))?(?![\w=@-])", prompt)
    held_at = int(held.group(2)) if held and held.group(2) else 0      # étape annoncée avant d'attendre (0 : avant)
    noisy = re.search(r"\bNOISE\b", prompt)
    preview_oom = re.search(r"\bPREVIEW_OOM\b", prompt)
    fewer = re.search(r"\bFEWER=(\d+)\b", prompt)
    runs = int(fewer.group(1)) if fewer else steps                    # étapes calculées
    print("Version: faux sd-cli du banc de test", flush=True)
    for p in unreadable_inputs(argv):
        print(f"[E] load image from '{p}' failed --- media_io.cpp:543", flush=True)
        return 1
    print("loading diffusion model", flush=True)
    for p in missing_models(argv):
        print(f"[ERROR] init model loader from file failed: '{p}'", flush=True)
        return 1
    if noisy:                                       # lecture d'une image d'entrée
        noise(25, steps)
        print("encode_first_stage completed, taking 1.00s", flush=True)
    if held and not held_at and not hold(held.group(1) or "hold"):
        print(f"[ERROR] faux moteur jamais libéré (HOLD, {HOLD_LIMIT} s)", flush=True)
        return 1
    print("get_learned_condition completed, taking 0.50s", flush=True)
    if re.search(r"\bOOM\b", prompt):             # lignes réelles, sans chemin
        for line in OOM_LINES:
            print(line, flush=True)
        return 1
    if noisy:                                       # d'un autre total que les étapes
        noise(25)
    for k in range(1, runs + 1):
        time.sleep(delay)
        print(f"  |{'=' * k}| {k}/{runs} - {max(delay, 0.01):.2f}s/it", flush=True)
        if preview_oom:
            for line in PREVIEW_OOM_LINES + (f"[E] preview decode failed at step {k} --- diffusion_engine.cpp:2135",):
                print(line, flush=True)
        if k == held_at and not hold(held.group(1) or "hold"):
            print(f"[ERROR] faux moteur jamais libéré (HOLD, {HOLD_LIMIT} s)", flush=True)
            return 1
        if fail:
            print("[ERROR] panne simulée par le banc de test", flush=True)
            return 1
        if preview and every and k % every == 0:
            # bruit : un aperçu de moins de 1000 octets serait ignoré par le serveur
            png(preview % k if "%" in preview else preview, 48, 48, lambda y: os.urandom(48 * 3))
    print(f"sampling completed, taking {runs * delay:.2f}s", flush=True)
    if noisy:                                       # décodage
        noise(25, steps)
    if out.lower().endswith(".webp"):
        webp(out, w, h)
    else:
        png(out, w, h, lambda y: bytes((40 + 160 * y // h, 60, 200 - 120 * y // h)) * w)
    print("decode_first_stage completed, taking 0.20s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
