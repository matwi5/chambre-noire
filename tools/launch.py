r"""Lanceur unique : interface web locale + moteur stable-diffusion.cpp (sd-cli lancé à chaque génération).

  Windows : venv\Scripts\python.exe tools\launch.py [--port 7860] [--backend vulkan|cuda|cpu] [--model q4|q8] [--no-browser]
  macOS   : venv/bin/python tools/launch.py [--port 7860] [--model q4|q8] [--no-browser]

- L'interface écoute sur 127.0.0.1:<port> et sert tools/ui/index.html. Avec --lan, elle écoute aussi sur le Wi-Fi
  (téléphone, tablette) : les appareils autres que le Mac doivent saisir une fois le code d'accès de
  tools/access_code.txt, créé au premier lancement ; sur macOS, le Mac ne se met pas en veille tant que le lanceur tourne.
- Chaque génération lance sd-cli (rechargement quasi instantané grâce à --mmap et au cache disque),
  lit sa progression (étape k/N, secondes par étape), expose des aperçus intermédiaires optionnels et enregistre
  le PNG final dans outputs/.
- Mode incognito ({"incognito": true} dans /api/generate) : rien n'est gardé sur le disque. Les fichiers de travail
  (références, aperçus, PNG final) vivent dans jobs/incognito_<id>/, supprimé dès la fin du job ; l'image reste en
  mémoire jusqu'à ce que l'interface la récupère (GET /api/job/<id>/result), puis l'interface fait oublier le job
  (POST /api/job/<id>/forget). Ni journal, ni galerie, ni calibration, ni ligne dans logs/.
- API : POST /api/generate, GET /api/job/<id>, GET /api/job/<id>/preview, POST /api/job/<id>/cancel,
        GET /api/job/<id>/result et POST /api/job/<id>/forget (incognito),
        GET /api/result?name=<png>[&download=1], GET /api/status,
        historique : GET /api/history, GET /api/thumb?name=<png>, POST /api/delete {"name": <png>},
        images d'entrée d'une image : GET /api/input?name=<png>&file=<init.png|ref_N.png>[&thumb=1][&download=1],
        notifications de fin de génération : GET /api/push/key, POST /api/push/subscribe {"subscription": …},
        POST /api/push/unsubscribe {"endpoint": …}.
- Notifications (Web Push, bibliothèque pywebpush) : à la fin de chaque génération, le Mac envoie une notification à
  chaque appareil abonné, même si l'application y est fermée. Clé d'envoi propre à la machine dans
  tools/push_vapid.pem, appareils abonnés dans tools/push_subscriptions.json (non versionnés). Jamais le prompt.
Aucun droit administrateur, aucune modification système : tout reste dans ce dossier.
"""
import argparse, base64, datetime, glob, hashlib, hmac, io, json, math, os, queue, re, secrets, shutil, socket, subprocess, sys, threading, time, uuid, webbrowser
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estimate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
CONFIG = P("tools", "config.json")
DIFFUSION = {   # versions du modèle de diffusion installables par setup.py (q8 : option --q8)
    "q4": P("models", "diffusion_models", "qwen-image-2.1-UC-Q4_K_M.gguf"),
    "q8": P("models", "diffusion_models", "qwen-image-2.1-UC-Q8_0.gguf"),
}
MODELS = {
    "diffusion": DIFFUSION["q4"],   # remplacé au démarrage selon --model
    "vae": P("models", "vae", "qwen_image_2.1_vae_bf16.safetensors"),
    "llm": P("models", "text_encoders", "qwen3vl_8b_int8_convrot_embfix.safetensors"),
}
if sys.platform == "darwin":   # Metal n'a pas de calcul int8 : encodeur GGUF officiel et sa tour vision, sur le GPU
    MODELS["llm"] = P("models", "text_encoders", "Qwen3VL-8B-Instruct-Q8_0.gguf")
    MODELS["llm_vision"] = P("models", "text_encoders", "mmproj-Qwen3VL-8B-Instruct-F16.gguf")
EXE = "sd-cli.exe" if os.name == "nt" else "sd-cli"
# moteurs de la plateforme, par ordre de repli quand celui demandé n'est pas installé
PLATFORM_BACKENDS = ["metal"] if sys.platform == "darwin" else ["vulkan", "cuda", "cpu"]
# vitesse du dernier pas : « 3/8 - 12.30s/it », ou « 3/8 - 1.52it/s » quand un pas dure moins d'une seconde
PROGRESS_RE = re.compile(r"(\d+)/(\d+)\s*-\s*([\d.]+)(s/it|it/s)")
TAKING_RE = re.compile(r"taking ([\d.]+)\s*s")
CALIB = P("tools", "calibration.json")
# Répartition par backend. CUDA : tout sur la carte (l'encodeur int8 convrot a un chemin CUDA natif, RTX 20xx+) ;
# --offload-to-cpu garde les poids en RAM et les copie à la demande, ce qui s'adapte à toute taille de VRAM.
# --mmap : rechargement quasi instantané du modèle d'une génération à l'autre grâce au cache disque.
BACKENDS = {
    "vulkan": ["--backend", "diffusion=vulkan0,vae=vulkan0,te=cpu", "--offload-to-cpu", "--mmap"],
    "cuda":   ["--backend", "cuda0", "--offload-to-cpu", "--diffusion-fa", "--mmap"],
    "cpu":    ["--backend", "cpu", "--mmap"],
    # Metal (Mac Apple Silicon, mesuré sur M6 avec sd.cpp d637cfb, release master-959) : tout sur le GPU.
    # - encodeur GGUF Q8_0 : 3 s pour une édition 512×512, contre 150 s pour l'encodeur int8 sur le CPU
    #   (Metal n'a pas de noyau int8 : kernel_mul_mm_i8_i8 absent, sd-cli plante si on l'y place) ;
    # - VAE : décodage 11 fois plus rapide que sur le CPU (3 s contre 37 s en 512×512) ;
    # - --fa (flash attention partout) : sans elle, la tour vision provoque une faute mémoire du GPU sur une
    #   référence en 2048×2048 ;
    # - --params-backend te=disk : poids de l'encodeur libérés après l'encodage ; en 2048×2048 avec une référence,
    #   la place libérée garde le cache de préfixe (sinon abandonné faute de mémoire) ; coût négligeable sinon ;
    # - --mmap : les poids projetés en mémoire passent par des tampons Metal ; rechargement quasi instantané.
    "metal":  ["--backend", "MTL0", "--fa", "--mmap", "--params-backend", "te=disk"],
}


def record_calib(job):
    """Ajoute la mesure de la génération aux données de calibration (voir tools/estimate.py)."""
    sample = estimate.make_sample(job, S.engine)
    if not sample:
        return
    S.store.add(S.backend, S.model, sample)
    c = S.store.coefficients(S.backend, S.model, S.engine)
    print(f"[calibration] {S.backend}/{S.model} : étape {sample['step']:.2f} s ({sample['w']}×{sample['h']}"
          f"{', ' + str(len(job.get('ref_px') or [])) + ' réf.' if job.get('ref_px') else ''}), "
          f"encodage {sample['enc']:.0f} s, décodage {sample['vae']:.0f} s — {c['samples']} mesure{'s' if c['samples'] > 1 else ''}", flush=True)


def load_config():
    cfg = {"backend": "vulkan", "ui_port": 7860, "cfg_scale": 1.0, "extra_args": []}
    if os.path.exists(CONFIG):
        cfg.update(json.load(open(CONFIG, encoding="utf-8")))
    return cfg


def engine_tag(backend):
    """Release de sd.cpp installée pour ce moteur (sdcpp/<moteur>/.installed, écrit par setup.py) ; une installation
    antérieure à ce marqueur est la première release épinglée."""
    try:
        return open(P("sdcpp", backend, ".installed"), encoding="utf-8").read().strip() or estimate.LEGACY_ENGINE
    except OSError:
        return estimate.LEGACY_ENGINE


def default_backend(cfg):
    """Moteur de config.json, ou celui de la plateforme si config.json en nomme un d'une autre (vulkan sur Mac)."""
    return cfg["backend"] if cfg["backend"] in PLATFORM_BACKENDS else PLATFORM_BACKENDS[0]


ACCESS_FILE = P("tools", "access_code.txt")
ACCESS_COOKIE = "qwen_access"
LOCAL_CLIENTS = ("127.0.0.1", "::1")
# fichiers de tools/ui servis sans code d'accès pour l'installation sur le téléphone (rien de personnel)
PUBLIC_FILES = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
    "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}
LOGIN_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Qwen-Image 2.1 local</title>
<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0b0a16" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#eceef7" media="(prefers-color-scheme: light)">
<style>
:root{color-scheme:dark;--void:#0b0a16;--ink:#f6f4ff;--ink2:rgba(236,233,255,.68);--iris:#8f7cff;--iris2:#b9a9ff;--err:#ff6b7a;
--glass:rgba(255,255,255,.07);--glass-hi:rgba(255,255,255,.15);--field:rgba(8,6,20,.32);--rim:rgba(255,255,255,.14)}
@media (prefers-color-scheme:light){:root{color-scheme:light;--void:#eceef7;--ink:#15131f;--ink2:rgba(21,19,31,.64);--iris:#6a52ff;
--iris2:#8f7cff;--err:#d93a4a;--glass:rgba(255,255,255,.42);--glass-hi:rgba(255,255,255,.78);--field:rgba(255,255,255,.55);--rim:rgba(255,255,255,.75)}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;display:grid;place-items:center;padding:16px;background:var(--void);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:-20%;z-index:-1;pointer-events:none;
background:radial-gradient(40% 35% at 20% 18%,rgba(143,124,255,.6),transparent 70%),radial-gradient(38% 32% at 85% 30%,rgba(255,120,190,.35),transparent 70%),
radial-gradient(45% 40% at 60% 92%,rgba(60,200,255,.3),transparent 70%)}
form{width:100%;max-width:360px;padding:28px 22px 22px;border-radius:30px;text-align:center;border:1px solid var(--rim);
background:linear-gradient(180deg,var(--glass-hi),var(--glass));-webkit-backdrop-filter:blur(26px) saturate(185%);backdrop-filter:blur(26px) saturate(185%);
box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 18px 50px -18px rgba(0,0,0,.6)}
.logo{width:52px;height:52px;margin:0 auto 14px;border-radius:16px;display:grid;place-items:center;color:#fff;font-weight:800;font-size:24px;
background:radial-gradient(120% 120% at 25% 15%,#d4c9ff,var(--iris) 45%,#5a3fd8);box-shadow:inset 0 1px 0 rgba(255,255,255,.55),0 10px 26px -6px rgba(143,124,255,.75)}
h1{font-size:22px;letter-spacing:-.02em;margin:0 0 6px}
p{color:var(--ink2);margin:0 0 20px;font-size:14.5px}
input{width:100%;font:inherit;font-size:24px;font-weight:650;letter-spacing:.16em;text-align:center;padding:14px;border-radius:18px;
border:1px solid var(--rim);background:var(--field);color:var(--ink);outline:none}
input:focus{border-color:var(--iris2)}
input::placeholder{color:var(--ink2);opacity:.5}
button{width:100%;margin-top:12px;font:inherit;font-size:17px;font-weight:700;padding:15px;border:0;border-radius:999px;color:#fff;cursor:pointer;
background:linear-gradient(180deg,color-mix(in srgb,var(--iris2) 70%,var(--iris)),var(--iris));
box-shadow:inset 0 1px 0 rgba(255,255,255,.45),0 10px 26px -8px var(--iris)}
button:disabled{opacity:.6}
#err{color:var(--err);font-size:14px;min-height:21px;margin-top:10px}
.shake{animation:shake .4s}
@keyframes shake{20%,60%{transform:translateX(-8px)}40%,80%{transform:translateX(8px)}}
@media (prefers-reduced-motion:reduce){.shake{animation:none}}
</style></head><body><form id="f"><div class="logo" aria-hidden="true">Q</div><h1>Qwen-Image</h1>
<p>Saisissez le code d'accès affiché sur le Mac, sous le bouton « Téléphone » en haut de l'interface. Il n'est demandé qu'une fois sur cet appareil.</p>
<input id="c" aria-label="Code d'accès" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" placeholder="xxxx-xxxx" autofocus>
<button id="b">Entrer</button><div id="err" role="alert"></div></form>
<script>
const f=document.getElementById('f'), b=document.getElementById('b'), err=document.getElementById('err');
f.onsubmit=async e=>{e.preventDefault(); b.disabled=true; err.textContent='';
 const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.getElementById('c').value})});
 if(r.ok) return location.replace('/');
 b.disabled=false; err.textContent='Code incorrect.'; f.classList.remove('shake'); void f.offsetWidth; f.classList.add('shake');};
</script></body></html>"""


THUMBS = P("outputs", ".thumbs")
PUSH_KEY = P("tools", "push_vapid.pem")
PUSH_SUBS = P("tools", "push_subscriptions.json")
PUSH_LOCK = threading.Lock()


def push_vapid():
    """Clé d'envoi des notifications (VAPID), créée au premier usage ; None si pywebpush n'est pas installé."""
    try:
        from py_vapid import Vapid
    except ImportError:
        return None
    with PUSH_LOCK:
        if not os.path.exists(PUSH_KEY):
            v = Vapid()
            v.generate_keys()
            v.save_key(PUSH_KEY)
            os.chmod(PUSH_KEY, 0o600)
        return Vapid.from_file(PUSH_KEY)


def push_public_key():
    """Clé publique d'envoi, au format attendu par pushManager.subscribe (point non compressé, base64url)."""
    v = push_vapid()
    if not v:
        return None
    from cryptography.hazmat.primitives import serialization
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def push_subscriptions(update=None):
    """Appareils abonnés (abonnements Web Push) ; update(liste) modifie la liste et l'enregistre."""
    with PUSH_LOCK:
        try:
            subs = json.load(open(PUSH_SUBS, encoding="utf-8"))
        except (OSError, ValueError):
            subs = []
        if update:
            subs = update(subs)
            with open(PUSH_SUBS, "w", encoding="utf-8") as f:
                json.dump(subs, f)
            os.chmod(PUSH_SUBS, 0o600)
        return subs


def notify_job(job):
    """Notification de fin de génération à tous les appareils abonnés, dans un thread pour ne pas retarder la file.
    Ni prompt ni nom de fichier : le message transite (chiffré) par le service de notification du navigateur."""
    subs = push_subscriptions()
    if not subs or job.get("calibration"):
        return
    secs = job.get("seconds") or 0
    duree = f"{int(secs // 60)} min {int(secs % 60):02d} s" if secs >= 60 else f"{int(secs)} s"
    if job.get("status") == "done":
        dims = "×".join(str(d) for d in job.get("dims") or [])
        payload = {"title": "Image incognito prête" if job.get("incognito") else "Image prête",
                   "body": f"Générée en {duree}" + (f" · {dims}" if dims else "")}
    else:
        payload = {"title": "Échec de la génération", "body": "Ouvrez l'application pour voir le détail."}
    payload.update(tag="qwen-image-job", url="/")

    def send():
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            return
        vapid, gone, sent = push_vapid(), set(), 0
        for sub in subs:
            try:
                webpush(sub, json.dumps(payload, ensure_ascii=False), vapid_private_key=vapid,
                        vapid_claims={"sub": "mailto:qwen-image-local@example.com"}, ttl=86400, timeout=15)   # téléphone hors ligne : remise jusqu'à 24 h après
                sent += 1
            except WebPushException as e:
                if e.response is not None and e.response.status_code in (404, 410):   # appareil désabonné
                    gone.add(sub.get("endpoint"))
                else:
                    print(f"[push] envoi impossible : {e}", flush=True)
            except Exception as e:
                print(f"[push] envoi impossible : {e}", flush=True)
        if gone:
            push_subscriptions(lambda l: [x for x in l if x.get("endpoint") not in gone])
        print(f"[push] notification envoyée à {sent} appareil{'s' if sent > 1 else ''}", flush=True)
    threading.Thread(target=send, daemon=True).start()
INPUTS = P("outputs", ".inputs")      # images d'entrée de chaque image de outputs/ : .inputs/<nom sans .png>/
INPUT_RE = re.compile(r"(init|ref_\d+)\.png")


def input_files(job_dir):
    """Images d'entrée d'un dossier de travail : image d'origine (init.png) puis références (ref_1.png…), dans l'ordre."""
    names = [n for n in os.listdir(job_dir) if INPUT_RE.fullmatch(n)] if os.path.isdir(job_dir) else []
    return sorted(names, key=lambda n: (n != "init.png", int(re.sub(r"\D", "", n) or 0)))


def save_inputs(job_dir, out_png):
    """Copie les images d'entrée d'un job à côté de son image, pour les revoir depuis la galerie."""
    names = input_files(job_dir)
    if names:
        dst = os.path.join(INPUTS, os.path.basename(out_png)[:-4])
        os.makedirs(dst, exist_ok=True)
        for n in names:
            shutil.copy2(os.path.join(job_dir, n), os.path.join(dst, n))


def output_path(name):
    """Chemin d'une image de outputs/ à partir de son nom, ou None si le nom sort du dossier ou n'est pas un PNG."""
    name = os.path.basename(str(name or ""))
    if not name or name.startswith(".") or not name.lower().endswith(".png"):
        return None
    fp = P("outputs", name)
    return fp if os.path.isfile(fp) else None


def history():
    """Images de outputs/, la plus récente d'abord, avec les réglages notés dans outputs/journal.jsonl."""
    meta = {}
    try:
        with open(P("outputs", "journal.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                meta[os.path.basename(m.get("file") or "")] = m
    except OSError:
        pass
    items = []
    for fp in glob.glob(P("outputs", "*.png")):
        name, st = os.path.basename(fp), os.stat(fp)
        m = meta.get(name, {})
        items.append({"name": name, "time": int(st.st_mtime), "size": st.st_size, "mode": m.get("mode"),
                      "prompt": m.get("prompt"), "width": m.get("width"), "height": m.get("height"),
                      "steps": m.get("steps"), "seconds": m.get("seconds"), "model": m.get("model"),
                      "inputs": input_files(os.path.join(INPUTS, name[:-4]))})
    return sorted(items, key=lambda x: x["time"], reverse=True)


def thumbnail(fp, th=None):
    """Miniature JPEG de 320 px (côté le plus long), gardée dans outputs/.thumbs/ et refaite si l'image change."""
    th = th or os.path.join(THUMBS, os.path.basename(fp)[:-4] + ".jpg")
    if not os.path.exists(th) or os.path.getmtime(th) < os.path.getmtime(fp):
        from PIL import Image
        os.makedirs(THUMBS, exist_ok=True)
        tmp = f"{th}.{threading.get_ident()}.tmp"   # écrite à côté puis renommée : jamais lue à moitié écrite
        with Image.open(fp) as im:
            im = im.convert("RGB")
            im.thumbnail((320, 320))
            im.save(tmp, "JPEG", quality=82)
        os.replace(tmp, th)
    return th


def normalize_code(code):
    return re.sub(r"[^a-z0-9]", "", str(code).lower())


def access_token(code):
    """Valeur du cookie d'accès : empreinte du code (le code lui-même ne circule pas dans le cookie)."""
    return hashlib.sha256(("qwen-image-local:" + normalize_code(code)).encode()).hexdigest()


def load_access_code():
    """Code d'accès des appareils du Wi-Fi : créé au premier lancement avec --lan, gardé dans tools/access_code.txt."""
    if os.path.exists(ACCESS_FILE):
        code = open(ACCESS_FILE, encoding="utf-8").read().strip()
        if len(normalize_code(code)) >= 6:
            return code
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"          # sans caractères ambigus (0/o, 1/l/i)
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    code = raw[:4] + "-" + raw[4:]
    with open(ACCESS_FILE, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    os.chmod(ACCESS_FILE, 0o600)
    return code


def lan_address():
    """Nom Bonjour (.local) et adresse IP du Mac sur le réseau local, pour l'afficher à l'utilisateur."""
    name = None
    if sys.platform == "darwin":
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip() + ".local"
        except OSError:
            pass
    ip = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:   # aucune donnée envoyée : choisit l'interface sortante
            sk.connect(("192.0.2.1", 9))
            ip = sk.getsockname()[0]
    except OSError:
        pass
    return name or ip, ip


def tailscale_json(*args):
    """Sortie JSON d'une commande tailscale, ou None si Tailscale n'est pas installé ou ne répond pas."""
    exe = shutil.which("tailscale") or next((p for p in ("/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale",
                                                          "/Applications/Tailscale.app/Contents/MacOS/Tailscale")
                                             if os.path.exists(p)), None)
    if not exe:
        return None
    try:
        return json.loads(subprocess.run([exe, *args, "--json"], capture_output=True, text=True, timeout=5).stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def tailscale_hosts():
    """Noms et adresse IPv4 du Mac sur Tailscale (court, MagicDNS complet, 100.x), pour un accès hors du Wi-Fi.
    Liste vide si Tailscale n'est pas installé ou pas connecté."""
    st = tailscale_json("status")
    if not st or st.get("BackendState") != "Running":
        return []
    me = st.get("Self") or {}
    dns = (me.get("DNSName") or "").rstrip(".").lower()
    ipv4 = [x for x in me.get("TailscaleIPs") or [] if "." in x]   # IPv6 écartée : il faudrait des crochets dans l'URL
    return [h for h in (dns.split(".")[0], dns, *ipv4) if h]


def tailscale_serve_url(dns, port):
    """Adresse HTTPS de l'interface si « tailscale serve » la publie (https://<nom MagicDNS>/ vers le port local),
    sinon None. Le HTTPS rend l'interface installable comme une application sur le téléphone."""
    web = (tailscale_json("serve", "status") or {}).get("Web") or {}
    handler = ((web.get(f"{dns}:443") or {}).get("Handlers") or {}).get("/") or {}
    return f"https://{dns}/" if re.fullmatch(rf"(https?://)?(127\.0\.0\.1|localhost):{port}/?", handler.get("Proxy", "")) else None


class State:
    backend = "vulkan"
    engine = estimate.LEGACY_ENGINE   # release de sd.cpp du moteur choisi
    model = "q4"
    store = None
    access_code = None       # avec --lan : code demandé aux appareils autres que le Mac
    access_token = None      # valeur du cookie posé après saisie du code (empreinte du code, pas le code)
    lan_urls = []            # adresses affichées pour le téléphone
    lan_hosts = set()        # noms d'hôte admis en plus des noms locaux (ceux de lan_urls et le nom HTTPS de Tailscale)
    cfg = {}
    ui_port = 7860
    jobs = {}
    q = queue.Queue()
    current = None


S = State()


def data_url_bytes(data_url):
    return base64.b64decode(data_url.split(",", 1)[1] if "," in data_url else data_url)


def write_data_url(data_url, path, what="image d'entrée"):
    """Écrit l'image d'une data URL dans path et renvoie ses dimensions ; ValueError « <what> illisible » si ce n'est
    pas une image que Pillow sait lire."""
    try:
        with open(path, "wb") as f:
            f.write(data_url_bytes(data_url))
        return image_size(path)
    except (ValueError, OSError) as e:          # base64 invalide, fichier qui n'est pas une image
        raise ValueError(f"{what} illisible") from e


def image_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def build_cmd(job):
    d = job["dir"]
    r = job["req"]
    w, h = int(r["width"]), int(r["height"])
    cmd = [P("sdcpp", S.backend, EXE),
           "--diffusion-model", MODELS["diffusion"], "--vae", MODELS["vae"], "--llm", MODELS["llm"]] + (
           ["--llm_vision", MODELS["llm_vision"]] if "llm_vision" in MODELS else []) + BACKENDS[S.backend] + [
           "-p", r["prompt"], "-W", str(r["width"]), "-H", str(r["height"]),
           "--steps", str(r["steps"]), "--cfg-scale", str(r.get("cfg", S.cfg.get("cfg_scale", 1.0))),
           "--sampling-method", "euler", "-s", str(r.get("seed", -1)), "-o", job["out"]]
    if r.get("negative_prompt"):
        cmd += ["-n", r["negative_prompt"]]
    job["ref_px"] = []
    for i, ref in enumerate(r.get("ref_images") or []):
        f = os.path.join(d, f"ref_{i+1}.png")
        job["ref_px"].append(estimate.ref_px(*write_data_url(ref, f, f"image de référence {i+1}"), w, h))   # telles que sd.cpp les redimensionne
        cmd += ["-r", f]
    if r.get("init_image"):
        write_data_url(r["init_image"], os.path.join(d, "init.png"), "image d'origine")
        cmd += ["-i", os.path.join(d, "init.png"), "--strength", str(r.get("strength", 1.0))]
        job["init_px"] = w * h
    if r.get("mask_image"):
        write_data_url(r["mask_image"], os.path.join(d, "mask.png"), "masque")
        cmd += ["--mask", os.path.join(d, "mask.png")]
    if r.get("preview"):
        interval = int(r.get("preview_interval") or 5)
        cmd += ["--preview", "vae", "--preview-path", os.path.join(d, "preview_%03d.png"), "--preview-interval", str(interval)]
        job["preview_interval"] = interval
    cmd += list(S.cfg.get("extra_args", []))
    return cmd


def latest_preview(job):
    files = sorted(glob.glob(os.path.join(job["dir"], "preview_*.png")), key=os.path.getmtime)
    if not files:
        return
    f = files[-1]
    try:
        size = os.path.getsize(f)
    except OSError:
        return
    if size > 1000 and (job.get("preview") != f or job.get("preview_size") != size):
        job["preview"] = f
        job["preview_size"] = size
        job["preview_version"] = job.get("preview_version", 0) + 1


def run_job(job):
    job["status"] = "running"
    job["started"] = time.time()
    job["phase"] = "chargement du modèle"
    cmd = build_cmd(job)
    job["cmd"] = " ".join(cmd)
    logf = open(os.devnull if job.get("incognito") else os.path.join(job["dir"], "sd-cli.log"), "wb")
    try:
        proc = subprocess.Popen(cmd, cwd=P("sdcpp", S.backend), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        job["status"] = "failed"
        job["error"] = f"impossible de lancer sd-cli : {e}"
        logf.close()
        return
    job["proc"] = proc
    buf = b""
    tail = []
    fd = proc.stdout.fileno()
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            chunk = b""
        if not chunk:
            break
        logf.write(chunk)
        buf += chunk
        while True:
            m = re.search(rb"[\r\n]", buf)
            if not m:
                break
            line, buf = buf[:m.start()], buf[m.end():]
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            tail.append(text)
            tail[:] = tail[-8:]
            pm = PROGRESS_RE.search(text)
            if pm:
                speed = float(pm.group(3))
                job["step"], job["total"] = int(pm.group(1)), int(pm.group(2))
                job["sec_per_it"] = speed if pm.group(4) == "s/it" else round(1 / max(speed, 1e-6), 3)
                times = job.setdefault("step_times", {})
                times[job["step"]] = job["sec_per_it"]
                # temps restant : moyenne des 3 derniers pas, sans le premier (il charge les poids) s'il y en a d'autres
                recent = [t for k, t in sorted(times.items()) if k > 1][-3:] or list(times.values())
                job["sec_per_it_recent"] = round(sum(recent) / len(recent), 3)
                job["phase"] = "génération"
                if job.get("preview_interval"):
                    latest_preview(job)
            elif "loading llm" in text or "loading diffusion model" in text:
                job["phase"] = "chargement du modèle"
            elif "computing condition graph" in text or "Version:" in text:
                job["phase"] = "encodage du prompt" + (" et des images" if job["req"].get("ref_images") else "")
            elif "encode_first_stage completed" in text:
                t = TAKING_RE.search(text)
                if t:
                    job["venc_seconds"] = float(t.group(1))
            elif "get_learned_condition completed" in text:
                job["phase"] = "génération"
                job["encode_seconds"] = round(time.time() - job["started"], 1)
                t = TAKING_RE.search(text)
                if t:
                    job["encode_seconds_net"] = float(t.group(1))
            elif "sampling completed" in text:
                job["phase"] = "décodage VAE"
                t = TAKING_RE.search(text)
                if t:
                    job["sampling_seconds"] = float(t.group(1))
            elif "decode_first_stage completed" in text:
                t = TAKING_RE.search(text)
                if t:
                    job["vae_seconds"] = float(t.group(1))
            elif "[ERROR" in text or text.startswith("[E]") or "GGML_ASSERT" in text:   # [E] : journaux de master-959
                job["error_lines"] = (job.get("error_lines") or []) + [text]
    rc = proc.wait()
    logf.close()
    job["finished"] = time.time()
    job["seconds"] = round(job["finished"] - job["started"], 1)
    if job.get("status") == "cancelled":
        discard_cancelled(job)
        return
    if rc == 0 and os.path.exists(job["out"]):
        try:
            from PIL import Image
            with Image.open(job["out"]) as im:
                job["dims"] = list(im.size)
        except Exception:
            job["dims"] = [job["req"]["width"], job["req"]["height"]]
        job["size"] = os.path.getsize(job["out"])
        if job.get("incognito"):                 # image gardée en mémoire seulement ; dossier supprimé par worker()
            with open(job["out"], "rb") as f:
                job["png"] = f.read()
            job["status"] = "done"
            job["phase"] = "terminé"
            return
        job["status"] = "done"
        job["phase"] = "terminé"
        if not job.get("calibration"):            # les générations de tools/calibrate.py restent hors du journal
            meta = {"mode": job["req"].get("mode"), "prompt": job["req"]["prompt"], "width": job["req"]["width"], "height": job["req"]["height"],
                    "steps": job["req"]["steps"], "seed": job["req"].get("seed"), "seconds": job["seconds"], "encode_seconds": job.get("encode_seconds"),
                    "sec_per_it": job.get("sec_per_it"), "file": job["out"], "size": job["size"], "backend": S.backend, "model": S.model}
            with open(P("outputs", "journal.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            try:
                save_inputs(job["dir"], job["out"])
            except OSError as e:
                print(f"[job] images d'entrée non conservées : {e}", flush=True)
            print(f"[job] PNG enregistré : {job['out']} ({job['size']} octets, {job['seconds']} s)", flush=True)
        try:
            record_calib(job)
        except Exception as e:
            print(f"[calibration] ignorée : {e}", flush=True)
    else:
        job["status"] = "failed"
        job["error"] = "sd-cli code " + str(rc) + " — " + " | ".join((job.get("error_lines") or tail)[-4:])
        # en incognito, le détail (qui peut citer le prompt) reste en mémoire pour l'interface, hors de logs/
        print("[job] échec : " + (f"génération incognito, sd-cli code {rc}" if job.get("incognito") else job["error"]), flush=True)


def discard_cancelled(job):
    """Génération annulée : rien n'en reste sur le disque, ni le dossier de travail (images d'entrée, aperçus, journal du
    moteur), ni une image finale que sd-cli aurait commencé à écrire avant d'être arrêté."""
    shutil.rmtree(job["dir"], ignore_errors=True)
    try:
        os.remove(job["out"])
    except OSError:
        pass


def forget_files(job):
    """Fin d'un job incognito : supprime son dossier de travail et retire de la mémoire le prompt, les images d'entrée et
    la ligne de commande ; seule l'image finale (job["png"]) reste, jusqu'à sa récupération par l'interface."""
    shutil.rmtree(job["dir"], ignore_errors=True)
    for k in ("req", "cmd", "error_lines", "preview", "step_times"):
        job.pop(k, None)


def fail_job(job, e):
    """Exception pendant la préparation ou l'exécution d'une génération : elle échoue seule, avec un message lisible,
    et le moteur est arrêté s'il tournait. Une génération annulée entre-temps ne laisse rien, comme d'habitude."""
    proc = job.get("proc")
    if proc and proc.poll() is None:
        proc.kill()
        proc.wait()
    if job.get("status") == "cancelled":
        discard_cancelled(job)
        return
    if job.get("status") == "done":             # image produite, journal ou calibration en échec : elle reste réussie
        print("[job] fin de génération incomplète" + ("" if job.get("incognito") else f" : {e}"), flush=True)
        return
    job["status"], job["phase"] = "failed", "échec"
    job["error"] = f"génération impossible : {e}"
    job.setdefault("finished", time.time())
    # en incognito, le détail (qui peut citer un fichier de travail) reste en mémoire pour l'interface, hors de logs/
    print("[job] échec : " + ("génération incognito, erreur de préparation" if job.get("incognito") else job["error"]), flush=True)


def worker():
    """Thread de calcul : une génération à la fois, dans l'ordre de la file. Aucune exception ne l'arrête : la
    génération en cause échoue et la suivante démarre."""
    while True:
        job = S.q.get()
        try:
            if job.get("status") == "cancelled":       # annulée avant de démarrer
                discard_cancelled(job)
                continue
            S.current = job["id"]
            try:
                run_job(job)
            except Exception as e:
                fail_job(job, e)
            if job.get("status") in ("done", "failed"):
                notify_job(job)
        except Exception as e:
            print("[job] erreur du thread de calcul" + ("" if job.get("incognito") else f" : {e}"), flush=True)
        finally:
            S.current = None
            job.pop("proc", None)
            if job.get("incognito"):
                forget_files(job)


def request_error(req):
    """Motif de refus d'une demande de génération (400), ou None : les champs que build_cmd utilise doivent avoir le bon
    type, pour qu'une demande invalide soit refusée tout de suite au lieu d'échouer dans la file."""
    is_int = lambda v: isinstance(v, int) and not isinstance(v, bool)
    is_num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not isinstance(req, dict):
        return "objet JSON attendu"
    if not isinstance(req.get("prompt"), str) or not req["prompt"].strip():
        return "prompt vide ou non textuel"
    for key, label, lo, hi in (("width", "largeur", 64, 4096), ("height", "hauteur", 64, 4096), ("steps", "étapes", 1, 200)):
        if not is_int(req.get(key)) or not lo <= req[key] <= hi:
            return f"{label} : nombre entier de {lo} à {hi} attendu"
    seed = req.get("seed", -1)
    if not is_int(seed) or not -1 <= seed < 2 ** 63:
        return "graine : nombre entier attendu (-1 pour une graine au hasard)"
    for key in ("cfg", "strength"):
        if key in req and not is_num(req[key]):
            return f"{key} : nombre fini attendu"
    if req.get("preview_interval") is not None and not (is_int(req["preview_interval"]) and req["preview_interval"] >= 1):
        return "preview_interval : nombre entier positif attendu"
    for key in ("negative_prompt", "init_image", "mask_image"):
        if req.get(key) is not None and not isinstance(req[key], str):
            return f"{key} : texte attendu"
    refs = req.get("ref_images")
    if refs is not None and not (isinstance(refs, list) and all(isinstance(x, str) for x in refs)):
        return "ref_images : liste d'images (data URL) attendue"
    if not isinstance(req.get("mode", "img"), str):
        return "mode : texte attendu"
    return None


ACTIVE = ("queued", "running")


def active_jobs():
    """Générations de la file : celle en cours d'abord, puis les autres dans l'ordre d'arrivée (S.jobs garde l'ordre
    d'insertion, qui est celui de S.q)."""
    return sorted((j for j in list(S.jobs.values()) if j.get("status") in ACTIVE), key=lambda j: j.get("status") != "running")


def queue_position(job):
    """Nombre de générations devant celle-ci dans la file (0 : en cours ou la prochaine), None si elle n'y est plus.
    Calculée à chaque lecture : elle avance à mesure que la file se vide."""
    return next((k for k, j in enumerate(active_jobs()) if j is job), None)


def request_inputs(req):
    """Pixels des images d'entrée tels que build_cmd les donnera au moteur, lus dans l'en-tête des images dès la demande,
    pour estimer la durée avant le calcul : (références, image de départ). Une image illisible ne compte pas (elle
    fera échouer sa génération)."""
    from PIL import Image
    w, h, refs = req["width"], req["height"], []
    for ref in req.get("ref_images") or []:
        try:
            with Image.open(io.BytesIO(data_url_bytes(ref))) as im:
                refs.append(estimate.ref_px(*im.size, w, h))
        except Exception:
            pass
    return refs, (w * h if req.get("init_image") else 0)


def queue_entry(job, position, coefs):
    """Entrée de la liste de la file (/api/status). Une génération incognito n'y montre que son genre : ni identifiant
    (seule la page qui l'a lancée peut la suivre ou l'annuler), ni prompt, ni mode. None si la génération vient de
    finir (forget_files a pu retirer sa demande)."""
    r = job.get("req")
    if r is None:
        return None
    refs, init = job["inputs"]
    previews = r["steps"] // (r.get("preview_interval") or 5) if r.get("preview") else 0
    e = {"status": job["status"], "position": position, "lot": None,
         "estimate": round(estimate.predict(coefs, r["width"], r["height"], r["steps"], refs, init, previews), 1),
         "elapsed": round(time.time() - job["started"], 1) if job.get("started") else None}
    if job.get("incognito"):
        e["kind"] = "incognito"
    else:
        prompt = " ".join(r["prompt"].split())
        e.update(kind="normal", id=job["id"], mode=job["mode"], prompt=prompt[:80] + ("…" if len(prompt) > 80 else ""))
    return e


def public(job):
    keys = ("id", "status", "phase", "step", "total", "sec_per_it", "sec_per_it_recent", "started", "finished", "seconds", "encode_seconds",
            "preview_version", "preview_interval", "size", "dims", "error")
    d = {k: job.get(k) for k in keys}
    d["queue_position"] = queue_position(job)
    d["elapsed"] = round(time.time() - job["started"], 1) if job.get("started") and not job.get("finished") else job.get("seconds")
    d["incognito"] = bool(job.get("incognito"))
    d["path"] = job["out"] if job.get("status") == "done" and not job.get("incognito") else None
    d["name"] = os.path.basename(job["out"])
    return d


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Python n'en garde que 5 par défaut : la galerie ouvre une connexion par miniature et, pendant que le processeur les
    # fabrique, les suivantes étaient refusées (« Connection reset by peer », miniature cassée sur le téléphone)
    request_queue_size = 128


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        msg = fmt % args
        if "/api/status" in msg or "/api/job/" in msg:
            return
        sys.stderr.write("[ui] " + msg + "\n")

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _host(self):
        return self.headers.get("Host", "").strip().lower()

    def _local_hosts(self):
        return {f"{h}:{S.ui_port}" for h in ("127.0.0.1", "localhost", "[::1]")}

    def _host_ok(self):
        """Refuse les noms d'hôte inconnus : une page dont le domaine pointe vers 127.0.0.1 (rebinding DNS) arrive avec
        son propre nom dans Host. Sont admis les noms locaux et ceux du Wi-Fi et de Tailscale fixés au démarrage (S.lan_hosts)."""
        return self._host() in self._local_hosts() | S.lan_hosts

    def _proxied(self):
        """Requête relayée par « tailscale serve » (HTTPS) : elle arrive de 127.0.0.1 mais vient d'un autre appareil."""
        return any(self.headers.get(k) is not None for k in ("X-Forwarded-For", "X-Forwarded-Host", "Tailscale-User-Login"))

    def _local(self):
        """Le Mac lui-même : adresse source locale et nom d'hôte local (un nom du Wi-Fi demande le code, même depuis le Mac),
        jamais une requête relayée."""
        return self.client_address[0] in LOCAL_CLIENTS and self._host() in self._local_hosts() and not self._proxied()

    def _post_refused(self):
        """Refus d'un POST venu d'un autre site (CSRF) : (code, motif), ou None s'il vient de l'interface. Un formulaire
        d'un autre site peut poster du JSON en text/plain sans contrôle préalable du navigateur ; exiger
        application/json oblige ce site à une requête que le navigateur ne lui laisse pas faire."""
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            return 403, "requête venant d'un autre site"
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip().lower() not in ("http://" + self._host(), "https://" + self._host()):
            return 403, "requête venant d'un autre site"
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return 415, "Content-Type application/json attendu"
        return None

    def _allowed(self):
        """Le Mac lui-même passe toujours ; un autre appareil doit avoir saisi le code d'accès (cookie). Sans --lan, pas de
        code : seul le Mac passe, une requête relayée par Tailscale est refusée."""
        if self._local():
            return True
        if not S.access_code:
            return not self._proxied()
        morsel = SimpleCookie(self.headers.get("Cookie", "")).get(ACCESS_COOKIE)
        return bool(morsel) and hmac.compare_digest(morsel.value, S.access_token)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "nom d'hôte refusé"})
        path, _, query = self.path.partition("?")
        if path in PUBLIC_FILES:   # manifeste, icônes, service worker : demandés par le navigateur sans le cookie d'accès
            name, ctype = PUBLIC_FILES[path]
            return self._send(200, open(P("tools", "ui", name), "rb").read(), ctype)
        if not self._allowed():
            if path in ("/", "/index.html"):
                return self._send(200, LOGIN_PAGE, "text/html; charset=utf-8")
            return self._send(401, {"error": "code d'accès requis"})
        if path in ("/", "/index.html"):
            return self._send(200, open(P("tools", "ui", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if path == "/api/status":
            missing = [k for k, v in MODELS.items() if not os.path.exists(v)]
            # un job incognito n'est jamais repris après un rechargement de la page : il est perdu avec elle
            last = max((j for j in list(S.jobs.values()) if not j.get("incognito")), key=lambda j: j["created"], default=None)
            coefs, active = S.store.coefficients(S.backend, S.model, S.engine), active_jobs()
            return self._send(200, {"sd_ready": not missing, "backend": S.backend, "busy": S.current is not None,
                                    "detail": ("fichiers manquants : " + ", ".join(missing)) if missing else "prêt",
                                    "model": os.path.basename(MODELS["diffusion"]), "model_version": S.model,
                                    "queued": sum(j["status"] == "queued" for j in active),
                                    "queue": [e for e in (queue_entry(j, k, coefs) for k, j in enumerate(active)) if e],
                                    "current_job": S.current, "last_job": public(last) if last else None,
                                    "estimates": coefs,
                                    # adresse et code pour le téléphone : montrés seulement sur le Mac lui-même
                                    "phone": {"urls": S.lan_urls, "code": S.access_code} if S.access_code and self._local() else None})
        m = re.match(r"^/api/job/([\w-]+)(/preview|/result)?$", path)
        if m:
            job = S.jobs.get(m.group(1))
            if not job:
                return self._send(404, {"error": "job inconnu"})
            if m.group(2) == "/result":           # image d'un job incognito, gardée en mémoire seulement
                png = job.get("png")
                if not png:
                    return self._send(404, {"error": "image incognito indisponible"})
                return self._send(200, png, "image/png")
            if m.group(2):
                if not job.get("preview"):
                    return self._send(404, {"error": "pas d'aperçu"})
                try:
                    return self._send(200, open(job["preview"], "rb").read(), "image/png")
                except OSError:
                    return self._send(404, {"error": "aperçu en cours d'écriture"})
            return self._send(200, public(job))
        q = {k: v[0] for k, v in parse_qs(query).items()}
        if path == "/api/result":
            fp = output_path(q.get("name"))
            if not fp:
                return self._send(404, {"error": "fichier inconnu"})
            extra = {"Content-Disposition": f'attachment; filename="{os.path.basename(fp)}"'} if q.get("download") else None
            return self._send(200, open(fp, "rb").read(), "image/png", extra)
        if path == "/api/history":
            return self._send(200, history())
        if path == "/api/push/key":
            key = push_public_key()
            return self._send(200, {"key": key}) if key else self._send(503, {"error": "pywebpush non installé"})
        if path == "/api/input":                  # image d'entrée d'une image de la galerie
            out, f = output_path(q.get("name")), q.get("file", "")
            fp = os.path.join(INPUTS, os.path.basename(out)[:-4], f) if out and INPUT_RE.fullmatch(f) else None
            if not fp or not os.path.isfile(fp):
                return self._send(404, {"error": "image d'entrée inconnue"})
            if q.get("thumb"):
                try:
                    th = thumbnail(fp, os.path.join(THUMBS, f"{os.path.basename(out)[:-4]}__{f[:-4]}.jpg"))
                    return self._send(200, open(th, "rb").read(), "image/jpeg")
                except Exception as e:
                    return self._send(500, {"error": f"miniature impossible : {e}"})
            extra = {"Content-Disposition": f'attachment; filename="{os.path.basename(out)[:-4]}_{f}"'} if q.get("download") else None
            return self._send(200, open(fp, "rb").read(), "image/png", extra)
        if path == "/api/thumb":
            fp = output_path(q.get("name"))
            if not fp:
                return self._send(404, {"error": "fichier inconnu"})
            try:
                return self._send(200, open(thumbnail(fp), "rb").read(), "image/jpeg")
            except Exception as e:
                return self._send(500, {"error": f"miniature impossible : {e}"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "nom d'hôte refusé"})
        refused = self._post_refused()
        if refused:
            return self._send(refused[0], {"error": refused[1]})
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if path == "/api/login" and S.access_code:
            try:
                code = json.loads(raw).get("code", "")
            except Exception:
                code = ""
            if not hmac.compare_digest(normalize_code(code), normalize_code(S.access_code)):
                time.sleep(1)                      # freine les essais en série
                return self._send(403, {"error": "code incorrect"})
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # Lax et non Strict : Chrome Android compte l'ouverture de l'application installée (écran d'accueil) comme une
            # arrivée d'un autre site et n'enverrait pas un cookie Strict, d'où le code redemandé à chaque ouverture.
            # Lax n'est envoyé d'un autre site que pour l'ouverture d'une page (GET, sans effet) ; les POST restent
            # protégés par _post_refused.
            self.send_header("Set-Cookie", f"{ACCESS_COOKIE}={S.access_token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._allowed():
            return self._send(401, {"error": "code d'accès requis"})
        if path == "/api/delete":
            try:
                fp = output_path(json.loads(raw).get("name"))
            except Exception:
                fp = None
            if not fp:
                return self._send(404, {"error": "fichier inconnu"})
            os.remove(fp)
            stem = os.path.basename(fp)[:-4]
            for th in [os.path.join(THUMBS, stem + ".jpg"), *glob.glob(os.path.join(THUMBS, glob.escape(stem) + "__*.jpg"))]:
                if os.path.exists(th):
                    os.remove(th)
            shutil.rmtree(os.path.join(INPUTS, stem), ignore_errors=True)
            print(f"[historique] supprimé : {os.path.basename(fp)}", flush=True)
            return self._send(200, {"ok": True})
        if path in ("/api/push/subscribe", "/api/push/unsubscribe"):
            try:
                body = json.loads(raw)
            except ValueError:
                body = {}
            sub = body.get("subscription") or {}
            endpoint = sub.get("endpoint") if path.endswith("/subscribe") else body.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
                return self._send(400, {"error": "abonnement invalide"})
            if path.endswith("/subscribe"):
                keys = sub.get("keys") or {}
                if not (isinstance(keys.get("p256dh"), str) and isinstance(keys.get("auth"), str)):
                    return self._send(400, {"error": "abonnement invalide"})
                entry = {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}
                push_subscriptions(lambda l: [x for x in l if x.get("endpoint") != endpoint] + [entry])
            else:
                push_subscriptions(lambda l: [x for x in l if x.get("endpoint") != endpoint])
            return self._send(200, {"ok": True})
        if path == "/api/generate":
            try:
                req = json.loads(raw)
            except Exception as e:
                return self._send(400, {"error": f"JSON invalide : {e}"})
            error = request_error(req)
            if error:
                return self._send(400, {"error": error})
            # une nouvelle génération fait perdre les images incognito terminées, récupérées ou non
            for k in [k for k, j in S.jobs.items() if j.get("incognito") and j.get("status") not in ("queued", "running")]:
                S.jobs.pop(k, None)
            jid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            mode = re.sub(r"[^a-z0-9]", "", str(req.get("mode", "img"))) or "img"
            incognito = req.get("incognito") is True
            d = P("jobs", ("incognito_" if incognito else "") + jid)
            os.makedirs(d, exist_ok=True)
            # en incognito, le PNG reste dans le dossier de travail (supprimé en fin de job) ; son nom sert au téléchargement
            out = os.path.join(d, f"{jid}_{mode}.png") if incognito else P("outputs", f"{jid}_{mode}.png")
            job = {"id": jid, "req": req, "mode": mode, "dir": d, "out": out, "status": "queued", "created": time.time(),
                   "incognito": incognito, "inputs": request_inputs(req)}
            S.jobs[jid] = job
            S.q.put(job)
            return self._send(202, public(job))
        m = re.match(r"^/api/job/([\w-]+)/(cancel|forget)$", path)
        if m:
            job = S.jobs.get(m.group(1))
            if not job:
                return self._send(404, {"error": "job inconnu"})
            if m.group(2) == "forget" and not job.get("incognito"):
                return self._send(400, {"error": "seul un job incognito peut être oublié"})
            if job.get("status") in ("queued", "running"):   # une génération terminée garde son statut et son image
                job["status"] = "cancelled"
                job["phase"] = "annulé"
                proc = job.get("proc")
                if proc and proc.poll() is None:
                    proc.kill()
            if m.group(2) == "forget":            # image récupérée par l'interface, ou page quittée : plus rien en mémoire
                S.jobs.pop(job["id"], None)
                job.pop("png", None)
                return self._send(200, {"ok": True})
            return self._send(200, public(job))
        self._send(404, {"error": "not found"})


def setup_state(cfg, backend, model):
    """Fixe le moteur et le modèle (repli si l'un n'est pas installé) et charge la calibration ; sort si sd-cli manque."""
    S.cfg = cfg
    if not os.path.exists(DIFFUSION[model]) and model != "q4":
        print(f"[launch] modèle {model} absent (setup.py --{model} pour l'installer), repli sur q4", flush=True)
        model = "q4"
    if not os.path.exists(P("sdcpp", backend, EXE)) and backend != PLATFORM_BACKENDS[0]:
        print(f"[launch] moteur {backend} absent (setup.py --{backend} pour l'installer), repli sur {PLATFORM_BACKENDS[0]}", flush=True)
        backend = PLATFORM_BACKENDS[0]
    exe = P("sdcpp", backend, EXE)
    if not os.path.exists(exe):
        py = "venv\\Scripts\\python.exe" if os.name == "nt" else "venv/bin/python"
        sys.exit(f"binaire introuvable : {exe} (lancez : {py} setup.py)")
    S.backend, S.model, S.engine = backend, model, engine_tag(backend)
    MODELS["diffusion"] = DIFFUSION[model]
    S.store = estimate.Store(CALIB)


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=cfg["ui_port"])
    ap.add_argument("--backend", choices=PLATFORM_BACKENDS, default=default_backend(cfg))
    ap.add_argument("--model", choices=list(DIFFUSION), default=cfg.get("model", "q4"),
                    help="q4 (Q4_K_M, par défaut) ou q8 (Q8_0, plus fidèle, installé par setup.py --q8)")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--lan", action="store_true", default=bool(cfg.get("lan")),
                    help="accessible aussi depuis le Wi-Fi (téléphone), avec un code d'accès ; Mac maintenu éveillé")
    a = ap.parse_args()
    S.ui_port = a.port
    setup_state(cfg, a.backend, a.model)
    for d in ("outputs", "logs", "jobs"):
        os.makedirs(P(d), exist_ok=True)
    for old in glob.glob(P("jobs", "incognito_*")):      # restes d'un job incognito interrompu par un arrêt brutal
        shutil.rmtree(old, ignore_errors=True)
    for fp in glob.glob(P("outputs", "*.png")):        # images antérieures à la conservation des entrées : reprises
        stem = os.path.basename(fp)[:-4]                # depuis leur dossier de travail tant qu'il existe
        if not os.path.isdir(os.path.join(INPUTS, stem)):
            try:
                save_inputs(P("jobs", stem.rsplit("_", 1)[0]), fp)
            except OSError:
                pass
    for old in sorted(glob.glob(P("jobs", "*")))[:-20]:   # ne garde que les 20 derniers dossiers de travail
        shutil.rmtree(old, ignore_errors=True)
    threading.Thread(target=worker, daemon=True).start()
    if a.lan:
        S.access_code = load_access_code()
        S.access_token = access_token(S.access_code)
        name, ip = lan_address()
        ts = tailscale_hosts()
        S.lan_urls = [f"http://{h}:{a.port}/" for h in dict.fromkeys(x for x in (name, ip, *ts) if x)]
        S.lan_hosts = {urlsplit(u).netloc.lower() for u in S.lan_urls}
        dns = next((h for h in ts if h.endswith(".ts.net")), None)
        if dns:
            S.lan_hosts.add(dns)                    # nom HTTPS de « tailscale serve », admis même s'il est activé plus tard
            https = tailscale_serve_url(dns, a.port)
            if https:
                S.lan_urls.insert(0, https)         # seule adresse où le téléphone peut installer l'application
        if sys.platform == "darwin":
            # empêche la veille du Mac tant que ce processus tourne (l'écran peut s'éteindre)
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    httpd = Server(("0.0.0.0" if a.lan else "127.0.0.1", a.port), H)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"[launch] backend {S.backend}, modèle {S.model} — interface : {url}  (Ctrl+C pour arrêter)", flush=True)
    if a.lan:
        print(f"[launch] depuis le Wi-Fi : {' ou '.join(S.lan_urls)} — code d'accès dans tools/access_code.txt", flush=True)
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cur = S.jobs.get(S.current) if S.current else None
        if cur and cur.get("proc") and cur["proc"].poll() is None:
            cur["proc"].kill()
        print("[launch] arrêté.", flush=True)


if __name__ == "__main__":
    main()
