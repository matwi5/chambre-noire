r"""Installation de Chambre noire (Qwen-Image 2.1 en local) : moteur, modèle, correctif et raccourci.

Windows : venv\Scripts\python.exe setup.py [options]   ·   macOS (Apple Silicon) : venv/bin/python setup.py [options]

    setup.py              # installation complète (≈ 15 Go à télécharger)
    setup.py --q8         # + modèle Q8_0, plus fidèle que Q4_K_M (≈ 7,6 Go de plus)
    setup.py --uc         # + variante communautaire du modèle (uc-q4, et uc-q8 avec --q8)
    setup.py --h3         # Mac : + MiniMax H3, modèle Q4_K_M avec son encodeur et son VAE (≈ 30,8 Go de plus)
    setup.py --h3-q8      # Mac : + MiniMax H3 en Q8_0 (≈ 21,4 Go, plus encodeur et VAE, 19,4 Go, s'ils manquent)
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
SHORTCUT = "Chambre noire.lnk" if WINDOWS else "Chambre noire.command"

# --- moteur stable-diffusion.cpp (versions testées, épinglées par moteur) ------------------------
# Windows reste sur master-890. Le Mac est passé à master-959, qui charge les poids en --mmap sur Metal, y rend le VAE
# rapide et ajoute le cache de préfixe de Qwen-Image 2.1 (les étapes d'une édition ne recalculent plus les références),
# puis à master-1090, qui fait aussi tourner MiniMax H3 et sa vidéo (Qwen y a été vérifié en texte vers image, édition
# et masque avec aperçus ; ses mesures de durée repartent de zéro, comme à chaque changement de release).
SDCPP_WIN = "master-890-74988b2"
SDCPP = {   # backend -> (release, archives à extraire dans sdcpp/<backend>/ ; empreintes : API GitHub de la release)
    "vulkan": (SDCPP_WIN, [("sd-master-74988b2-bin-win-vulkan-x64.zip", "744c8f817c66ecfd02fbb9dc8b122e1f29f7240db1f6086dfde2669403c5d896")]),
    "cpu":    (SDCPP_WIN, [("sd-master-74988b2-bin-win-cpu-x64.zip",    "24fcac70fadc41eb3524837893f1cb7ea54895fe4d807f88ef7afdeee8bd484b")]),
    "cuda":   (SDCPP_WIN, [("sd-master-74988b2-bin-win-cuda12-x64.zip", "e9b86c2166aaf3a89f3e13326312d34b79ec1a2b61101d0ccff2805e7ee7b269"),
                           ("cudart-sd-bin-win-cu12-x64.zip",           "fe20366827d357c00797eebb58244dddab7fd9a348d70090c3871004c320f38d")]),
    # macOS : binaire universel (arm64 + x86_64) compilé avec Metal
    "metal":  ("master-1090-8b1e9df", [("sd-master-8b1e9df-bin-Darwin-macOS-26.7.2-arm64.zip",
                                        "dcf8fcd492a0d7c89eab61a662a393df082f7b81d53a21855e957d389f4d2528")]),
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

# --- MiniMax H3 (Mac seulement, options --h3 et --h3-q8) : fichiers épinglés et vérifiés de la même façon ---------
# Modèle de diffusion allégé, quantifié en GGUF par Hearthscale ; encodeur de texte (GGUF Q4_K_M) publié par leejet ;
# VAE fp16 publié par Comfy-Org. Mêmes clés, noms et dossiers que H3_DIFFUSION et H3_FILES de tools/launch.py.
HF = "https://huggingface.co/"
HEARTHSCALE = HF + "Hearthscale/MiniMax-H3-Image-GGUF/resolve/2cd99b1e7307385b61def10c5caf0cbbef3aaaa2/"
H3_DIFFUSION = {   # version -> (url, chemin local, taille, sha256)
    "h3-q4": (HEARTHSCALE + "minimax_h3_image_pruned-Q4_K_M.gguf",
              "models/diffusion_models/minimax_h3_image_pruned-Q4_K_M.gguf", 11429589600,
              "13fc0add19eaf268ac4ad38704e312c634627feb443ffa89c9a4dce6301926d2"),
    "h3-q8": (HEARTHSCALE + "minimax_h3_image_pruned-Q8_0.gguf",
              "models/diffusion_models/minimax_h3_image_pruned-Q8_0.gguf", 21447217248,
              "311889a1d8e28122c6b9bd1322d7e46e9d56a60bb1b75b269c87f2855c051640"),
}
H3_FILES = {   # fichiers communs aux deux versions
    "vae": (HF + "Comfy-Org/MiniMax-H3-Image/resolve/0bb149f51e3156ed4b90dd45d5620346bfe1df8f/"
            "vae/minimax_h3_image_vae_fp16.safetensors", "models/vae/minimax_h3_image_vae_fp16.safetensors",
            1168505312, "d80e9c2e5cfc9844869961ff5a58c9a9e52182df6bfb30b26018dd7f348721af"),
    "llm": (HF + "leejet/MiniMax-H3-GGUF/resolve/d9c4c6312b4728a68a15a35626d84775a6523783/"
            "qwen3vl_32b_minimax_h3-Q4_K_M.gguf", "models/text_encoders/qwen3vl_32b_minimax_h3-Q4_K_M.gguf",
            18218065024, "11e6efe70a57ce7f4838c47bdbd1a1c4b8ce10e2b7747f1b065990b70f4b05fc"),
}
H3_OPTIONS = {"h3-q4": "--h3", "h3-q8": "--h3-q8"}   # option de setup.py par version


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
    req = urllib.request.Request(url, headers={"User-Agent": "chambre-noire-setup"})
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


def step_files(entries, check_only, tag="[modèle]"):
    """Télécharge et vérifie les fichiers épinglés entries ((url, chemin local, taille, sha256)) ; un fichier à la bonne
    taille et déjà vérifié (marqueur .sha256ok) n'est ni retéléchargé ni rehaché. --check : présence et taille
    seulement ; renvoie False si un fichier manque."""
    ok = True
    for url, local, size, digest in entries:
        dest = P(*local.split("/"))
        label = os.path.basename(local)
        if os.path.exists(dest) and os.path.getsize(dest) == size:
            print(f"{tag} {label} : présent ({human(size)})")
            if check_only:
                continue
            marker = dest + ".sha256ok"
            if os.path.exists(marker):
                continue
        elif check_only:
            print(f"{tag} {label} : ABSENT")
            ok = False
            continue
        else:
            print(f"{tag} {label} : téléchargement ({human(size)})")
            download(url, dest, size)
        got = sha256(dest)
        if got != digest:
            os.replace(dest, dest + ".corrompu")
            sys.exit(f"{tag} {label} : SHA256 incorrect ({got}). Fichier renommé en .corrompu, relancez setup.py.")
        open(dest + ".sha256ok", "w").write(digest)
        print(f"{tag} {label} : SHA256 conforme")
    return ok


def step_models(versions, check_only):
    return step_files([DIFFUSION[v] for v in versions] + ENCODER + [VAE], check_only)


def h3_versions(a):
    """Versions de MiniMax H3 demandées par --h3 et --h3-q8 (dans l'ordre de H3_DIFFUSION) ; hors de macOS, refus
    avant toute écriture : son moteur et ses réglages ne sont mesurés que sur Mac."""
    wanted = [v for v, on in (("h3-q4", a.h3), ("h3-q8", a.h3_q8)) if on]
    if wanted and not MACOS:
        sys.exit(f"{' et '.join(H3_OPTIONS[v] for v in wanted)} : MiniMax H3 s'installe sur Mac seulement "
                 "(Apple Silicon, moteur Metal).")
    return wanted


def step_h3(versions, check_only):
    """MiniMax H3 : les versions données et les fichiers communs (encodeur de texte, VAE) ; sans version, rien."""
    if not versions:
        return True
    return step_files([H3_DIFFUSION[v] for v in versions] + list(H3_FILES.values()), check_only, "[MiniMax H3]")


def installed(entry):
    """Le fichier épinglé entry est là, à sa taille (sans le rehacher, comme --check)."""
    dest = P(*entry[1].split("/"))
    return os.path.exists(dest) and os.path.getsize(dest) == entry[2]


def model_summary():
    """--check : ce qui est installé pour chaque modèle. Renvoie les lignes à afficher et l'option de setup.py qui
    complète un MiniMax H3 à moitié installé ou à moitié téléchargé (None : rien à compléter ; un MiniMax H3 absent
    est facultatif)."""
    qwen = [v for v, entry in DIFFUSION.items() if installed(entry)]
    complete = qwen and all(installed(entry) for entry in ENCODER + [VAE])
    lines = ["Qwen : " + (f"installé ({', '.join(qwen)})" if complete else "incomplet")]
    if not MACOS:
        return lines + ["MiniMax H3 : Mac seulement"], None
    h3 = [v for v, entry in H3_DIFFUSION.items() if installed(entry)]
    if h3 and all(installed(entry) for entry in H3_FILES.values()):
        return lines + [f"MiniMax H3 : installé ({', '.join(h3)})"], None
    started = [P(*entry[1].split("/")) + suffix for entry in [*H3_DIFFUSION.values(), *H3_FILES.values()]
               for suffix in ("", ".part")]            # .part : téléchargement interrompu, repris par l'option
    if not any(os.path.exists(path) for path in started):
        return lines + ["MiniMax H3 : non installé (option --h3, ou --h3-q8 pour la version Q8_0)"], None
    option = H3_OPTIONS["h3-q8"] if h3 == ["h3-q8"] else H3_OPTIONS["h3-q4"]
    return lines + [f"MiniMax H3 : incomplet, lancez : {PY} setup.py {option}"], option


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
    """Trois courtes générations par modèle installé : les estimations de durée sont justes dès la première image.
    Un échec n'arrête pas l'installation, mais son erreur est affichée (la sortie d'erreur de tools/calibrate.py est
    lue, puis montrée). Renvoie les modèles dont la calibration a échoué."""
    failed = []
    if check_only or skip:
        return failed
    for v in versions:
        print(f"[calibration] modèle {v} : trois courtes générations pour mesurer la vitesse de cette machine "
              "(quelques minutes, davantage sur un GPU intégré ; --no-calibrate pour passer cette étape)", flush=True)
        try:
            # le Python enfant écrit en UTF-8 même sous Windows (sinon page de code ANSI, lue ici en UTF-8)
            r = subprocess.run([sys.executable, P("tools", "calibrate.py"), "--model", v, "--if-needed"],
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            code, error = r.returncode, (r.stderr or "").strip()
        except OSError as e:
            code, error = 1, str(e)
        prefix = "[calibration] "            # calibrate.py préfixe déjà ses propres messages
        error = "\n".join(line[len(prefix):] if line.startswith(prefix) else line for line in error.splitlines())
        if error:
            print("\n".join(prefix + line for line in error.splitlines()[-20:]), flush=True)
        if code:
            failed.append(v)
            print(f"[calibration] ÉCHEC du modèle {v} ({error.splitlines()[-1] if error else f'code {code}'}) : "
                  "l'installation continue sans calibration ; les estimations partent des valeurs par défaut et se "
                  f"calibreront à l'usage (pour réessayer : {PY} {os.path.join('tools', 'calibrate.py')} --model {v})",
                  flush=True)
    return failed


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--q8", action="store_true", help="installer aussi le modèle Q8_0, plus fidèle (≈ 7,6 Go)")
    ap.add_argument("--uc", action="store_true", help="installer aussi la variante communautaire du modèle (uc-q4, "
                    "et uc-q8 avec --q8)")
    ap.add_argument("--h3", action="store_true", help="Mac : installer aussi MiniMax H3, modèle Q4_K_M avec son "
                    "encodeur de texte et son VAE (≈ 30,8 Go)")
    ap.add_argument("--h3-q8", action="store_true", help="Mac : installer aussi MiniMax H3 en Q8_0 (≈ 21,4 Go, plus "
                    "l'encodeur et le VAE s'ils manquent) ; \"h3\": \"q8\" dans tools/config.local.json le choisit "
                    "quand les deux versions sont là")
    ap.add_argument("--cuda", action="store_true", help="Windows : installer aussi le moteur CUDA (cartes NVIDIA, ≈ 900 Mo)")
    ap.add_argument("--no-cpu", action="store_true", help="Windows : ne pas installer le moteur de secours CPU")
    ap.add_argument("--no-calibrate", action="store_true", help="ne pas lancer les générations de calibration")
    ap.add_argument("--check", action="store_true", help="vérifier sans rien télécharger")
    return ap


def main():
    a = parser().parse_args()
    if not (WINDOWS or MACOS):
        sys.exit("Ce projet cible Windows et macOS (binaires stable-diffusion.cpp de ces systèmes). Voir le README pour Linux.")
    h3 = h3_versions(a)
    if a.check:                    # comme pour Qwen : --check vérifie aussi les versions présentes
        h3 += [v for v in H3_DIFFUSION if v not in h3 and os.path.exists(P(*H3_DIFFUSION[v][1].split("/")))]
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
    step_h3(h3, a.check)              # facultatif : son état, à --check, vient de model_summary
    ok = step_fix(a.check) and ok
    step_config(backends, a.check)
    step_shortcut(a.check)
    uncalibrated = step_calibrate(versions, a.check, a.no_calibrate) if ok else []
    launch = f"{PY} {os.path.join('tools', 'launch.py')}"
    if a.check:
        lines, h3_option = model_summary()
        for line in lines:
            print(f"[modèles] {line}")
        rerun = f"{PY} setup.py" + (f" {h3_option}" if h3_option else "")
        print("\nÉtat : " + ("complet" if ok and not h3_option else f"incomplet, lancez : {rerun}"))
    else:
        print(f"\nInstallation terminée. Démarrage : double-clic sur {SHORTCUT},")
        print(f"ou : {launch}   puis http://127.0.0.1:7860/")
        for v in versions[1:]:
            print(f"Modèle {v} : {launch} --model {v}   (ou \"model\": \"{v}\" dans tools/config.local.json)")
        if h3:
            print(f"MiniMax H3 ({', '.join(h3)}) : une demande le choisit par \"model\": \"h3\" ; relancez le "
                  "serveur si ce script vient de mettre à jour son moteur" + (
                      " ; version Q8_0 quand les deux sont là : \"h3\": \"q8\" dans tools/config.local.json, puis "
                      "relancez le serveur" if "h3-q8" in h3 else ""))
        for v in uncalibrated:
            print(f"Calibration du modèle {v} en échec (erreur « [calibration] » plus haut), pour réessayer : "
                  f"{PY} {os.path.join('tools', 'calibrate.py')} --model {v}")


if __name__ == "__main__":
    main()
