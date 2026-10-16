r"""Installation de Qwen-Image-2.1 local : moteur, modèle, correctif et raccourci.

Windows : venv\Scripts\python.exe setup.py [options]   ·   macOS (Apple Silicon) : venv/bin/python setup.py [options]

    setup.py              # installation complète (≈ 15 Go à télécharger)
    setup.py --q8         # + modèle Q8_0, plus fidèle que Q4_K_M (≈ 7,6 Go de plus)
    setup.py --uc         # + variante communautaire du modèle (uc-q4, et uc-q8 avec --q8)
    setup.py --cuda       # Windows : + moteur CUDA pour carte NVIDIA (≈ 900 Mo de plus)
    setup.py --no-cpu     # Windows : sans le moteur de secours CPU
    setup.py --no-calibrate  # sans les générations de calibration de fin d'installation
    setup.py --check      # vérifie seulement ce qui est installé

Chaque étape est idempotente : relancer le script reprend les téléchargements interrompus
et ne refait pas ce qui est déjà en place et vérifié.
"""
import argparse, hashlib, os, shutil, subprocess, sys, time, urllib.request, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)
WINDOWS, MACOS = os.name == "nt", sys.platform == "darwin"
EXE = "sd-cli.exe" if WINDOWS else "sd-cli"
PY = r"venv\Scripts\python.exe" if WINDOWS else "venv/bin/python"
SHORTCUT = "Qwen-Image.lnk" if WINDOWS else "Qwen-Image.command"

# --- moteur stable-diffusion.cpp (versions testées, épinglées par moteur) ------------------------
# Windows reste sur master-890 ; le Mac passe à master-959, qui charge les poids en --mmap sur Metal, y rend le VAE
# rapide et ajoute le cache de préfixe de Qwen-Image 2.1 (les étapes d'une édition ne recalculent plus les références).
SDCPP_WIN = "master-890-74988b2"
SDCPP = {   # backend -> (release, archives à extraire dans sdcpp/<backend>/ ; empreintes : API GitHub de la release)
    "vulkan": (SDCPP_WIN, [("sd-master-74988b2-bin-win-vulkan-x64.zip", "744c8f817c66ecfd02fbb9dc8b122e1f29f7240db1f6086dfde2669403c5d896")]),
    "cpu":    (SDCPP_WIN, [("sd-master-74988b2-bin-win-cpu-x64.zip",    "24fcac70fadc41eb3524837893f1cb7ea54895fe4d807f88ef7afdeee8bd484b")]),
    "cuda":   (SDCPP_WIN, [("sd-master-74988b2-bin-win-cuda12-x64.zip", "e9b86c2166aaf3a89f3e13326312d34b79ec1a2b61101d0ccff2805e7ee7b269"),
                           ("cudart-sd-bin-win-cu12-x64.zip",           "fe20366827d357c00797eebb58244dddab7fd9a348d70090c3871004c320f38d")]),
    # macOS : binaire universel (arm64 + x86_64) compilé avec Metal
    "metal":  ("master-959-d637cfb", [("sd-master-d637cfb-bin-Darwin-macOS-26.6.2-arm64.zip",
                                       "535b5eccae1d7c81a20466b41433f062d64130e5513fd069006cdd6401dc4ce5")]),
}
SDCPP_URL = "https://github.com/leejet/stable-diffusion.cpp/releases/download/{tag}/{name}"

# --- modèle : fichiers épinglés sur un commit de leur dépôt Hugging Face, vérifiés par SHA256 ----
# Diffusion : quantifications GGUF des poids officiels de Qwen/Qwen-Image-2.1, branche « base » du dépôt
# abenzerps/Qwen-Image-2.1-Uncensored-Quantized ; sa branche principale porte la variante communautaire, en option
# (--uc). Encodeur et VAE : dépôt Comfy-Org/Qwen-Image-2.1 (fichiers identiques à ceux du dépôt abenzerps).
ABENZERPS = "https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/resolve/"
BASE = ABENZERPS + "4db8efdbe3426175988fca2ac50670f35ccb7ec9/"   # branche base
UC = ABENZERPS + "7959e658915f52274897fb573ffeda49de8dc16b/"     # branche main
COMFY = "https://huggingface.co/Comfy-Org/Qwen-Image-2.1/resolve/df94239739eef7205973a145ffa6f441f7b64e84/"
DIFFUSION = {   # version -> (url, chemin local, taille, sha256) ; mêmes clés que DIFFUSION de tools/launch.py
    "q4": (BASE + "qwen-image-2.1-Q4_K_M.gguf", "models/diffusion_models/qwen-image-2.1-Q4_K_M.gguf", 4604557984,
           "833439e91bc1152d28f37aa198c7f6f4218b7de95754c2f7a318a2422ab4b2f8"),
    "q8": (BASE + "qwen-image-2.1-Q8_0.gguf", "models/diffusion_models/qwen-image-2.1-Q8_0.gguf", 7591557792,
           "9a7ec02f4c9d5cf5b78e8efa6ccd81ec0c35a898defbf8e77ac7c02a32fe0d7e"),
    "uc-q4": (UC + "qwen-image-2.1-UC-Q4_K_M.gguf", "models/diffusion_models/qwen-image-2.1-UC-Q4_K_M.gguf",
              4604558112, "e79c8a009f2ecbdb6c70fd663d9aea9ee304a0d91f347e4169a756b8ad141b41"),
    "uc-q8": (UC + "qwen-image-2.1-UC-Q8_0.gguf", "models/diffusion_models/qwen-image-2.1-UC-Q8_0.gguf",
              7591557920, "cde456c72ea3ecebfc1be783300e972711d875e0c5f1bed33d42b66b156affa8"),
}
TE = (COMFY + "text_encoders/qwen3vl_8b_int8_convrot.safetensors", "models/text_encoders/qwen3vl_8b_int8_convrot.safetensors",
      9350798360, "8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f")
VAE = (COMFY + "vae/qwen_image_2.1_vae_bf16.safetensors", "models/vae/qwen_image_2.1_vae_bf16.safetensors",
       675509688, "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9")
TE_FIXED = "models/text_encoders/qwen3vl_8b_int8_convrot_embfix.safetensors"
# macOS : Metal n'a pas de calcul int8, l'encodeur int8 ci-dessus y tournerait sur le processeur (≈ 2 min 30 par
# référence en 512×512). L'encodeur GGUF officiel de Qwen (Q8_0) et sa tour vision (mmproj, F16) tournent sur le GPU.
QWEN_VL = "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/f982a07559d4a2f6c8744d840bf6fccab30eea96/"
TE_GGUF = (QWEN_VL + "Qwen3VL-8B-Instruct-Q8_0.gguf", "models/text_encoders/Qwen3VL-8B-Instruct-Q8_0.gguf",
           8709519456, "0d264b3941185d00a74f75c4245521dae088ff1efc90ab8d1754e83f5844adb0")
TE_VISION = (QWEN_VL + "mmproj-Qwen3VL-8B-Instruct-F16.gguf", "models/text_encoders/mmproj-Qwen3VL-8B-Instruct-F16.gguf",
             1159029824, "ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38")
ENCODER = [TE_GGUF, TE_VISION] if MACOS else [TE]


def human(n):
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or u == "Go":
            return f"{n:.1f} {u}" if u != "o" else f"{n} o"
        n /= 1024


def sha256(path):
    h = hashlib.sha256()
    size, done, t0 = os.path.getsize(path), 0, time.time()
    with open(path, "rb") as f:
        while True:
            b = f.read(16 << 20)
            if not b:
                break
            h.update(b)
            done += len(b)
            if size > 500 << 20:
                print(f"\r    vérification SHA256 … {100 * done // size:3d} %", end="", flush=True)
    if size > 500 << 20:
        print(f"\r    vérification SHA256 … 100 % ({time.time() - t0:.0f} s)")
    return h.hexdigest()


def download(url, dest, expected_size=None, attempts=5):
    """Téléchargement avec reprise automatique si la connexion coupe (Hugging Face interrompt parfois les gros fichiers)."""
    for i in range(1, attempts + 1):
        try:
            return download_once(url, dest, expected_size)
        except OSError as e:          # urllib.error.URLError, coupure réseau, flux HTTP/2 annulé…
            if i == attempts:
                raise
            print(f"\n    connexion interrompue ({e}), reprise {i}/{attempts - 1} dans 5 s")
            time.sleep(5)


def download_once(url, dest, expected_size=None):
    """Téléchargement avec reprise (en-tête Range) et barre de progression."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if expected_size and have == expected_size:
        os.replace(part, dest)
        return
    req = urllib.request.Request(url, headers={"User-Agent": "qwen-image-local-setup"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:           # le serveur ne gère pas la reprise : on repart de zéro
            have = 0
        total = (have + int(r.headers.get("Content-Length", 0))) or expected_size or 0
        t0, last = time.time(), 0
        with open(part, "ab" if have else "wb") as f:
            got = have
            while True:
                b = r.read(4 << 20)
                if not b:
                    break
                f.write(b)
                got += len(b)
                now = time.time()
                if now - last > 0.5:
                    speed = (got - have) / max(now - t0, 1e-6)
                    pct = f"{100 * got / total:5.1f} %" if total else ""
                    print(f"\r    {pct}  {human(got)} / {human(total)}  {human(speed)}/s   ", end="", flush=True)
                    last = now
    print()
    if expected_size and os.path.getsize(part) != expected_size:
        raise OSError(f"téléchargement incomplet ({human(os.path.getsize(part))} sur {human(expected_size)})")
    os.replace(part, dest)


def extract(zpath, target):
    """Extrait l'archive ; hors Windows, rétablit les droits d'exécution que zipfile ne restaure pas."""
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            path = z.extract(info, target)
            mode = (info.external_attr >> 16) & 0o777
            if mode and not WINDOWS:
                os.chmod(path, mode)


def installed_tag(be):
    """Release notée dans sdcpp/<backend>/.installed, ou None (moteur absent, ou installé avant ce marqueur)."""
    marker = P("sdcpp", be, ".installed")
    return open(marker, encoding="utf-8").read().strip() if os.path.exists(marker) else None


def step_engine(backends, check_only):
    ok = True
    for be in backends:
        tag, archives = SDCPP[be]
        target = P("sdcpp", be)
        have = installed_tag(be)
        if have == tag or (have is None and be != "cuda" and os.path.exists(os.path.join(target, EXE))):
            print(f"[moteur] {be} : déjà installé ({target})")
            continue
        if check_only:
            print(f"[moteur] {be} : " + (f"À METTRE À JOUR ({have} → {tag})" if have else "ABSENT"))
            ok = False
            continue
        # mise à jour : extraction dans un dossier neuf, puis échange, pour ne pas réécrire en place
        # un binaire qu'une génération en cours utiliserait
        dest = target + ".new" if have else target
        if have:
            shutil.rmtree(dest, ignore_errors=True)
        for name, digest in archives:
            print(f"[moteur] {be} : téléchargement de {name}" + (f" (mise à jour {have} → {tag})" if have else ""))
            zpath = P("sdcpp", name)
            download(SDCPP_URL.format(tag=tag, name=name), zpath)
            got = sha256(zpath)
            if got != digest:
                os.remove(zpath)
                sys.exit(f"[moteur] empreinte inattendue pour {name} : {got}")
            extract(zpath, dest)
            os.remove(zpath)
        open(os.path.join(dest, ".installed"), "w").write(tag)
        if have:
            old = target + ".old"
            shutil.rmtree(old, ignore_errors=True)
            os.replace(target, old)
            os.replace(dest, target)
            shutil.rmtree(old, ignore_errors=True)
        print(f"[moteur] {be} : installé et vérifié ({tag})")
    return ok


def step_config(backends, check_only):
    """Choisit le backend par défaut du lanceur : cuda s'il est installé, sinon vulkan.
    Sur macOS, rien à écrire : le lanceur prend metal, seul moteur de la plateforme."""
    if MACOS:
        print("[config] backend par défaut : metal")
        return
    cfg_path = P("tools", "config.json")
    import json
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) else {}
    best = "cuda" if os.path.exists(P("sdcpp", "cuda", ".installed")) else "vulkan"
    if check_only:
        print(f"[config] backend par défaut : {cfg.get('backend', 'vulkan')}")
        return
    if cfg.get("backend") != best:
        cfg["backend"] = best
        json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[config] backend par défaut : {best}")


def step_models(versions, check_only):
    ok = True
    for url, local, size, digest in [DIFFUSION[v] for v in versions] + ENCODER + [VAE]:
        dest = P(*local.split("/"))
        label = os.path.basename(local)
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            print(f"[modèle] {label} : présent ({human(size)})")
            if check_only:
                continue
            marker = dest + ".sha256ok"
            if os.path.exists(marker):
                continue
        elif check_only:
            print(f"[modèle] {label} : ABSENT")
            ok = False
            continue
        else:
            print(f"[modèle] {label} : téléchargement ({human(size)})")
            download(url, dest, size)
        got = sha256(dest)
        if got != digest:
            os.replace(dest, dest + ".corrompu")
            sys.exit(f"[modèle] {label} : SHA256 incorrect ({got}). Fichier renommé en .corrompu, relancez setup.py.")
        open(dest + ".sha256ok", "w").write(digest)
        print(f"[modèle] {label} : SHA256 conforme")
    return ok


def step_fix(check_only):
    """Windows : copie corrigée de l'encodeur int8 (voir tools/fix_int8_te.py). Le Mac prend l'encodeur GGUF."""
    if MACOS:
        old = [p for p in (P(*TE[1].split("/")), P(*TE_FIXED.split("/"))) if os.path.exists(p)]
        if old:
            print(f"[encodeur] l'encodeur int8 ne sert plus sur Mac ; ces fichiers peuvent être supprimés "
                  f"({human(sum(os.path.getsize(p) for p in old))}) : " + ", ".join(os.path.relpath(p, ROOT) for p in old))
        return True
    fixed = P(*TE_FIXED.split("/"))
    if os.path.exists(fixed):
        print("[correctif] encodeur texte corrigé : présent")
        return True
    if check_only:
        print("[correctif] encodeur texte corrigé : ABSENT")
        return False
    src = P(*TE[1].split("/"))
    print("[correctif] création de l'encodeur texte compatible stable-diffusion.cpp (≈ 3 min, ≈ 9 Go écrits)")
    subprocess.run([sys.executable, P("tools", "fix_int8_te.py"), src, fixed], check=True)
    return True


def step_shortcut(check_only):
    lnk = P(SHORTCUT)
    if check_only:
        print("[raccourci] " + ("présent" if os.path.exists(lnk) else "absent"))
        return True
    try:
        subprocess.run([sys.executable, P("tools", "make_shortcut.py")], check=True)
    except Exception as e:
        print(f"[raccourci] non créé ({e}). Lancez l'application avec : {PY} {os.path.join('tools', 'launch.py')}")
    return True



def step_calibrate(versions, check_only, skip):
    """Trois courtes générations par modèle installé : les estimations de durée sont justes dès la première image."""
    if check_only or skip:
        return
    for v in versions:
        print(f"[calibration] modèle {v} : trois courtes générations pour mesurer la vitesse de cette machine "
              "(quelques minutes, davantage sur un GPU intégré ; --no-calibrate pour passer cette étape)", flush=True)
        r = subprocess.run([sys.executable, P("tools", "calibrate.py"), "--model", v, "--if-needed"])
        if r.returncode:
            print("[calibration] échec : les estimations partent des valeurs par défaut et se calibreront à l'usage")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--q8", action="store_true", help="installer aussi le modèle Q8_0, plus fidèle (≈ 7,6 Go)")
    ap.add_argument("--uc", action="store_true", help="installer aussi la variante communautaire du modèle (uc-q4, "
                    "et uc-q8 avec --q8)")
    ap.add_argument("--cuda", action="store_true", help="Windows : installer aussi le moteur CUDA (cartes NVIDIA, ≈ 900 Mo)")
    ap.add_argument("--no-cpu", action="store_true", help="Windows : ne pas installer le moteur de secours CPU")
    ap.add_argument("--no-calibrate", action="store_true", help="ne pas lancer les générations de calibration")
    ap.add_argument("--check", action="store_true", help="vérifier sans rien télécharger")
    a = ap.parse_args()
    if not (WINDOWS or MACOS):
        sys.exit("Ce projet cible Windows et macOS (binaires stable-diffusion.cpp de ces systèmes). Voir le README pour Linux.")
    for d in ("models/diffusion_models", "models/text_encoders", "models/vae", "outputs", "logs", "jobs"):
        os.makedirs(P(*d.split("/")), exist_ok=True)
    if MACOS:
        backends = ["metal"]
    else:
        backends = ["vulkan"] + ([] if a.no_cpu else ["cpu"]) + (["cuda"] if a.cuda else [])
        if a.check and os.path.exists(P("sdcpp", "cuda")) and "cuda" not in backends:
            backends.append("cuda")
    asked = {"q8": a.q8, "uc-q4": a.uc, "uc-q8": a.uc and a.q8}
    # --check vérifie aussi les versions déjà installées sans avoir été demandées
    versions = ["q4"] + [v for v in DIFFUSION if v != "q4" and (asked.get(v) or (a.check and os.path.exists(
        P(*DIFFUSION[v][1].split("/")))))]
    ok = step_engine(backends, a.check)
    ok = step_models(versions, a.check) and ok
    ok = step_fix(a.check) and ok
    step_config(backends, a.check)
    step_shortcut(a.check)
    if ok:
        step_calibrate(versions, a.check, a.no_calibrate)
    launch = f"{PY} {os.path.join('tools', 'launch.py')}"
    if a.check:
        print("\nÉtat : " + ("complet" if ok else f"incomplet, lancez : {PY} setup.py"))
    else:
        print(f"\nInstallation terminée. Démarrage : double-clic sur {SHORTCUT},")
        print(f"ou : {launch}   puis http://127.0.0.1:7860/")
        for v in versions[1:]:
            print(f"Modèle {v} : {launch} --model {v}   (ou \"model\": \"{v}\" dans tools/config.local.json)")


if __name__ == "__main__":
    main()
