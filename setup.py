r"""Installation de Qwen-Image-2.1 local : moteur, modèle, correctif et raccourci.

    venv\Scripts\python.exe setup.py            # installation complète (≈ 15 Go à télécharger)
    venv\Scripts\python.exe setup.py --no-cpu   # sans le moteur de secours CPU
    venv\Scripts\python.exe setup.py --check    # vérifie seulement ce qui est installé

Chaque étape est idempotente : relancer le script reprend les téléchargements interrompus
et ne refait pas ce qui est déjà en place et vérifié.
"""
import argparse, hashlib, os, subprocess, sys, time, urllib.request, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)

# --- moteur stable-diffusion.cpp (version testée, épinglée) -------------------------------------
SDCPP_TAG = "master-890-74988b2"
SDCPP = {
    "vulkan": ("sd-master-74988b2-bin-win-vulkan-x64.zip", "744c8f817c66ecfd02fbb9dc8b122e1f29f7240db1f6086dfde2669403c5d896"),
    "cpu":    ("sd-master-74988b2-bin-win-cpu-x64.zip",    "24fcac70fadc41eb3524837893f1cb7ea54895fe4d807f88ef7afdeee8bd484b"),
}
SDCPP_URL = "https://github.com/leejet/stable-diffusion.cpp/releases/download/{tag}/{name}"

# --- modèle (dépôt abenzerps/Qwen-Image-2.1-GGUF, empreintes de son fichier SHA256SUMS) ----------
HF = "https://huggingface.co/abenzerps/Qwen-Image-2.1-GGUF/resolve/main/"
MODELS = [
    ("qwen-image-2.1-Q4_K_M.gguf", "models/diffusion_models/qwen-image-2.1-Q4_K_M.gguf", 4604557984,
     "833439e91bc1152d28f37aa198c7f6f4218b7de95754c2f7a318a2422ab4b2f8"),
    ("text_encoders/qwen3vl_8b_int8_convrot.safetensors", "models/text_encoders/qwen3vl_8b_int8_convrot.safetensors", 9350798360,
     "8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f"),
    ("vae/qwen_image_2.1_vae_bf16.safetensors", "models/vae/qwen_image_2.1_vae_bf16.safetensors", 675509688,
     "bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9"),
]
TE_FIXED = "models/text_encoders/qwen3vl_8b_int8_convrot_embfix.safetensors"


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


def download(url, dest, expected_size=None):
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
    os.replace(part, dest)


def step_engine(backends, check_only):
    ok = True
    for be in backends:
        name, digest = SDCPP[be]
        target = P("sdcpp", be)
        if os.path.exists(os.path.join(target, "sd-cli.exe")):
            print(f"[moteur] {be} : déjà installé ({target})")
            continue
        if check_only:
            print(f"[moteur] {be} : ABSENT")
            ok = False
            continue
        print(f"[moteur] {be} : téléchargement de {name}")
        zpath = P("sdcpp", name)
        download(SDCPP_URL.format(tag=SDCPP_TAG, name=name), zpath)
        got = sha256(zpath)
        if got != digest:
            sys.exit(f"[moteur] empreinte inattendue pour {name} : {got}")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(target)
        os.remove(zpath)
        print(f"[moteur] {be} : installé et vérifié")
    return ok


def step_models(check_only):
    ok = True
    for remote, local, size, digest in MODELS:
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
            download(HF + remote, dest, size)
        got = sha256(dest)
        if got != digest:
            os.replace(dest, dest + ".corrompu")
            sys.exit(f"[modèle] {label} : SHA256 incorrect ({got}). Fichier renommé en .corrompu, relancez setup.py.")
        open(dest + ".sha256ok", "w").write(digest)
        print(f"[modèle] {label} : SHA256 conforme")
    return ok


def step_fix(check_only):
    fixed = P(*TE_FIXED.split("/"))
    if os.path.exists(fixed):
        print("[correctif] encodeur texte corrigé : présent")
        return True
    if check_only:
        print("[correctif] encodeur texte corrigé : ABSENT")
        return False
    src = P(*MODELS[1][1].split("/"))
    print("[correctif] création de l'encodeur texte compatible stable-diffusion.cpp (≈ 3 min, ≈ 9 Go écrits)")
    subprocess.run([sys.executable, P("tools", "fix_int8_te.py"), src, fixed], check=True)
    return True


def step_shortcut(check_only):
    lnk = P("Qwen-Image.lnk")
    if check_only:
        print("[raccourci] " + ("présent" if os.path.exists(lnk) else "absent"))
        return True
    try:
        subprocess.run([sys.executable, P("tools", "make_shortcut.py")], check=True)
    except Exception as e:
        print(f"[raccourci] non créé ({e}). Lancez l'application avec : venv\\Scripts\\python.exe tools\\launch.py")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-cpu", action="store_true", help="ne pas installer le moteur de secours CPU")
    ap.add_argument("--check", action="store_true", help="vérifier sans rien télécharger")
    a = ap.parse_args()
    if os.name != "nt":
        sys.exit("Ce projet cible Windows (binaires stable-diffusion.cpp Windows). Voir le README pour les autres systèmes.")
    for d in ("models/diffusion_models", "models/text_encoders", "models/vae", "outputs", "logs", "jobs"):
        os.makedirs(P(*d.split("/")), exist_ok=True)
    backends = ["vulkan"] + ([] if a.no_cpu else ["cpu"])
    ok = step_engine(backends, a.check)
    ok = step_models(a.check) and ok
    ok = step_fix(a.check) and ok
    step_shortcut(a.check)
    if a.check:
        print("\nÉtat : " + ("complet" if ok else "incomplet, lancez : venv\\Scripts\\python.exe setup.py"))
    else:
        print("\nInstallation terminée. Démarrage : double-clic sur Qwen-Image.lnk,")
        print("ou : venv\\Scripts\\python.exe tools\\launch.py   puis http://127.0.0.1:7860/")


if __name__ == "__main__":
    main()
