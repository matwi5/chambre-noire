r"""Lanceur unique : interface web locale + moteur stable-diffusion.cpp (sd-cli lancé à chaque génération).

  Windows : venv\Scripts\python.exe tools\launch.py [--port 7860] [--backend vulkan|cuda|cpu] [--model q4|q8] [--no-browser]
  macOS   : venv/bin/python tools/launch.py [--port 7860] [--model q4|q8] [--no-browser]
  Entrée dans l'interface déjà lancée, sans taper le code : venv/bin/python tools/launch.py --enter [--port 7860]

- L'interface écoute sur 127.0.0.1:<port> et sert tools/ui/index.html. Tout appareil, le Mac lui-même compris, saisit
  une fois le code d'accès de tools/access_code.txt, créé au premier lancement, avec ou sans --lan ; sur l'ordinateur,
  le lancement (hors --no-browser) et --enter ouvrent le navigateur par une entrée à usage unique (tools/entry.html,
  qui redirige vers GET /entrer?jeton=… : jeton de tools/entry_token, une minute, une fois). Avec --lan, elle
  écoute aussi sur le Wi-Fi (téléphone, tablette) ; sur macOS, le Mac ne se met pas en veille tant que le lanceur
  tourne.
- Chaque génération lance sd-cli (rechargement quasi instantané grâce à --mmap et au cache disque),
  lit sa progression (étape k/N, secondes par étape), expose des aperçus intermédiaires optionnels et écrit le PNG
  dans son dossier de travail jobs/<id>/ ; fini, il passe dans la pile (outputs/.pile/), à trier : Garder le fait
  passer dans les tirages (outputs/), Jeter l'efface avec tout ce qui s'y rattache.
- Espace privé ({"private": true} dans /api/generate, session de l'espace exigée) : pendant le calcul, fichiers de
  travail dans jobs/private_<id>/, supprimé dès la fin du job (ni journal, ni calibration ; dans logs/, rien que la
  ligne commune « [job] génération terminée »), puis l'image, sa
  miniature, ses entrées et ses réglages sont chiffrés avec la clé publique de l'espace dans
  private/items/<id au hasard>/ ; voir DECISIONS.md. Une demande {"incognito": true} (mode retiré) est refusée
  (400).
- Lots : {"count": 2 à 4} dans /api/generate (tous les modes, jamais avec une campagne) lance autant de générations
  de la même demande, à la suite dans la file, chacune avec sa graine ; {"campaign": [{"image", "width", "height"}, …]}
  (mode Éditer, 10 photos au plus) lance une édition par photo, avec cette seule photo en référence ; le lot porte
  "campaign" (vrai ou faux). Les générations d'un lot sont suivies, annulées (POST /api/lot/<id>/cancel), passées en
  tête (POST /api/lot/<id>/first) et notifiées ensemble.
- API : POST /api/generate, GET /api/job/<id>, GET /api/job/<id>/preview, POST /api/job/<id>/cancel, POST /api/lot/<id>/cancel,
        POST /api/job/<id>/first et POST /api/lot/<id>/first (« Passer en tête »),
        POST /api/job/<id>/forget (génération privée),
        espace privé : POST /api/private/create|unlock|lock|code|reset|delete|keep|discard,
        GET /api/private/history|pile,
        GET /api/private/image|thumb?id=<id>, GET /api/private/input?id=<id>&file=<init.png|ref_N.png>,
        prompts enregistrés de l'espace privé (private/prompts, chiffré) : GET /api/private/prompts,
        POST /api/private/prompts, POST /api/private/prompts/delete, POST /api/private/prompts/used,
        GET /api/result?name=<png>[&download=1], GET /api/status,
        tirages et pile : GET /api/history, GET /api/pile, GET /api/thumb?name=<png>, POST /api/keep {"name": <png>},
        POST /api/discard {"name": <png>}, POST /api/delete {"name": <png>},
        images d'entrée d'une image : GET /api/input?name=<png>&file=<init.png|ref_N.png>[&thumb=1][&download=1],
        notifications de fin de génération : GET /api/push/key, POST /api/push/subscribe {"subscription": …},
        POST /api/push/unsubscribe {"endpoint": …},
        prompts enregistrés (tools/saved_prompts.json, communs à tous les appareils) et prompts types
        (tools/prompt_types.json, lecture seule) : GET /api/prompts,
        POST /api/prompts (création, ou modification avec "id"), POST /api/prompts/delete, POST /api/prompts/used.
- Notifications (Web Push, bibliothèque pywebpush) : à la fin de chaque génération, le Mac envoie une notification à
  chaque appareil abonné, même si l'application y est fermée. Clé d'envoi propre à la machine dans
  tools/push_vapid.pem, appareils abonnés dans tools/push_subscriptions.json (non versionnés). Jamais le prompt.
Aucun droit administrateur, aucune modification système : tout reste dans ce dossier.
"""
import argparse, base64, datetime, errno, glob, hashlib, hmac, io, json, math, os, re, secrets, shutil, socket
import pathlib, subprocess, sys, threading, time, uuid, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit
try:
    import fcntl                                # F_FULLFSYNC de macOS (sync_fd) ; absent sous Windows
except ImportError:
    fcntl = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estimate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
CONFIG = P("tools", "config.json")
CONFIG_LOCAL = P("tools", "config.local.json")   # réglages propres à la machine, non suivis, lus par-dessus CONFIG
DIFFUSION = {   # versions du modèle de diffusion installables par setup.py (voir SETUP_FLAGS)
    "q4": P("models", "diffusion_models", "qwen-image-2.1-Q4_K_M.gguf"),
    "q8": P("models", "diffusion_models", "qwen-image-2.1-Q8_0.gguf"),
    "uc-q4": P("models", "diffusion_models", "qwen-image-2.1-UC-Q4_K_M.gguf"),   # variante communautaire, en option
    "uc-q8": P("models", "diffusion_models", "qwen-image-2.1-UC-Q8_0.gguf"),
}
SETUP_FLAGS = {"q4": "", "q8": "--q8", "uc-q4": "--uc", "uc-q8": "--uc --q8"}   # options de setup.py par version
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
MAX_VARIANTS = 4                          # images d'un lot de variantes (tous les modes, hors campagne)
MAX_CAMPAIGN = 10                         # photos d'une campagne (mode Éditer), comme les références d'une édition
PRIVATE_JOB_TTL = 24 * 3600               # génération privée finie, jamais oubliée par sa page : oubliée après ce délai
# ligne de fin de toute génération réussie, normale ou privée, sans chemin ni durée : une seule source, pour que rien
# dans logs/ ne distingue une génération privée (décision du 23/10/2026)
DONE_LINE = "[job] génération terminée"
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
    """Ajoute la mesure de la génération aux données de calibration (voir tools/estimate.py). Seules les générations de
    tools/calibrate.py en parlent : dans logs/, une ligne de calibration ne suivrait que les générations normales et les
    distinguerait des privées (décision du 23/10/2026)."""
    talk = job.get("calibration")
    try:
        sample = estimate.make_sample(job, S.engine)
        if not sample:
            return
        S.store.add(S.backend, S.model, sample)
    except Exception as e:
        if talk:
            print(f"[calibration] ignorée : {e}", flush=True)
        return
    if not talk:
        return
    c = S.store.coefficients(S.backend, S.model, S.engine)
    print(f"[calibration] {S.backend}/{S.model} : étape {sample['step']:.2f} s ({sample['w']}×{sample['h']}"
          f"{', ' + str(len(job.get('ref_px') or [])) + ' réf.' if job.get('ref_px') else ''}), "
          f"encodage {sample['enc']:.0f} s, décodage {sample['vae']:.0f} s — {c['samples']} mesure{'s' if c['samples'] > 1 else ''}", flush=True)


def load_config():
    cfg = {"backend": "vulkan", "ui_port": 7860, "cfg_scale": 1.0, "extra_args": []}
    for path in (CONFIG, CONFIG_LOCAL):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
    return cfg


VERSION_TTL = 30                                     # secondes entre deux lectures de la version du code servi
_version = {"root": None, "at": 0.0, "value": None, "git": True}


def code_version():
    """Version du code servi par ce dossier : {"server", "commit", "date", "branch"}. server : empreinte de
    tools/launch.py et tools/estimate.py, seul code que le serveur charge à son lancement (il n'est à relancer que si
    elle a changé depuis) ; les autres : dernier commit (git), None hors git. Relue au plus toutes les VERSION_TTL
    secondes : index.html est relu à chaque requête, un git pull change donc l'interface servie sans relancer le
    serveur. git n'est appelé que si le dossier a un .git (fichier dans un worktree), et plus jamais après un échec :
    sur un Mac sans outils de développement, /usr/bin/git ouvre une fenêtre d'installation ; un délai dépassé (disque
    occupé par une génération) est retenté."""
    if _version["root"] == ROOT and time.time() - _version["at"] < VERSION_TTL:
        return _version["value"]
    if _version["root"] != ROOT:
        _version["git"] = True
    value = {"server": None, "commit": None, "date": None, "branch": None}
    try:
        digest = hashlib.sha1()
        for name in ("launch.py", "estimate.py"):
            with open(P("tools", name), "rb") as f:
                digest.update(f.read())
        value["server"] = digest.hexdigest()[:12]
    except OSError:
        pass
    if _version["git"] and os.path.exists(os.path.join(ROOT, ".git")):
        try:
            out = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%h%n%cs%n%D"], capture_output=True,
                                 text=True, timeout=5, check=True).stdout.splitlines()
            refs = (out[2] if len(out) > 2 else "").split(", ")
            heads = [r[len("HEAD -> "):] for r in refs if r.startswith("HEAD -> ")]
            value.update(commit=out[0], date=out[1], branch=heads[0] if heads else None)
        except subprocess.TimeoutExpired:
            pass
        except (OSError, subprocess.SubprocessError, IndexError):
            _version["git"] = False
    _version.update(root=ROOT, at=time.time(), value=value)
    return value


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
# entrée depuis l'ordinateur sans taper le code (launch.py --enter, GET /entrer) : jeton à usage unique, valable
# ENTRY_TTL s, et page de redirection qui le porte ; tous deux lisibles par le seul compte, jamais suivis par git
ENTRY_TOKEN = P("tools", "entry_token")
ENTRY_PAGE = P("tools", "entry.html")
ENTRY_TTL = 60
# un jeton ne sert qu'une fois, même à deux requêtes simultanées, et ne s'écrit pas pendant sa lecture : dans un même
# processus seulement. launch.py --enter en est un autre : chacun de ses deux fichiers est remplacé d'un coup, mais pas
# la paire ; deux --enter rapprochés gardent le dernier jeton, et l'onglet resté sur l'ancien, s'il a déjà le cookie,
# est renvoyé vers / (_enter), sinon il reçoit la page du code
ENTRY_LOCK = threading.Lock()
ENTRY_USED = set()                              # empreintes des jetons servis : refusés même si leur fichier reste
LOCAL_CLIENTS = ("127.0.0.1", "::1")
# fichiers de tools/ui servis sans code d'accès pour l'installation sur le téléphone (rien de personnel)
PUBLIC_FILES = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
    "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
    # police pixel du nom et des titres (Pixelify Sans, licence OFL : tools/ui/OFL.txt), aussi pour la page du code
    "/PixelifySans.woff2": ("PixelifySans.woff2", "font/woff2"),
}
LOGIN_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Chambre noire</title>
<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<meta name="theme-color" content="#0d0a08">
<style>
:root{color-scheme:dark;--void:#0d0a08;--surf:#17120f;--field:#100c0a;--line:rgba(241,230,210,.13);--ink:#f1e6d2;
--ink2:rgba(241,230,210,.68);--accent:#ffa53a;--on-accent:#1c1006;--halo:rgba(190,28,18,.22);--err:#ff4f45;--r-m:6px}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;display:grid;place-items:center;padding:16px;background:var(--void);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
background:radial-gradient(90% 55% at 50% -8%,var(--halo),transparent 72%)}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.32;background-size:180px;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E\
%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E\
%3CfeColorMatrix values='0 0 0 0 .95 0 0 0 0 .9 0 0 0 0 .82 0 0 0 .5 0'/%3E%3C/filter%3E\
%3Crect width='100%25' height='100%25' filter='url(%23g)'/%3E%3C/svg%3E")}
form{width:100%;max-width:360px;padding:28px 22px 22px;border-radius:var(--r-m);text-align:center;
border:1px solid var(--line);background:var(--surf);box-shadow:0 18px 40px -22px rgba(0,0,0,.9)}
.logo{display:block;width:52px;height:52px;margin:0 auto 14px;border-radius:23%;box-shadow:0 0 0 1px var(--line)}
@font-face{font-family:"Pixelify Sans";src:url(/PixelifySans.woff2) format("woff2");font-weight:400 700;
font-display:swap}
h1{font:500 24px/1.3 "Pixelify Sans",system-ui,sans-serif;margin:0 0 6px}
p{color:var(--ink2);margin:0 0 20px;font-size:14.5px}
code{font:13.5px ui-monospace,Menlo,monospace;color:var(--ink)}
input{width:100%;font:inherit;font-size:24px;font-weight:650;letter-spacing:.16em;text-align:center;padding:14px;
border-radius:var(--r-m);border:1px solid var(--line);background:var(--field);color:var(--ink);outline:none}
input:focus{border-color:var(--accent)}
input::placeholder{color:var(--ink2);opacity:.5}
button{width:100%;margin-top:12px;font:inherit;font-size:17px;font-weight:700;padding:15px;border:0;
border-radius:var(--r-m);color:var(--on-accent);cursor:pointer;background:var(--accent)}
button:disabled{opacity:.6}
#err{color:var(--err);font-size:14px;min-height:21px;margin-top:10px}
#err:not(:empty)::before{content:"";display:inline-block;width:.95em;height:.95em;margin-right:.4em;
vertical-align:-.12em;background:currentColor;
--ico-err:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9' \
shape-rendering='crispEdges'%3E%3Cpath fill-rule='evenodd' \
d='M1 0h7v1h1v7h-1v1h-7v-1h-1v-7h1zM4 2h1v3h-1zM4 6h1v1h-1z'/%3E\
%3C/svg%3E");-webkit-mask:var(--ico-err) center/contain no-repeat;mask:var(--ico-err) center/contain no-repeat}
.shake{animation:shake .4s}
@keyframes shake{20%,60%{transform:translateX(-8px)}40%,80%{transform:translateX(8px)}}
@media (prefers-reduced-motion:reduce){.shake{animation:none}}
</style></head><body><form id="f"><img class="logo" src="/logo.svg" alt=""><h1>Chambre noire</h1>
<p>Saisissez le code d'accès affiché sur le Mac : touchez la lampe d'état, en haut à droite de l'interface, puis
« Ouvrir depuis le téléphone ». Il n'est demandé qu'une fois sur cet appareil.</p><!--mac-->
<input id="c" aria-label="Code d'accès" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false" placeholder="xxxx-xxxx" autofocus>
<button id="b">Entrer</button><div id="err" role="alert"></div></form>
<script>
const f=document.getElementById('f'), b=document.getElementById('b'), err=document.getElementById('err');
f.onsubmit=async e=>{e.preventDefault(); b.disabled=true; err.textContent='';
 const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.getElementById('c').value})});
 if(r.ok) return location.replace('/');
 b.disabled=false; err.textContent='Code incorrect.'; f.classList.remove('shake'); void f.offsetWidth; f.classList.add('shake');};
</script></body></html>"""
# ajouté à la page du code pour une requête de l'ordinateur lui-même (_local), à la place de <!--mac--> : pas sur le
# téléphone ; « ordinateur » et non « Mac » : la même page sert sous Windows
LOGIN_MAC = ("<p>Sur cet ordinateur : ouvrez Chambre noire par son raccourci, ou saisissez le code de "
             "<code>tools/access_code.txt</code>.</p>")


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


PROMPTS_FILE = P("tools", "saved_prompts.json")   # prompts enregistrés (non versionné), partagés par tous les appareils
PROMPTS_LOCK = threading.Lock()
PROMPT_USAGES = ("t2i", "edit", "mask")            # onglet où le prompt a été enregistré
MAX_PROMPT_TITLE, MAX_PROMPT_TEXT, MAX_SAVED_PROMPTS = 80, 4000, 500
# prompts types livrés avec l'application (versionné, liste validée par le porteur) : lus, jamais écrits par le serveur
PROMPT_TYPES_FILE = P("tools", "prompt_types.json")


def prompt_types():
    """Prompts types [{id, title, text, usage}], relus à chaque demande ; liste vide si le fichier manque ou est illisible."""
    try:
        with open(PROMPT_TYPES_FILE, encoding="utf-8") as f:
            types = json.load(f)
        if not (isinstance(types, list) and all(isinstance(p, dict) for p in types)):
            raise ValueError("liste de prompts attendue")
        return types
    except (OSError, ValueError) as e:
        print(f"[prompts] prompts types illisibles : {e}", flush=True)
        return []


def prompt_list(prompts):
    """La liste de prompts lue d'un fichier, si elle a la forme attendue ; sinon ValueError (fichier modifié à la
    main)."""
    if not (isinstance(prompts, list) and all(isinstance(p, dict) and isinstance(p.get("id"), str)
                                              and isinstance(p.get("used"), (int, float)) for p in prompts)):
        raise ValueError("liste de prompts attendue")
    return prompts


def saved_prompts(update=None):
    """Prompts enregistrés : [{id, title, text, usage, used}], used = dernière utilisation (secondes). update(liste)
    renvoie la liste modifiée, ou None pour ne rien écrire ; l'écriture passe par un fichier temporaire renommé
    ensuite, pour que le fichier ne soit jamais à moitié écrit. Un fichier illisible lève ValueError sans être écrasé."""
    with PROMPTS_LOCK:
        try:
            with open(PROMPTS_FILE, encoding="utf-8") as f:
                prompts = prompt_list(json.load(f))
        except FileNotFoundError:
            prompts = []
        changed = update(prompts) if update else None
        if changed is None:
            return prompts
        tmp = PROMPTS_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(changed, f, ensure_ascii=False)
            os.chmod(tmp, 0o600)                   # textes de l'utilisateur : lisibles par lui seul, comme les abonnements
            os.replace(tmp, PROMPTS_FILE)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        return changed


def prompt_error(action, body):
    """Motif du refus (400) d'une demande sur un prompt enregistré, ou None. « delete » et « used » : un id ; « save »
    sans id : création, avec son usage ; avec id : modification du titre et du texte (l'usage reste celui de
    l'enregistrement)."""
    if action != "save":
        return None if isinstance(body.get("id"), str) else "id : identifiant attendu"
    for key, label, most in (("title", "titre", MAX_PROMPT_TITLE), ("text", "texte", MAX_PROMPT_TEXT)):
        v = body.get(key)
        if not isinstance(v, str) or not v.strip():
            return f"{label} : texte non vide attendu"
        if len(v.strip()) > most:
            return f"{label} : {most} caractères au plus"
    if body.get("id") is None and body.get("usage") not in PROMPT_USAGES:
        return "usage : t2i, edit ou mask attendu"
    if body.get("id") is not None and not isinstance(body["id"], str):
        return "id : identifiant attendu"
    return None


def change_prompt(action, body, store=saved_prompts):
    """Crée (« save » sans id), modifie (« save » avec id), supprime (« delete ») ou marque comme utilisé (« used ») un
    prompt enregistré ; renvoie (code HTTP, réponse). Seuls le titre et le texte sont gardés, jamais les réglages.
    store : la liste à modifier, saved_prompts (espace public) ou celle de l'espace privé (private_prompts)."""
    result = (404, {"error": "prompt inconnu"})

    def stamp(prompts):
        # strictement après toutes les autres utilisations : deux gestes dans le même tic d'horloge (grossier sous
        # Windows) ne laissent pas d'égalité, et le dernier passe bien en tête
        return max(time.time(), max((x["used"] for x in prompts), default=0) + 0.001)

    def change(prompts):
        nonlocal result
        if action == "save" and body.get("id") is None:
            if len(prompts) >= MAX_SAVED_PROMPTS:
                result = (400, {"error": f"{MAX_SAVED_PROMPTS} prompts enregistrés au plus"})
                return None
            p = {"id": uuid.uuid4().hex[:12], "title": body["title"].strip(), "text": body["text"].strip(),
                 "usage": body["usage"], "used": stamp(prompts)}
            result = (200, p)
            return prompts + [p]
        p = next((p for p in prompts if p["id"] == body.get("id")), None)
        if not p:
            return None
        if action == "delete":
            result = (200, {"ok": True})
            return [x for x in prompts if x is not p]
        if action == "used":
            p["used"] = stamp(prompts)
        else:
            p.update(title=body["title"].strip(), text=body["text"].strip())
        result = (200, p)
        return prompts
    store(change)
    return result


try:                                           # espace privé ; sans cryptography, il est indisponible
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False
PRIVATE = P("private")                         # espace privé : space.json (clés), puis les images chiffrées
PRIVATE_COOKIE = "qwen_private"                # session de l'espace privé, propre à chaque appareil
PRIVATE_IDLE = 15 * 60                         # session fermée après 15 min sans requête privée
PRIVATE_LOCK = threading.RLock()               # dérivations du code privé, écritures des clés et des images : une à la fois
REKEY = ".rekey"                               # dossier de travail d'un changement de code, dans private/
META_TMP = "meta.tmp"                          # fiche réécrite par Garder, dans private/, avant de remplacer l'ancienne
MIN_PRIVATE_CODE, MAX_PRIVATE_CODE = 8, 256
SCRYPT_N = 2 ** 18                             # 256 Mio et ≈ 0,3 s par essai sur le Mac ; gardé dans space.json
KEY_AAD = b"qwen-image-local private key v1"   # données associées du chiffrement de la clé privée
FILE_MAGIC = b"QPV1"                           # en-tête d'un fichier chiffré de l'espace privé (version 1)
FILE_INFO = b"qwen-image-local private file v1"   # contexte HKDF de la clé d'un fichier
ITEM_RE = re.compile(r"[0-9a-f]{32}")          # nom d'une image privée : 128 bits tirés au hasard
PRIVATE_HTTPS_ONLY = ("espace privé : ouvrez l'application par son adresse HTTPS (Tailscale) ou sur le Mac ; "
                      "en http:// sur le Wi-Fi, le code et les images passeraient en clair")


def b64e(raw):
    return base64.b64encode(raw).decode()


def read_space():
    """Clés de l'espace privé (private/space.json), ou None s'il n'existe pas : {v, public, kdf, key}, voir
    DECISIONS.md (« Espace privé : format des clés, des fichiers et sessions »)."""
    try:
        with open(os.path.join(PRIVATE, "space.json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def code_key(code, kdf):
    """Clé de 32 octets tirée du code privé, tel que saisi (UTF-8), par scrypt avec les paramètres de space.json."""
    return Scrypt(salt=base64.b64decode(kdf["salt"]), length=32, n=kdf["n"], r=kdf["r"], p=kdf["p"]).derive(code.encode("utf-8"))


def write_space(public, private_key, code, fp=None):
    """Écrit space.json (ou fp) : clé publique en clair, clé privée chiffrée en AES-256-GCM par la clé du code (sel
    neuf à chaque écriture). Fichier temporaire puis renommage : jamais à moitié écrit."""
    kdf = {"alg": "scrypt", "n": SCRYPT_N, "r": 8, "p": 1, "salt": b64e(os.urandom(16))}
    nonce = os.urandom(12)
    sealed = AESGCM(code_key(code, kdf)).encrypt(nonce, private_key.private_bytes_raw(), KEY_AAD)
    fp = fp or os.path.join(PRIVATE, "space.json")
    private_dir(os.path.dirname(fp), exist_ok=True)
    write_synced(fp + ".tmp", json.dumps({"v": 1, "public": public, "kdf": kdf, "key": b64e(nonce + sealed)}).encode())
    os.replace(fp + ".tmp", fp)
    sync_dir(os.path.dirname(fp))


def sync_fd(fd, full=True):
    """Attend que le fichier ou dossier ouvert soit sur le disque : F_FULLFSYNC sur macOS (fsync y laisse les données
    dans le cache du disque), fsync ailleurs. full=False : fsync seul, quand un F_FULLFSYNC suit avant que l'écriture
    compte (il vide tout le cache du disque, y compris ce que les fsync précédents y ont envoyé)."""
    if full and hasattr(fcntl, "F_FULLFSYNC"):
        try:
            return fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        except OSError:                         # système de fichiers qui ne le connaît pas : fsync
            pass
    os.fsync(fd)


def open_private(fp, append=False):
    """Ouvre en écriture binaire (ou en ajout : append) un fichier lisible par son seul propriétaire (0o600) : fichiers
    de private/, journal des images ; jamais lisible par un autre compte du Mac, même le temps de l'écrire ; un fichier
    qui existait reprend ces droits."""
    flags = os.O_APPEND if append else os.O_TRUNC
    fd = os.open(fp, os.O_WRONLY | os.O_CREAT | flags | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.chmod(fp, 0o600)
        return os.fdopen(fd, "ab" if append else "wb")
    except BaseException:
        os.close(fd)
        raise


def private_dir(d, exist_ok=False):
    """Crée le dossier d de private/, et ceux qui lui manquent depuis private/ compris, chacun en 0o700 dès sa
    création (os.makedirs ne donne un mode qu'au dernier) ; un dossier qui existait reprend ces droits. Comme
    os.makedirs, échoue si d existe déjà, sauf exist_ok."""
    rel = os.path.relpath(d, PRIVATE)
    parts = [] if rel == os.curdir else rel.split(os.sep)
    path = PRIVATE
    for i, part in enumerate([None] + parts):
        path = os.path.join(path, part) if part else path
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            if i == len(parts) and not exist_ok:
                raise
        os.chmod(path, 0o700)


def write_synced(fp, data, full=True):
    """Écrit un fichier de private/ ou le journal réécrit (droits 0o600, open_private) et attend qu'il soit sur le
    disque : une coupure de courant ne le laisse ni vide ni tronqué derrière un renommage qui, lui, aurait été écrit."""
    with open_private(fp) as f:
        f.write(data)
        f.flush()
        sync_fd(f.fileno(), full)


def sync_dir(d, full=True):
    """Met sur le disque les créations et renommages d'un dossier (sans effet là où un dossier ne s'ouvre pas : Windows)."""
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        sync_fd(fd, full)
    except OSError:
        pass
    finally:
        os.close(fd)


def open_space(space, code):
    """Clé privée de l'espace (X25519PrivateKey) si le code est le bon, sinon None."""
    if not isinstance(code, str):
        return None
    blob = base64.b64decode(space["key"])
    try:
        raw = AESGCM(code_key(code, space["kdf"])).decrypt(blob[:12], blob[12:], KEY_AAD)
    except InvalidTag:
        return None
    return X25519PrivateKey.from_private_bytes(raw)


def file_key(shared, eph_pub, pub):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_pub + pub, info=FILE_INFO).derive(shared)


def seal(data, public, label):
    """Chiffre un fichier de l'espace privé avec sa clé publique (base64), sans la clé privée : clé éphémère X25519,
    accord, HKDF-SHA256, AES-256-GCM. Résultat : FILE_MAGIC + clé éphémère (32) + nonce (12) + chiffré et étiquette.
    label (« <image>/<rôle> ») entre dans les données associées : un fichier ne peut pas passer pour un autre."""
    pub = base64.b64decode(public)
    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes_raw()
    nonce = os.urandom(12)
    head = FILE_MAGIC + eph_pub + nonce
    key = file_key(eph.exchange(X25519PublicKey.from_public_bytes(pub)), eph_pub, pub)
    return head + AESGCM(key).encrypt(nonce, data, head + label.encode())


def unseal(blob, private_key, label):
    """Déchiffre un fichier scellé par seal() ; InvalidTag (ou ValueError) s'il a été altéré ou vient d'ailleurs."""
    if blob[:4] != FILE_MAGIC or len(blob) < 48:
        raise ValueError("fichier privé illisible")
    eph_pub, nonce = blob[4:36], blob[36:48]
    pub = private_key.public_key().public_bytes_raw()
    key = file_key(private_key.exchange(X25519PublicKey.from_public_bytes(eph_pub)), eph_pub, pub)
    return AESGCM(key).decrypt(nonce, blob[48:], blob[:48] + label.encode())


def store_private(public, meta, image, inputs):
    """Range une image dans l'espace privé : private/items/<128 bits au hasard>/ avec meta (réglages, en JSON), image,
    thumb (miniature fabriquée en mémoire) et input_<k> (images d'entrée), chacun scellé à part. Écrit dans un dossier
    caché puis renommé : ni la pile ni les tirages privés ne voient une image à moitié rangée. Renvoie son
    identifiant.
    public : la clé publique notée au lancement de la génération ; si le code a changé
    depuis, l'image est scellée avec la clé qui l'a remplacée ; si l'espace a été supprimé ou recréé entre-temps, elle
    est abandonnée (RuntimeError) plutôt que rangée avec une clé disparue. Jamais pendant un changement de code."""
    with PRIVATE_LOCK:
        while public in S.rekeyed:
            public = S.rekeyed[public]
        if (read_space() or {}).get("public") != public:
            raise RuntimeError("espace privé supprimé pendant la génération")
        item = secrets.token_hex(16)
        items = os.path.join(PRIVATE, "items")
        tmp = os.path.join(items, "." + item)
        private_dir(tmp)
        try:
            files = {"meta": json.dumps({**meta, "inputs": [n for n, _ in inputs]}, ensure_ascii=False).encode(),
                     "image": image, "thumb": thumb_jpeg(io.BytesIO(image))}
            files.update((f"input_{k}", raw) for k, (_, raw) in enumerate(inputs))
            for role, data in files.items():
                with open_private(os.path.join(tmp, role)) as f:
                    f.write(seal(data, public, f"{item}/{role}"))
            os.rename(tmp, os.path.join(items, item))
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return item


def rekey_space(old_key, code):
    """Changement de code : nouvelle paire de clés, toutes les images et les prompts privés rechiffrés, pour qu'une
    ancienne copie de space.json ne lise plus rien avec l'ancien code. Ordre d'écriture sûr (DECISIONS.md) : tout est
    d'abord écrit à part, dans private/.rekey/ (la nouvelle clé publique, chaque fichier rechiffré sous son nom, les
    nouvelles clés scellées par le nouveau code) ; la bascule est le remplacement de space.json, atomique ;
    finish_rekey() range ensuite les fichiers rechiffrés à la place des anciens. Une panne avant la bascule laisse
    l'ancien espace intact. Sous PRIVATE_LOCK, après finish_rekey() (aucun reste d'un changement interrompu) ; renvoie
    la nouvelle clé publique."""
    staging = os.path.join(PRIVATE, REKEY)
    key = X25519PrivateKey.generate()
    public = b64e(key.public_key().public_bytes_raw())

    def reseal(src, dst, label):
        """Copie src rechiffré avec la nouvelle clé ; un fichier déjà illisible avec l'ancienne est gardé tel quel, rien
        n'est perdu. fsync seul (voir plus bas)."""
        with open(src, "rb") as f:
            blob = f.read()
        try:
            blob = seal(unseal(blob, old_key, label), public, label)
        except (InvalidTag, ValueError):
            pass
        write_synced(dst, blob, full=False)
    try:
        # reste d'un enregistrement des prompts privés coupé par une panne : scellé avec l'ancienne clé, il partirait
        # lisible par l'ancien code
        # de même pour une fiche réécrite par Garder (sort_private)
        for leftover in ("prompts.tmp", META_TMP):
            try:
                os.remove(os.path.join(PRIVATE, leftover))
            except FileNotFoundError:
                pass
        private_dir(os.path.join(staging, "items"))
        # fichiers et dossiers copiés : fsync seul ; le F_FULLFSYNC de write_space, avant la bascule, les met tous sur
        # le disque d'un coup (un F_FULLFSYNC par fichier viderait le cache du disque autant de fois)
        write_synced(os.path.join(staging, "public"), public.encode(), full=False)   # marque de la bascule : space.json porte-t-il cette clé ?
        for d in glob.glob(os.path.join(PRIVATE, "items", "*")):
            item = os.path.basename(d)
            if not ITEM_RE.fullmatch(item):
                continue
            private_dir(os.path.join(staging, "items", item))
            for role in os.listdir(d):
                reseal(os.path.join(d, role), os.path.join(staging, "items", item, role), f"{item}/{role}")
            sync_dir(os.path.join(staging, "items", item), full=False)
        sync_dir(os.path.join(staging, "items"), full=False)
        if os.path.exists(os.path.join(PRIVATE, "prompts")):   # prompts enregistrés de l'espace
            reseal(os.path.join(PRIVATE, "prompts"), os.path.join(staging, "prompts"), "prompts")
        write_space(public, key, code, os.path.join(staging, "space.json"))   # copies sur le disque avant la bascule
        sync_dir(PRIVATE)                       # l'entrée de .rekey/ elle-même, avant la bascule qui la rend nécessaire
        # la bascule, dernière instruction du try : si elle échoue, rien n'a changé et les copies sont jetées ; si elle
        # réussit, plus rien ne doit les jeter (space.json porte déjà la nouvelle clé)
        os.replace(os.path.join(staging, "space.json"), os.path.join(PRIVATE, "space.json"))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    sync_dir(PRIVATE)
    return public


def finish_rekey():
    """Termine un changement de code interrompu après la bascule (les images rechiffrées remplacent les anciennes, une
    à une, puis les prompts privés), ou l'abandonne s'il s'est arrêté avant (l'ancien espace est intact : les copies
    sont jetées). Sans effet sans private/.rekey/. Appelé sous PRIVATE_LOCK, au démarrage et avant toute ouverture ou
    écriture de l'espace."""
    staging = os.path.join(PRIVATE, REKEY)
    if not os.path.isdir(staging):
        return
    try:
        with open(os.path.join(staging, "public"), encoding="utf-8") as f:
            public = f.read()
    except OSError:
        public = None
    if not public or public != (read_space() or {}).get("public"):
        shutil.rmtree(staging)
        return
    for d in glob.glob(os.path.join(staging, "items", "*")):
        dst = os.path.join(PRIVATE, "items", os.path.basename(d))
        if os.path.exists(dst):
            shutil.rmtree(dst)                  # l'ancienne version, illisible avec la nouvelle clé (la nouvelle est écrite)
        os.rename(d, dst)
    sync_dir(os.path.join(PRIVATE, "items"))
    if os.path.exists(os.path.join(staging, "prompts")):   # prompts rechiffrés : remplacent les anciens d'un coup
        os.replace(os.path.join(staging, "prompts"), os.path.join(PRIVATE, "prompts"))
        sync_dir(PRIVATE)
    shutil.rmtree(staging)


def read_private(private_key, item, role):
    """Fichier déchiffré d'une image privée, ou None si l'image ou le fichier n'existe pas."""
    if not ITEM_RE.fullmatch(str(item or "")):
        return None
    try:
        with open(os.path.join(PRIVATE, "items", item, role), "rb") as f:
            blob = f.read()
    except OSError:
        return None
    return unseal(blob, private_key, f"{item}/{role}")


def private_items(private_key, pile):
    """Images de l'espace privé, la plus récente d'abord : réglages déchiffrés et identifiant (une image illisible avec
    cette clé est ignorée) ; pile : celles de la pile (fiche marquée « pile », toujours chiffrée), sinon les tirages
    (les images d'avant la pile en sont). La marque ne part pas vers l'interface."""
    items = []
    for d in glob.glob(os.path.join(PRIVATE, "items", "*")):
        item = os.path.basename(d)
        try:
            meta = json.loads(read_private(private_key, item, "meta") or b"null")
        except (InvalidTag, ValueError):
            continue
        if isinstance(meta, dict) and bool(meta.pop("pile", False)) == pile:
            # time est à la seconde : deux images d'un lot finies la même seconde se départagent par leur dossier
            try:
                finished = os.stat(d).st_mtime_ns
            except FileNotFoundError:           # jetée ou supprimée pendant la lecture
                continue
            items.append(((meta.get("time") or 0, finished), {**meta, "id": item, "private": True}))
    return [it for _, it in sorted(items, key=lambda x: x[0], reverse=True)]


def space_public(private_key):
    """Clé publique de space.json, si private_key est encore la clé de l'espace ; sinon StaleKey (code changé ou
    espace supprimé pendant la requête). Sous PRIVATE_LOCK, après finish_rekey()."""
    public = (read_space() or {}).get("public")
    if public != b64e(private_key.public_key().public_bytes_raw()):
        raise StaleKey("espace privé verrouillé")
    return public


def replace_synced(tmp, fp, data, full=True):
    """Remplace fp par data d'un coup : écrit dans tmp, mis sur le disque (droits 600), puis os.replace ; tmp ne reste
    pas après un échec."""
    try:
        write_synced(tmp, data, full)
        os.replace(tmp, fp)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def remove_private_item(item):
    """Supprime le dossier d'une image privée (Jeter, /api/private/delete), renommé d'abord en dossier caché (purgé au
    démarrage) : un effacement coupé ne laisse pas une image sans fiche, que ni la pile ni les tirages ne montreraient
    plus. Sous PRIVATE_LOCK, après finish_rekey() : un changement de code interrompu en rangerait sinon la copie
    rechiffrée à sa place."""
    hidden = os.path.join(PRIVATE, "items", "." + item)
    os.rename(os.path.join(PRIVATE, "items", item), hidden)
    S.rev["private"] += 1
    shutil.rmtree(hidden)


def sort_private(action, private_key, item):
    """Garder (keep) ou Jeter (discard) une image de la pile privée avec la clé d'une session : (code, réponse). Sous
    PRIVATE_LOCK, après finish_rekey() ; 404 « déjà triée » si l'image n'est pas (ou plus) dans la pile : le premier
    geste arrivé l'emporte. Garder déchiffre la fiche (meta), en retire la marque « pile » et la rescelle avec la clé
    publique de space.json (fichier temporaire private/meta.tmp mis sur le disque, puis remplacement atomique) ; image,
    vignette et entrées restent telles quelles. Jeter supprime le dossier de l'image (remove_private_item).
    StaleKey si la clé n'est plus celle de l'espace ; une fiche illisible lève InvalidTag ou ValueError."""
    with PRIVATE_LOCK:
        finish_rekey()
        public = space_public(private_key)
        raw = read_private(private_key, item, "meta") if isinstance(item, str) else None
        meta = json.loads(raw) if raw else None
        if not (isinstance(meta, dict) and meta.get("pile")):
            return 404, {"error": "déjà triée"}
        if action == "discard":
            remove_private_item(item)
            return 200, {"ok": True}
        d = os.path.join(PRIVATE, "items", item)
        del meta["pile"]
        # fsync seul : le F_FULLFSYNC de sync_dir(d) met aussi le fichier temporaire sur le disque
        replace_synced(os.path.join(PRIVATE, META_TMP), os.path.join(d, "meta"),
                       seal(json.dumps(meta, ensure_ascii=False).encode(), public, f"{item}/meta"), full=False)
        sync_dir(d)
        S.rev["private"] += 1                   # après le changement : une page qui relit la pile le voit
        return 200, {"ok": True}


class StaleKey(Exception):
    """Clé privée d'une session qui n'est plus celle de l'espace : traitée comme un espace verrouillé (403)."""


def private_prompts(private_key, update=None):
    """Prompts enregistrés de l'espace privé, comme saved_prompts (même format, même update), lus et écrits avec la clé
    d'une session : private/prompts, scellé par seal() avec l'étiquette « prompts », absent tant qu'aucun prompt privé
    n'existe (DECISIONS.md). Sous PRIVATE_LOCK, après finish_rekey() ; écriture mise sur le disque dans un fichier
    temporaire, puis remplacement atomique, droits 600. Un fichier illisible lève ValueError (ou InvalidTag) sans être
    écrasé ; StaleKey si la clé n'est plus celle de l'espace (code changé ou espace supprimé pendant la requête)."""
    fp = os.path.join(PRIVATE, "prompts")
    with PRIVATE_LOCK:
        finish_rekey()
        public = space_public(private_key)
        try:
            with open(fp, "rb") as f:
                prompts = prompt_list(json.loads(unseal(f.read(), private_key, "prompts")))
        except FileNotFoundError:
            prompts = []
        changed = update(prompts) if update else None
        if changed is None:
            return prompts
        replace_synced(fp + ".tmp", fp, seal(json.dumps(changed, ensure_ascii=False).encode(), public, "prompts"))
        sync_dir(PRIVATE)
        return changed


def private_code_error(code):
    if not isinstance(code, str) or len(code) < MIN_PRIVATE_CODE:
        return f"code privé : {MIN_PRIVATE_CODE} caractères au moins"
    if len(code) > MAX_PRIVATE_CODE:
        return f"code privé : {MAX_PRIVATE_CODE} caractères au plus"
    return None


def duration_text(secs):
    return f"{int(secs // 60)} min {int(secs % 60):02d} s" if secs >= 60 else f"{int(secs)} s"


def notify_job(job):
    """Notification de fin d'une génération seule (celles d'un lot : notify_lot). Une génération privée notifie comme
    une génération normale : rien ne trahit l'espace privé (décision du porteur du 14/10/2026)."""
    if job.get("calibration"):
        return
    if job.get("status") == "done":
        dims = "×".join(str(d) for d in job.get("dims") or [])
        push_notify({"title": "Image prête",
                     "body": f"Générée en {duration_text(job.get('seconds') or 0)}" + (f" · {dims}" if dims else "")})
    else:
        push_notify({"title": "Échec de la génération", "body": "Ouvrez l'application pour voir le détail."})


def notify_lot(lot):
    """Une seule notification pour tout un lot, quand sa dernière génération se termine : images prêtes et en échec ;
    rien si tout le lot a été annulé. Compte d'après les statuts seuls (une génération privée a déjà oublié sa demande).
    Un lot privé notifie comme un lot normal."""
    jobs = lot["jobs"]
    done, failed = (sum(j.get("status") == s for j in jobs) for s in ("done", "failed"))
    if not done and not failed:
        return
    if done:
        s = "s" if done > 1 else ""
        title = f"{done} image{s} prête{s}" + (f", {failed} en échec" if failed else "")
        span = max(j.get("finished") or 0 for j in jobs) - min(j["started"] for j in jobs if j.get("started"))
        what = f"Campagne de {len(jobs)} photos terminée" if lot["campaign"] else f"Lot de {len(jobs)} images terminé"
        push_notify({"title": title, "body": f"{what} en {duration_text(span)}"})
    else:
        push_notify({"title": "Échec du lot", "body": "Ouvrez l'application pour voir le détail."})


def push_notify(payload):
    """Envoie une notification à tous les appareils abonnés, dans un thread pour ne pas retarder la file.
    Ni prompt ni nom de fichier : le message transite (chiffré) par le service de notification du navigateur."""
    subs = push_subscriptions()
    if not subs:
        return
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
INPUTS = P("outputs", ".inputs")      # images d'entrée d'un tirage ou d'une image de la pile : .inputs/<nom sans .png>/
INPUT_RE = re.compile(r"(init|ref_\d+)\.png")
# pile de l'espace public : images terminées à trier ; Garder les fait passer dans outputs/ (les tirages), Jeter les
# efface. Vignettes et images d'entrée sont rangées par nom d'image et ne bougent pas quand elle passe aux tirages.
PILE = P("outputs", ".pile")
JOB_ID_RE = re.compile(r"\d{8}_\d{6}_[0-9a-f]{6}")   # identifiant d'une génération normale (new_job)


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
            # copyfile, pas copy2 : la copie prend les droits du masque (restrict_new_files), pas ceux de la source
            shutil.copyfile(os.path.join(job_dir, n), os.path.join(dst, n))


def image_in(folder, name):
    """Chemin d'une image de folder à partir de son nom, ou None si le nom sort du dossier, n'est pas un PNG ou n'y
    est pas."""
    name = os.path.basename(str(name or ""))
    if not name or name.startswith(".") or not name.lower().endswith(".png"):
        return None
    fp = os.path.join(folder, name)
    return fp if os.path.isfile(fp) else None


def output_path(name):
    """Chemin d'un tirage (image de outputs/), ou None."""
    return image_in(P("outputs"), name)


def pile_path(name):
    """Chemin d'une image de la pile, ou None."""
    return image_in(PILE, name)


def image_path(name):
    """Chemin d'un tirage ou d'une image de la pile : ce que l'image, sa vignette et ses images d'entrée servent."""
    return output_path(name) or pile_path(name)


def on_image(name, use):
    """use(chemin) sur un tirage ou une image de la pile, ou None si elle n'existe pas (ou plus) : une image gardée
    entre la recherche et la lecture (passée de la pile aux tirages) est cherchée une seconde fois, plutôt qu'un 404
    pour une image qui existe."""
    for _ in range(2):
        fp = image_path(name)
        if not fp:
            return None
        try:
            return use(fp)
        except FileNotFoundError:
            pass
    return None


# journal des images et tri : l'arrivée d'une image dans la pile avec sa ligne (to_pile), Garder, Jeter et Supprimer
# (vérification, déplacement ou effacements, réécriture du journal), comme la lecture des tirages et de la pile, se
# font chacun d'un bloc sous ce verrou ; le premier geste arrivé l'emporte. RLock : ces blocs appellent des fonctions
# qui le prennent aussi.
JOURNAL_LOCK = threading.RLock()


def journal_line(line):
    """Ligne du journal (octets) : (nom de l'image, réglages), ou None pour une ligne illisible (pas du JSON en UTF-8,
    pas un objet). Lecture et réécriture du journal la jugent de la même façon."""
    try:
        m = json.loads(line)
    except ValueError:                          # UnicodeDecodeError compris
        return None
    return (os.path.basename(str(m.get("file") or "")), m) if isinstance(m, dict) else None


def journal_entries():
    """Lignes du journal des images (outputs/journal.jsonl) par nom d'image (la dernière si plusieurs)."""
    entries = {}
    with JOURNAL_LOCK:
        try:
            with open(P("outputs", "journal.jsonl"), "rb") as f:
                for line in f:
                    entry = journal_line(line)
                    if entry:
                        entries[entry[0]] = entry[1]
        except OSError:
            pass
    return entries


def append_journal(meta):
    """Ajoute la ligne d'une image au journal, sous JOURNAL_LOCK ; le journal (des prompts) n'est lisible que par son
    propriétaire (0o600), un journal d'avant reprend ces droits."""
    with JOURNAL_LOCK:
        with open_private(P("outputs", "journal.jsonl"), append=True) as f:
            f.write((json.dumps(meta, ensure_ascii=False) + "\n").encode("utf-8"))


def to_pile(job, meta):
    """Fin d'une génération normale réussie : son image passe du dossier de travail dans la pile, puis sa ligne du
    journal (meta) et ses images d'entrée, d'un bloc sous JOURNAL_LOCK : ni la lecture de la pile ni un tri ne voient
    l'image sans sa ligne. L'image d'abord : une panne ensuite laisse une image de la pile que Jeter efface en entier,
    jamais une ligne du journal (son prompt) sans image. Le passage dans la pile et le statut « done » se font sous
    S.turn, comme une annulation (cancel_job) : une génération annulée entre-temps n'arrive pas dans la pile, False
    (run_job la jette). jobs/ et outputs/ sont sous ROOT, sur le même disque : os.replace déplace sans copier (un
    outputs/ sur un autre disque ferait échouer la génération). Le PNG est mis sur le disque avant d'être déplacé :
    une coupure ne laisse pas dans la pile un fichier vide derrière un renommage écrit."""
    try:                                        # fsync seul : le F_FULLFSYNC de sync_dir(PILE) suit le déplacement
        with open(job["out"], "rb") as f:
            sync_fd(f.fileno(), full=False)
    except OSError:                             # Windows (fsync d'un fichier ouvert en lecture) : os.replace tranche
        pass
    with JOURNAL_LOCK:
        os.makedirs(PILE, exist_ok=True)
        dst = os.path.join(PILE, os.path.basename(job["out"]))
        os.chmod(job["out"], 0o600)             # lisible par le seul propriétaire dès la pile (os.replace le garde)
        with S.turn:
            if job.get("status") == "cancelled":
                return False
            os.replace(job["out"], dst)
            # réussie dès qu'elle est dans la pile : un échec du journal ou des entrées ne la retire pas (fail_job)
            job["out"], job["status"], job["phase"] = dst, "done", "terminé"
        sync_dir(PILE)
        S.rev["public"] += 1
        append_journal({**meta, "file": dst})
        try:
            save_inputs(job["dir"], dst)
        except OSError:
            print("[job] images d'entrée non conservées", flush=True)   # sans détail : chemin de l'image
    return True


def hidden_png(fp):
    """Nom caché d'un PNG pendant son effacement : un point devant, dans le même dossier ; images_in (glob « *.png »)
    et les routes (image_in) ne voient pas les noms en point."""
    return os.path.join(os.path.dirname(fp), "." + os.path.basename(fp))


def delete_output(fp):
    """Efface une image (tirage ou image de la pile) et tout ce qui s'y rattache (décisions du 23/10/2026). Le PNG est
    d'abord renommé en nom caché (hidden_png) : sous Windows, un fichier ouvert refuse ce renommage tout de suite, avant
    que rien ne soit effacé. Puis ses miniatures, ses images d'entrée, son dossier de travail jobs/<id>/ (identifiant
    tiré du nom, validé par JOB_ID_RE) et ses lignes du journal, et le PNG en dernier, seulement si tout le reste est
    parti : une pièce qui résiste (ou toute autre exception) lui rend son nom, et l'image reste là où elle était, qu'un
    second geste efface en entier, au lieu d'une ligne du journal (son prompt) que plus rien ne retirerait ; une panne
    entre-temps est rattrapée au démarrage (restore_hidden_images). Une pièce déjà absente est sautée (le démarrage ne
    garde que 20 dossiers de travail) ; une pièce qui résiste n'arrête pas les suivantes : la première erreur est levée
    à la fin. Sous JOURNAL_LOCK (sort_image)."""
    name, hidden = os.path.basename(fp), hidden_png(fp)
    os.replace(fp, hidden)
    try:
        jid = name[:-4].rsplit("_", 1)[0]
        steps = [lambda: delete_extras(name[:-4]), lambda: drop_from_journal(name)]
        if JOB_ID_RE.fullmatch(jid):
            steps.insert(1, lambda: remove_tree(P("jobs", jid)))
        error = None
        for step in steps:
            try:
                step()
            except OSError as e:
                error = error or e
        if not error:
            os.remove(hidden)
            return
    except BaseException:
        unhide(hidden, fp)
        raise
    unhide(hidden, fp)
    raise error


def unhide(hidden, fp):
    """Rend son nom au PNG d'un effacement qui n'a pas abouti ; s'il résiste, le démarrage le rattrapera
    (restore_hidden_images) : l'erreur que voit l'appelant reste celle d'origine."""
    try:
        os.replace(hidden, fp)
    except OSError:
        pass


def restore_hidden_images():
    """Démarrage : un PNG resté sous son nom caché (delete_output coupé par une panne) reprend son nom ; l'image revient
    dans la pile ou les tirages, et un nouveau geste l'efface en entier. Seuls les noms d'images du serveur
    (identifiant JOB_ID_RE) sont rendus, pas un fichier caché d'un autre outil (« ._X.png » des volumes exFAT ou SMB) ;
    si le nom d'origine est déjà pris, la copie cachée, en double, est supprimée. Un renommage qui échoue est retenté
    au démarrage suivant."""
    for folder in (P("outputs"), PILE):
        for fp in glob.glob(os.path.join(folder, ".*.png")):
            name = os.path.basename(fp)[1:]
            if not JOB_ID_RE.fullmatch(name[:-4].rsplit("_", 1)[0]):
                continue
            dst = os.path.join(folder, name)
            try:
                if os.path.exists(dst):
                    os.remove(fp)
                else:
                    os.replace(fp, dst)
            except OSError:
                pass


def drop_from_journal(name):
    """Retire du journal les lignes de l'image name, sous JOURNAL_LOCK : le journal réécrit dans un fichier temporaire
    mis sur le disque (droits 600), puis remplacé d'un coup, jamais à moitié réécrit. Les lignes illisibles sont
    recopiées telles quelles."""
    fp = P("outputs", "journal.jsonl")
    with JOURNAL_LOCK:
        try:
            with open(fp, "rb") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return
        kept = [line for line in lines if (journal_line(line) or ("",))[0] != name]
        if len(kept) == len(lines):
            return
        # fsync seul : le F_FULLFSYNC de sync_dir met aussi le fichier temporaire sur le disque
        replace_synced(fp + ".tmp", fp, b"".join(kept), full=False)
        sync_dir(P("outputs"))


# Garder et Jeter visent la pile, Supprimer les tirages : où chercher l'image, et la réponse quand elle n'y est pas
SORTS = {"keep": (pile_path, "déjà triée"), "discard": (pile_path, "déjà triée"),
         "delete": (output_path, "fichier inconnu")}


def sort_image(action, name):
    """Garder (keep : de la pile aux tirages, PNG seul déplacé, de façon atomique) ou Jeter (discard : effacement
    complet) une image de la pile, Supprimer (delete : effacement complet) un tirage ; (code, réponse). D'un bloc sous
    JOURNAL_LOCK : le premier geste arrivé l'emporte, le second ne trouve plus l'image (404)."""
    find, unknown = SORTS[action]
    with JOURNAL_LOCK:
        fp = find(name)
        if not fp:
            return 404, {"error": unknown}
        dst = P("outputs", os.path.basename(fp))
        if action == "keep" and os.path.lexists(dst):   # os.replace écraserait le tirage
            return 409, {"error": "un tirage du même nom existe déjà"}
        S.rev["public"] += 1
        try:
            if action == "keep":
                os.replace(fp, dst)
                sync_dir(P("outputs"))
            else:
                delete_output(fp)       # sans ligne au journal du serveur : une suppression privée n'en écrit pas
        except OSError:
            return 500, {"error": "image gardée dans la pile : déplacement impossible" if action == "keep"
                         else "effacement incomplet"}
    return 200, {"ok": True}


def delete_extras(stem):
    """Miniatures et images d'entrée d'un tirage ou d'une image de la pile déjà supprimés."""
    for th in [os.path.join(THUMBS, stem + ".jpg"), *glob.glob(os.path.join(THUMBS, glob.escape(stem) + "__*.jpg"))]:
        if os.path.exists(th):
            os.remove(th)
    remove_tree(os.path.join(INPUTS, stem))


def remove_tree(d):
    """Supprime un dossier ; déjà absent, rien ; un fichier qui résiste lève l'erreur (delete_output garde alors le
    PNG)."""
    try:
        shutil.rmtree(d)
    except FileNotFoundError:
        pass


def read_inputs(d):
    """Images d'entrée d'un dossier (init.png puis ref_N.png) avec leur contenu : [(nom, octets)]."""
    inputs = []
    for n in input_files(d):
        with open(os.path.join(d, n), "rb") as f:
            inputs.append((n, f.read()))
    return inputs


def images_in(folder):
    """Images d'un dossier (outputs/ ou la pile), la plus récente d'abord, avec les réglages notés dans
    outputs/journal.jsonl ; sous JOURNAL_LOCK : une image et sa ligne y arrivent ensemble (to_pile), un tri n'efface
    rien pendant la lecture."""
    items = []
    with JOURNAL_LOCK:
        meta = journal_entries()
        for fp in glob.glob(os.path.join(folder, "*.png")):
            name, st = os.path.basename(fp), os.stat(fp)
            m = meta.get(name, {})
            item = {"name": name, "time": int(st.st_mtime), "size": st.st_size, "mode": m.get("mode"),
                    "prompt": m.get("prompt"), "width": m.get("width"), "height": m.get("height"),
                    "steps": m.get("steps"), "seconds": m.get("seconds"), "model": m.get("model"),
                    "seed": m.get("seed"),
                    # identifiant, rang, taille et marqueur de campagne d'une image de lot ; None pour une image seule
                    "lot": m.get("lot"),
                    "inputs": input_files(os.path.join(INPUTS, name[:-4]))}
            items.append((st.st_mtime_ns, item))   # à la nanoseconde : deux images d'un lot finies la même seconde
    return [it for _, it in sorted(items, key=lambda x: x[0], reverse=True)]


def history():
    """Tirages (images de outputs/), le plus récent d'abord ; les images d'avant la pile en sont."""
    return images_in(P("outputs"))


def pile():
    """Pile de l'espace public, la dernière arrivée d'abord."""
    return images_in(PILE)


def thumb_jpeg(src):
    """Miniature JPEG de 320 px (côté le plus long) d'une image (chemin ou fichier en mémoire), en octets."""
    from PIL import Image
    buf = io.BytesIO()
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((320, 320))
        im.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def thumbnail(fp, th=None):
    """Miniature d'un tirage, d'une image de la pile ou d'une de leurs images d'entrée (fp), gardée dans
    outputs/.thumbs/ et refaite si l'image change. Mise en place sous JOURNAL_LOCK, et seulement si fp existe
    encore : une miniature finie après Jeter ou Supprimer ne reste pas ; FileNotFoundError alors."""
    th = th or os.path.join(THUMBS, os.path.basename(fp)[:-4] + ".jpg")
    if not os.path.exists(th) or os.path.getmtime(th) < os.path.getmtime(fp):
        os.makedirs(THUMBS, exist_ok=True)
        tmp = f"{th}.{threading.get_ident()}.tmp"   # écrite à côté puis renommée : jamais lue à moitié écrite
        try:
            with open(tmp, "wb") as f:
                f.write(thumb_jpeg(fp))
            with JOURNAL_LOCK:
                if not os.path.exists(fp):
                    raise FileNotFoundError(fp)
                os.replace(tmp, th)
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
    return th


def normalize_code(code):
    return re.sub(r"[^a-z0-9]", "", str(code).lower())


def access_token(code):
    """Valeur du cookie d'accès : empreinte du code (le code lui-même ne circule pas dans le cookie)."""
    return hashlib.sha256(("qwen-image-local:" + normalize_code(code)).encode()).hexdigest()


def read_access_code():
    """Code d'accès de tools/access_code.txt, remis en 0o600, ou None s'il manque ou compte moins de 6 signes ; ne crée
    rien (aussi lu par tests/run_tests.py). Un fichier illisible (droits, encodage, dossier) lève OSError ou
    ValueError (UnicodeDecodeError)."""
    try:
        with open(ACCESS_FILE, encoding="utf-8") as f:
            code = f.read().strip()
    except FileNotFoundError:
        return None
    try:
        os.chmod(ACCESS_FILE, 0o600)                 # créé autrement (à la main, copie) : fermé aux autres comptes
    except OSError:
        pass
    return code if len(normalize_code(code)) >= 6 else None


class AccessPending(Exception):
    """Fichier du code créé par un autre lancement, encore vide ou incomplet au bout de l'attente."""


def wait_access_code():
    """Code de tools/access_code.txt relu pendant 2 s au plus : un autre lancement peut l'avoir créé à l'instant
    (O_EXCL) sans l'avoir encore écrit ; None s'il reste absent ou trop court."""
    for _ in range(40):
        code = read_access_code()
        if code:
            return code
        time.sleep(0.05)
    return None


def load_access_code():
    """Code d'accès de tous les appareils, le Mac compris : créé au premier lancement, avec ou sans --lan, gardé dans
    tools/access_code.txt (0o600). Un fichier illisible n'est jamais écrasé (OSError, ValueError : setup_access
    arrête le lancement) ; un fichier lisible mais trop court est remplacé, s'il l'est encore après l'attente d'un
    autre lancement qui l'écrirait (wait_access_code) : un fichier vide n'est jamais effacé sous ce lancement-là."""
    code = read_access_code()
    if code:
        return code
    if os.path.exists(ACCESS_FILE):
        code = wait_access_code()                    # peut-être en cours d'écriture par un autre lancement
        if code:
            return code
        try:
            os.remove(ACCESS_FILE)                   # resté trop court : remplacé par un nouveau code
        except FileNotFoundError:
            pass
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"          # sans caractères ambigus (0/o, 1/l/i)
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    code = raw[:4] + "-" + raw[4:]
    try:                                             # création exclusive, d'emblée en 0o600
        fd = os.open(ACCESS_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:                          # créé entre-temps par un autre lancement : son code est gardé
        code = wait_access_code()
        if code:
            return code
        raise AccessPending()
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    return code


def setup_access():
    """Code d'accès chargé ou créé, et empreinte du cookie qui le prouve : posés par main() à chaque lancement, avec ou
    sans --lan (le Mac lui-même demande le code). Fichier illisible, ou encore en cours d'écriture par un autre
    lancement : arrêt, avec un message qui ne cite pas son contenu."""
    try:
        S.access_code = load_access_code()
    except AccessPending:                            # pas « supprimez-le » : ce serait perdre le code de l'autre
        sys.exit("[launch] un autre lancement crée tools/access_code.txt : patientez, puis relancez.")
    except (OSError, ValueError):
        sys.exit("[launch] tools/access_code.txt est illisible : supprimez-le, puis relancez (un nouveau code d'accès "
                 "sera créé, que chaque appareil redemandera).")
    S.access_token = access_token(S.access_code)


def access_cookie_header():
    """Cookie d'accès posé après le code (/api/login) ou le jeton d'entrée (/entrer). Lax et non Strict : Chrome Android
    compte l'ouverture de l'application installée (écran d'accueil) comme une arrivée d'un autre site et n'enverrait
    pas un cookie Strict, d'où le code redemandé à chaque ouverture. Lax n'est envoyé d'un autre site que pour
    l'ouverture d'une page (GET, sans effet) ; les POST restent protégés par _post_refused."""
    return f"{ACCESS_COOKIE}={S.access_token}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax"


def write_owner_only(path, text):
    """Écrit text dans path sans qu'un autre compte puisse le lire, même un instant : fichier temporaire au nom tiré au
    hasard, créé en 0o600 par création exclusive (O_EXCL : jamais un lien symbolique suivi), à côté, puis remplacement
    atomique (un ancien fichier, quels que soient ses droits, disparaît d'un coup). Pas replace_synced : son temporaire
    a un nom fixe, ouvert sans O_EXCL (un lien posé à sa place serait suivi), et il sert l'espace privé, qu'on ne
    touche pas ici ; pas de fsync non plus : un jeton d'entrée perdu à une coupure se refait."""
    tmp = f"{path}.{secrets.token_hex(8)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def make_entry(port):
    """Jeton d'entrée tiré au hasard (128 bits, tools/entry_token) et page de redirection vers
    http://127.0.0.1:<port>/entrer?jeton=<jeton> (tools/entry.html) ; renvoie le chemin de la page. Le navigateur
    ouvre ce fichier : le jeton ne passe jamais sur une ligne de commande, que ps montre aux autres comptes."""
    token = secrets.token_urlsafe(16)
    url = f"http://127.0.0.1:{port}/entrer?jeton={token}"
    with ENTRY_LOCK:                             # pas de jeton à moitié remplacé pendant un /entrer du même processus
        write_owner_only(ENTRY_TOKEN, token + "\n")
        write_owner_only(ENTRY_PAGE, '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
                         '<meta name="referrer" content="no-referrer">'
                         f'<meta http-equiv="refresh" content="0;url={url}"><title>Chambre noire</title></head>'
                         '<body><p>Ouverture de Chambre noire…</p></body></html>\n')
    return ENTRY_PAGE


def open_entry(port):
    """Ouvre l'interface dans le navigateur par la page de redirection (son chemin), jamais par l'adresse qui porte le
    jeton (launch.py --enter, et main() au lancement). Le système ouvre ce fichier .html avec son application
    habituelle : un éditeur réglé pour les .html l'ouvrirait à la place du navigateur (recours : l'adresse et le
    code)."""
    webbrowser.open(pathlib.Path(make_entry(port)).as_uri())


def open_browser(port):
    """Navigateur ouvert au lancement : par l'entrée à usage unique ; si elle ne peut pas s'écrire (dossier en lecture
    seule, disque plein), par l'adresse simple, sans jeton, où le code est demandé (une ligne neutre au journal)."""
    try:
        open_entry(port)
    except (OSError, ValueError):
        print("[launch] entrée sans code impossible : le code d'accès sera demandé", flush=True)
        webbrowser.open(f"http://127.0.0.1:{port}/")


def remove_entry():
    """Efface le jeton et sa page ; un fichier qui résiste (tenu ouvert sous Windows) reste, sans erreur : un jeton
    servi est de toute façon refusé ensuite (ENTRY_USED)."""
    for path in (ENTRY_TOKEN, ENTRY_PAGE):
        try:
            os.remove(path)
        except OSError:
            pass


def use_entry_token(token):
    """Vrai si token est le jeton d'entrée en cours : il est alors effacé, page de redirection comprise (usage unique).
    Un jeton de plus de ENTRY_TTL s est effacé et refusé ; un mauvais jeton n'efface rien (un autre compte effacerait
    sinon le jeton du porteur avant son navigateur). Comparaison en temps constant, en octets."""
    with ENTRY_LOCK:
        try:
            with open(ENTRY_TOKEN, encoding="utf-8") as f:
                # âge du fichier lu, pas d'un autre : un --enter qui le remplace entre-temps garde son jeton neuf
                age = time.time() - os.fstat(f.fileno()).st_mtime
                expected = f.read().strip()
        except (OSError, ValueError):
            return False
        if abs(age) > ENTRY_TTL:
            remove_entry()
            return False
        if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
            return False
        used = hashlib.sha256(expected.encode()).hexdigest()
        if used in ENTRY_USED:                   # déjà servi, fichier resté (effacement refusé)
            return False
        ENTRY_USED.add(used)
        remove_entry()
        return True


def cookie_value(header, name):
    """Valeur du cookie name dans un en-tête Cookie, ou None. Découpé à la main sur « ; » : SimpleCookie perd tout
    l'en-tête sur une seule paire mal formée, ou lève CookieError, et l'ordinateur partage ses cookies avec tout serveur
    de 127.0.0.1 ou localhost (autres applications). Guillemets autour de la valeur retirés."""
    for pair in header.split(";"):
        key, sep, value = pair.partition("=")
        if sep and key.strip() == name:
            value = value.strip()
            return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value
    return None


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
    access_code = None       # code demandé à tout appareil, le Mac compris (posé par setup_access, à chaque lancement)
    access_token = None      # valeur du cookie posé après saisie du code (empreinte du code, pas le code)
    lan_urls = []            # adresses affichées pour le téléphone
    lan_hosts = set()        # noms d'hôte admis en plus des noms locaux (ceux de lan_urls et le nom HTTPS de Tailscale)
    https_hosts = set()      # nom HTTPS de « tailscale serve » : seule origine, avec le Mac, où l'espace privé s'ouvre
    cfg = {}
    ui_port = 7860
    jobs = {}
    lots = {}                # lots en cours par identifiant : {"jobs": [...], "campaign"} ; garde les
                             # générations d'un lot même quand une génération privée a quitté S.jobs, jusqu'à la fin
                             # du lot
    private_sessions = {}    # sessions de l'espace privé : {jeton du cookie : {"key": clé privée, "seen": dernière requête privée}}
    rekeyed = {}             # clé publique remplacée par un changement de code → la suivante : une génération privée lancée
                             # avant le changement est rangée avec la nouvelle clé (store_private)
    pending = []             # générations en attente, dans l'ordre de calcul : seule source de l'ordre de la file ; une
                             # génération annulée y reste jusqu'à ce que worker() la saute
    turn = threading.Condition()   # protège pending : un lot y entre d'un bloc, « Passer en tête » y réordonne,
                                   # worker() y prend la tête, la pose dans current et la passe « en cours » en
                                   # une seule opération ; cancel_job y annule (la fin d'une génération, done ou
                                   # failed, s'écrit sans lui)
    current = None
    # compteur de chaque espace, augmenté à chaque image arrivée dans sa pile et à chaque Garder, Jeter, Supprimer
    # (sous le verrou du changement) : l'interface relit pile et tirages quand celui de son espace change. Il part de
    # l'heure du lancement, pour qu'un redémarrage ne redonne pas une valeur qu'une page a déjà vue.
    rev = dict.fromkeys(("public", "private"), time.time_ns() // 1_000_000)
    started = None           # version du code au lancement du serveur (code_version) : launch.py n'est relu qu'au
                             # redémarrage, l'interface à chaque requête


S = State()


def data_url_bytes(data_url):
    return base64.b64decode(data_url.split(",", 1)[1] if "," in data_url else data_url)


def write_data_url(data_url, path, what="image d'entrée"):
    """Écrit l'image d'une data URL dans path et renvoie ses dimensions ; ValueError « <what> illisible » si ce n'est
    pas une image que Pillow sait lire. Un PNG ou un JPEG est écrit tel quel ; un autre format (WebP, AVIF, TIFF…),
    que la page envoie tel qu'elle l'a reçu et que sd-cli (stb_image) refuse, est converti en PNG."""
    from PIL import Image
    try:
        raw = data_url_bytes(data_url)
        with Image.open(io.BytesIO(raw)) as im:
            size = im.size
            if im.format not in ("PNG", "JPEG"):
                buf = io.BytesIO()
                im.convert("RGBA" if "A" in im.getbands() or "transparency" in im.info else "RGB").save(buf, "PNG")
                raw = buf.getvalue()
        with open(path, "wb") as f:
            f.write(raw)
        return size
    except (ValueError, OSError) as e:          # base64 invalide, fichier qui n'est pas une image
        raise ValueError(f"{what} illisible") from e


def image_size(path):
    """Dimensions d'une image : chemin de fichier ou objet fichier (io.BytesIO)."""
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


def start_job(job):
    """Passe une génération « en cours » : worker() l'appelle sous S.turn, en même temps que la prise en tête ;
    tools/calibrate.py, qui lance run_job hors de la file, l'appelle aussi."""
    job["status"], job["started"], job["phase"] = "running", time.time(), "chargement du modèle"


def run_job(job):
    """Prépare et calcule une génération passée « en cours » par start_job ; une génération annulée depuis ne lance
    pas le moteur et ne laisse rien."""
    if job.get("status") == "cancelled":         # annulée depuis la prise en tête : pas même ses images d'entrée
        discard_cancelled(job)
        return
    cmd = build_cmd(job)
    job["cmd"] = " ".join(cmd)
    if job.get("status") == "cancelled":         # annulée pendant la préparation (images d'entrée)
        discard_cancelled(job)
        return
    logf = open(os.devnull if secret(job) else os.path.join(job["dir"], "sd-cli.log"), "wb")
    try:
        proc = subprocess.Popen(cmd, cwd=P("sdcpp", S.backend), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        logf.close()
        if job.get("status") == "cancelled":     # annulée entre-temps : elle le reste, sans message d'échec
            discard_cancelled(job)
            return
        job["status"] = "failed"
        job["error"] = f"impossible de lancer sd-cli : {e}"
        return
    job["proc"] = proc
    if job.get("status") == "cancelled":         # annulée pendant le lancement du moteur : arrêté aussitôt
        proc.kill()
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
        if job.get("private"):                   # chiffrée dans l'espace privé ; dossier supprimé par worker()
            item = keep_private(job)
            # annulée ou oubliée pendant le rangement : « done » n'écrase pas « cancelled », sous S.turn comme
            # cancel_job, et l'image rangée est supprimée (décision du 23/10/2026)
            with S.turn:
                cancelled = job.get("status") == "cancelled"
                if not cancelled:
                    job["item"], job["status"], job["phase"] = item, "done", "terminé"
            if cancelled:                         # une erreur du disque ici la laisse dans la pile privée, à jeter
                with PRIVATE_LOCK:
                    finish_rekey()
                    remove_private_item(item)
                return
            with PRIVATE_LOCK:                   # dans la pile privée : après « done », comme to_pile
                S.rev["private"] += 1
            print(DONE_LINE, flush=True)
            return
        if job.get("calibration"):                # les générations de tools/calibrate.py restent hors du journal
            job["status"] = "done"
            job["phase"] = "terminé"
        else:                                     # dans la pile, à trier
            meta = {"mode": job["req"].get("mode"), "prompt": job["req"]["prompt"], "width": job["req"]["width"], "height": job["req"]["height"],
                    "steps": job["req"]["steps"], "seed": job["req"].get("seed"), "seconds": job["seconds"], "encode_seconds": job.get("encode_seconds"),
                    "sec_per_it": job.get("sec_per_it"), "size": job["size"], "backend": S.backend, "model": S.model}
            if job.get("lot"):
                meta["lot"] = job["lot"]
            if not to_pile(job, meta):            # annulée pendant la fin du calcul : rien n'en reste
                discard_cancelled(job)
                return
        print(DONE_LINE, flush=True)
        record_calib(job)
    else:
        job["status"] = "failed"
        job["error"] = "sd-cli code " + str(rc) + " — " + " | ".join((job.get("error_lines") or tail)[-4:])
        # même ligne pour toutes les générations : le détail (qui peut citer le prompt) reste en mémoire pour
        # l'interface, hors de logs/, et rien n'y distingue une génération privée
        print(f"[job] échec : génération, sd-cli code {rc}", flush=True)


def secret(job):
    """Génération privée : rien d'elle ne doit rester en clair (journal, calibration, logs/, disque)."""
    return bool(job.get("private"))


def keep_private(job):
    """Fin d'une génération privée réussie : image, entrées et réglages chiffrés dans l'espace privé avec la clé publique
    du lancement, ou celle qui l'a remplacée si le code a changé (aucun code ni session n'est nécessaire, l'espace peut
    avoir été verrouillé). Si l'espace a été supprimé ou recréé entre-temps, l'image est abandonnée (store_private)."""
    r = job["req"]
    meta = {"mode": job["mode"], "prompt": r["prompt"], "width": r["width"], "height": r["height"], "steps": r["steps"],
            "seed": r.get("seed"), "seconds": job["seconds"], "model": S.model, "lot": job.get("lot"), "time": int(job["finished"]),
            "dims": job.get("dims"), "pile": True}   # à trier : la marque reste dans la fiche chiffrée
    with open(job["out"], "rb") as f:
        image = f.read()
    return store_private(job["public"], meta, image, read_inputs(job["dir"]))


def discard_cancelled(job):
    """Génération annulée : rien n'en reste sur le disque, ni le dossier de travail (images d'entrée, aperçus, journal du
    moteur), ni une image finale que sd-cli aurait commencé à écrire avant d'être arrêté. Sa fin est notée si rien ne
    l'a encore fait (annulée au démarrage) : le suivi et sweep() la comptent depuis là."""
    job.setdefault("finished", time.time())
    shutil.rmtree(job["dir"], ignore_errors=True)
    try:
        os.remove(job["out"])
    except OSError:
        pass


def forget_files(job):
    """Fin d'un job privé : supprime son dossier de travail et retire de la mémoire le prompt, les images d'entrée et la
    ligne de commande."""
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
        print("[job] fin de génération incomplète", flush=True)   # sans détail, qui peut citer un fichier
        return
    job["status"], job["phase"] = "failed", "échec"
    job["error"] = f"génération impossible : {e}"
    job.setdefault("finished", time.time())
    # même ligne pour toutes les générations : le détail (qui peut citer un fichier de travail) reste en mémoire pour
    # l'interface, hors de logs/
    print("[job] échec : génération, erreur de préparation", flush=True)


ACTIVE = ("queued", "running")             # statuts d'une génération de la file


def cancel_job(job):
    """Annule une génération en file ou en cours (le moteur est arrêté) ; une génération terminée garde son statut et son
    image. worker() supprime ensuite ses fichiers. Sous S.turn, comme la prise en tête par worker() : une génération
    prise en tête est déjà « en cours »."""
    with S.turn:
        if job.get("status") not in ACTIVE:
            return
        if job["status"] == "queued":
            job["finished"] = time.time()       # fin d'une génération qui n'a jamais tourné (run_job pose celle des autres)
        job["status"] = "cancelled"
        job["phase"] = "annulé"
    proc = job.get("proc")                      # lu après le statut : run_job pose proc, puis relit le statut
    if proc and proc.poll() is None:
        proc.kill()


def forget_job(job):
    """Génération privée que sa page fait oublier, ou trop ancienne (sweep) : arrêtée si elle tournait encore, puis plus
    rien en mémoire (le dossier de travail est supprimé par worker() à la fin de la génération)."""
    cancel_job(job)
    S.jobs.pop(job["id"], None)


def sweep():
    """Ménage fait à chaque requête : une génération privée terminée (réussie, en échec ou annulée) que sa page n'a
    jamais fait oublier (page fermée ou tuée avant la fin) est oubliée PRIVATE_JOB_TTL secondes après sa fin ; une
    session de l'espace privé sans requête privée depuis PRIVATE_IDLE secondes est fermée (clé privée oubliée)."""
    now = time.time()
    for token, session in list(S.private_sessions.items()):
        if now - session["seen"] > PRIVATE_IDLE:
            S.private_sessions.pop(token, None)
    for job in list(S.jobs.values()):
        if (secret(job) and job.get("status") not in ACTIVE
                and now - (job.get("finished") or job["created"]) > PRIVATE_JOB_TTL):
            forget_job(job)


def worker():
    """Thread de calcul : une génération à la fois, dans l'ordre de la file. Aucune exception ne l'arrête : la
    génération en cause échoue et la suivante démarre."""
    while True:
        with S.turn:                               # tête de la file, et génération en cours, en une seule opération
            while not S.pending:
                S.turn.wait()
            job = S.pending.pop(0)
            if job.get("status") != "cancelled":
                # « en cours » posé dans la même section : une annulation (cancel_job, sous S.turn) passe avant ou
                # après, jamais entre la prise en tête et le passage en cours, et run_job ne l'écrase plus
                S.current = job["id"]
                start_job(job)
        try:
            if job.get("status") == "cancelled":       # annulée avant de démarrer
                discard_cancelled(job)
                continue
            try:
                run_job(job)
            except Exception as e:
                fail_job(job, e)
            if job.get("status") in ("done", "failed") and not job.get("lot"):
                notify_job(job)
        except Exception:
            print("[job] erreur du thread de calcul", flush=True)   # sans détail : même ligne pour toutes
        finally:
            # S.current rendu en dernier : « plus de génération en cours » veut dire fichiers rangés et notification
            # du lot décidée (le banc s'y synchronise au lieu d'attendre au hasard)
            try:
                job.pop("proc", None)
                if secret(job):
                    forget_files(job)
                if job.get("lot"):
                    end_of_lot(job)
            finally:
                S.current = None


def end_of_lot(job):
    """Après chaque génération d'un lot, terminée ou annulée en file : le lot est fini quand aucune de ses générations
    n'attend ni ne tourne. Il quitte alors S.lots (rien n'en reste en mémoire pour un lot privé oublié par sa page)
    et sa notification part, une seule fois : une génération annulée en file passe encore par worker() après la fin
    du lot, mais ne le trouve plus."""
    lot = S.lots.get(job["lot"]["id"])
    if lot and not any(j.get("status") in ACTIVE for j in lot["jobs"]):
        S.lots.pop(job["lot"]["id"], None)
        try:
            notify_lot(lot)
        except Exception:
            print("[push] notification du lot impossible", flush=True)   # sans détail : même ligne pour tous


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
    if req.get("private") is not None and not isinstance(req["private"], bool):
        return "private : vrai ou faux attendu"
    if req.get("incognito"):                    # ancienne page restée ouverte : jamais une image en clair à sa place
        return "L'incognito n'existe plus : passez par l'espace privé."
    count = req.get("count")
    if count is not None:
        if not is_int(count) or not 1 <= count <= MAX_VARIANTS:
            return f"count : nombre entier de 1 à {MAX_VARIANTS} attendu"
        if count > 1 and req.get("campaign") is not None:
            return "count : pas de variantes dans une campagne"
    campaign = req.get("campaign")
    if campaign is not None:
        if req.get("mode") != "edit":
            return "campaign : campagne en mode Éditer (edit) seulement"
        if not isinstance(campaign, list) or not 1 <= len(campaign) <= MAX_CAMPAIGN:
            return f"campaign : liste de 1 à {MAX_CAMPAIGN} photos attendue"
        if req.get("ref_images"):
            return "campaign : les photos vont dans campaign, pas dans ref_images"
        for c in campaign:                   # chaque photo devient une génération : mêmes contrôles qu'une demande seule
            if not isinstance(c, dict) or not isinstance(c.get("image"), str):
                return "campaign : chaque photo porte son image (data URL)"
            if not all(is_int(c.get(k)) and 64 <= c[k] <= 4096 for k in ("width", "height")):
                return "campaign : largeur et hauteur de chaque photo, nombres entiers de 64 à 4096"
    return None


def expand_request(req):
    """Demandes des générations d'une demande validée, chacune avec sa graine : une seule, ou une par image d'un lot
    (variantes : count fois le même prompt ; campagne : une édition par photo, cette seule photo en référence, à ses
    dimensions)."""
    campaign = req.pop("campaign", None)
    n = req.pop("count", None) or 1
    seeds = draw_seeds(req.get("seed", -1), len(campaign) if campaign else n)
    if campaign:
        return [{**req, "ref_images": [c["image"]], "width": c["width"], "height": c["height"], "seed": seed}
                for c, seed in zip(campaign, seeds)]
    return [{**req, "seed": seed} for seed in seeds]


def draw_seeds(seed, n):
    """Graines des n générations d'une demande. Graine au hasard (-1) : tirées par le serveur, distinctes, pour qu'elles
    soient connues et écrites au journal ; graine choisie : seed, seed+1… (variantes reproductibles)."""
    if seed != -1:
        return [(seed + k) % 2 ** 63 for k in range(n)]
    seeds = []
    while len(seeds) < n:
        s = secrets.randbelow(2 ** 31)       # reste exact en JavaScript et dans le JSON
        if s not in seeds:
            seeds.append(s)
    return seeds


def active_jobs():
    """Générations de la file : celle en cours d'abord, puis les autres dans l'ordre de calcul (S.pending)."""
    with S.turn:
        jobs = [S.jobs.get(S.current)] + S.pending
    return [j for j in jobs if j and j.get("status") in ACTIVE]


def move_first(jobs):
    """« Passer en tête » : celles de jobs encore en attente (dans S.pending) passent juste après la génération en
    cours, dans l'ordre de jobs ; False si aucune n'attend plus (en cours, finie ou annulée)."""
    with S.turn:
        waiting = {j["id"] for j in S.pending if j.get("status") == "queued"}
        moved = [j for j in jobs if j["id"] in waiting]
        if not moved:
            return False
        moved_ids = {j["id"] for j in moved}
        S.pending[:] = moved + [j for j in S.pending if j["id"] not in moved_ids]
    return True


def moved_first(jobs, error):
    """Réponse d'une route « Passer en tête » : 200, ou 409 avec error si rien de jobs n'attend plus."""
    return (200, {"ok": True}) if move_first(jobs) else (409, {"error": error})


def in_space(job, private):
    """La génération est-elle de cet espace : privée pour l'espace privé, normale pour l'espace public."""
    return bool(job.get("private")) == private


def queue_ranks(active, private):
    """Rang de chaque génération d'un espace dans la file (active : active_jobs()), par identifiant : 0 pour celle qui
    tourne, sinon le nombre de générations de l'espace en attente devant elle, plus une si une génération tourne,
    de quelque espace qu'elle soit (« 1re en attente » derrière une génération cachée, sans compter celles-ci).
    Une génération finie que worker() range encore (S.current posé) occupe toujours le moteur : la suivante reste
    « 1re »."""
    with S.turn:
        busy = S.current is not None
    running = busy or any(j["status"] == "running" for j in active)
    ranks, waiting = {}, 0
    for j in active:
        if in_space(j, private):
            ranks[j["id"]] = 0 if j["status"] == "running" else waiting + running
            waiting += j["status"] == "queued"
    return ranks


def queue_position(job):
    """Rang de la génération parmi celles de son espace (queue_ranks), None si elle n'est plus dans la file. Calculé à
    chaque lecture : il avance à mesure que la file se vide."""
    if job.get("status") not in ACTIVE:
        return None
    return queue_ranks(active_jobs(), bool(job.get("private"))).get(job["id"])


def request_inputs(req):
    """Pixels des images d'entrée tels que build_cmd les donnera au moteur, lus dans l'en-tête des images dès la demande,
    pour estimer la durée avant le calcul : (références, image de départ). Une image illisible ne compte pas (elle
    fera échouer sa génération)."""
    w, h, refs = req["width"], req["height"], []
    for ref in req.get("ref_images") or []:
        try:
            refs.append(estimate.ref_px(*image_size(io.BytesIO(data_url_bytes(ref))), w, h))
        except Exception:
            pass
    return refs, (w * h if req.get("init_image") else 0)


def job_estimate(job, r, coefs):
    """Durée estimée d'une génération de la file (estimate.predict, seule source de l'estimation) ; r : sa demande, lue
    une seule fois par l'appelant (forget_files la retire à la fin d'une génération secrète, à tout moment)."""
    refs, init = job["inputs"]
    previews = r["steps"] // (r.get("preview_interval") or 5) if r.get("preview") else 0
    return estimate.predict(coefs, r["width"], r["height"], r["steps"], refs, init, previews)


def queue_entry(job, position, ahead, coefs):
    """Entrée de la liste de la file (/api/status), vue depuis l'espace de la génération. Une génération privée n'est
    vue que depuis l'espace privé, où elle a une entrée complète comme une génération normale, genre « private ».
    ahead : durée restante estimée des générations de l'autre espace placées devant elle. None si la génération vient
    de finir."""
    r = job.get("req")
    if r is None:
        return None
    est, lot = job_estimate(job, r, coefs), job.get("lot")
    prompt = " ".join(r["prompt"].split())
    # réglages de la demande : proportions de la vignette et ligne des réglages de la file
    return {"status": job["status"], "position": position, "ahead": round(ahead, 1), "lot": lot and dict(lot),
            "estimate": round(est, 1),
            "elapsed": round(time.time() - job["started"], 1) if job.get("started") else None,
            "kind": "private" if job.get("private") else "normal", "id": job["id"], "mode": job["mode"],
            "width": r["width"], "height": r["height"], "steps": r["steps"],
            "prompt": prompt[:80] + ("…" if len(prompt) > 80 else "")}


def queue_view(private, coefs):
    """Liste de la file vue depuis un espace : les entrées de ses seules générations, rangs propres à l'espace
    (queue_ranks) ; le travail de l'autre espace placé devant une entrée compte dans son ahead (la génération en cours
    pour ce qui lui reste, les autres pour leur estimation)."""
    active, now = active_jobs(), time.time()
    ranks, entries, hidden = queue_ranks(active, private), [], 0.0
    for j in active:
        if in_space(j, private):
            e = queue_entry(j, ranks[j["id"]], hidden, coefs)
            if e:
                entries.append(e)
        else:
            r = j.get("req")
            est = job_estimate(j, r, coefs) if r else 0.0
            hidden += max(0.0, est - (now - j["started"])) if j["status"] == "running" and j.get("started") else est
    return entries


def new_job(req, inputs, lot=None):
    """Génération en attente pour une demande validée (sa graine déjà fixée), avec son dossier de travail. Identifiant
    d'une génération privée : 128 bits tirés au hasard, impossible à deviner pour un autre appareil ; celui d'une
    génération normale dit sa date."""
    private = req.get("private") is True
    jid = (secrets.token_hex(16) if private
           else datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
    mode = re.sub(r"[^a-z0-9]", "", str(req.get("mode", "img"))) or "img"
    d = P("jobs", ("private_" if private else "") + jid)
    os.makedirs(d, exist_ok=True)
    if private:                                 # PNG en clair et prompt dans ses métadonnées : pour le seul compte,
        os.chmod(d, 0o700)                      # même sans le masque de restrict_new_files
    # le PNG s'écrit dans le dossier de travail : une génération normale le fait passer dans la pile une fois fini
    # (to_pile), la pile ne voit jamais une image à moitié écrite ; une privée le chiffre (keep_private)
    out = os.path.join(d, f"{jid}_{mode}.png")
    return {"id": jid, "req": req, "mode": mode, "dir": d, "out": out, "status": "queued", "created": time.time(),
            "private": private, "inputs": inputs, "seed": req["seed"], "lot": lot,
            # noms des images d'entrée que build_cmd écrit et que save_inputs garde (init.png, puis ref_N.png) : la page
            # qui suit la génération les montre, même après l'oubli de la demande
            "input_names": (["init.png"] if req.get("init_image") else [])
            + [f"ref_{i + 1}.png" for i in range(len(req.get("ref_images") or []))],
            "public": private and (read_space() or {}).get("public")}    # clé publique de l'espace au lancement


def public(job):
    keys = ("id", "status", "phase", "step", "total", "sec_per_it", "sec_per_it_recent", "started", "finished", "seconds", "encode_seconds",
            "preview_version", "preview_interval", "size", "dims", "error")
    d = {k: job.get(k) for k in keys}
    d["queue_position"] = queue_position(job)
    d["elapsed"] = round(time.time() - job["started"], 1) if job.get("started") and not job.get("finished") else job.get("seconds")
    d["private"] = bool(job.get("private"))
    d["item"] = job.get("item")                   # image privée rangée : identifiant dans la pile privée
    d["lot"], d["seed"] = job.get("lot"), job.get("seed")
    d["mode"], d["inputs"] = job.get("mode"), job.get("input_names") or []   # vrai mode, images d'entrée gardées
    # prompt complet, pour la page qui reprend une génération (la file n'en montre que le début) : tant que la demande
    # est en mémoire (une privée l'oublie à sa fin) ; une privée n'est suivie que dans l'espace privé (_hidden)
    d["prompt"] = (job.get("req") or {}).get("prompt")
    d["path"] = job["out"] if job.get("status") == "done" and not secret(job) else None
    d["name"] = os.path.basename(job["out"])
    return d


QUIET_ROUTES = ("/api/status", "/api/job/", "/api/private/", "/api/lot/", "/api/generate", "/entrer")
REQUEST_PATH_RE = re.compile(r'"[A-Z]+ ([^ ?#]*)')   # chemin de la ligne de requête, sans ce qui suit « ? »


def quiet_request(msg):
    """Requêtes tues dans le journal du serveur même en erreur (les réussies n'y vont jamais : H.log_request), d'après
    leur chemin seul (une chaîne de requête ne fait rien taire) : suivi de l'état et des générations, et tout ce qui
    peut toucher à l'espace privé (rien n'en va dans logs/), annulation et passage en tête d'une génération ou d'un lot
    compris (leur identifiant), et toute demande de génération, ses refus propres (403, 503) ne venant que de l'espace
    privé (décision du 23/10/2026). Ainsi tus, les refus d'accès d'une demande de génération (401, 403, 415) ne sont
    plus suivis non plus."""
    m = REQUEST_PATH_RE.match(msg)
    if m:
        return m.group(1).startswith(QUIET_ROUTES)
    return any(route in msg for route in QUIET_ROUTES)


# erreurs d'écriture d'une connexion que l'appareil a fermée : macOS donne parfois EPROTOTYPE ou ENOTCONN, un simple
# OSError, au lieu de EPIPE
CUT_ERRNOS = {getattr(errno, n) for n in ("EPIPE", "ECONNRESET", "ECONNABORTED", "ESHUTDOWN", "EPROTOTYPE", "ENOTCONN")
              if hasattr(errno, n)}


def cut_connection(e):
    """L'erreur vient-elle d'une connexion fermée par l'appareil ?"""
    return isinstance(e, ConnectionError) or isinstance(e, OSError) and e.errno in CUT_ERRNOS


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Python n'en garde que 5 par défaut : la galerie ouvre une connexion par miniature et, pendant que le processeur les
    # fabrique, les suivantes étaient refusées (« Connection reset by peer », miniature cassée sur le téléphone)
    request_queue_size = 128

    def handle_error(self, request, client_address):
        # connexion coupée par l'appareil (page quittée pendant un chargement) : une ligne neutre au lieu de la pile
        # d'appels de Python, qui nommerait une route privée, l'adresse de l'appareil et des chemins du Mac
        if cut_connection(sys.exc_info()[1]):
            print("[ui] connexion interrompue", flush=True)
            return
        super().handle_error(request, client_address)


class H(BaseHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        # seules les requêtes en erreur vont au journal : la suite des requêtes réussies (image et miniature lues après
        # une génération normale seulement) trahirait les générations privées (décision du 23/10/2026)
        if isinstance(code, int) and code < 400:   # int ou HTTPStatus
            return
        super().log_request(code, size)

    def log_message(self, fmt, *args):
        msg = fmt % args
        if not quiet_request(msg):
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

    def _secure(self):
        """Requête qui ne passe pas en clair sur le réseau : le Mac lui-même, ou l'adresse HTTPS de « tailscale serve »,
        qui relaie depuis 127.0.0.1. Jugé sur l'adresse source et le nom d'hôte, jamais sur les en-têtes de relais, qu'un
        appareil du Wi-Fi peut envoyer en http://. Seule origine où l'espace privé s'ouvre (décision du porteur)."""
        return self.client_address[0] in LOCAL_CLIENTS and self._host() in self._local_hosts() | S.https_hosts

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
        """Tout appareil, le Mac lui-même compris, doit avoir saisi le code d'accès (cookie), avec ou sans --lan ; seuls
        les fichiers publics (PUBLIC_FILES) passent sans lui, avant ce contrôle. Sans code chargé, rien ne passe."""
        if not S.access_token:
            return False
        value = cookie_value(self.headers.get("Cookie", ""), ACCESS_COOKIE)
        # en octets : compare_digest lève TypeError sur un texte non ASCII (cookie mal formé, jamais une erreur)
        return value is not None and hmac.compare_digest(value.encode(), S.access_token.encode())

    def _private_token(self):
        return cookie_value(self.headers.get("Cookie", ""), PRIVATE_COOKIE)

    def _private_session(self, touch=False):
        """Session de l'espace privé de cet appareil (cookie), ou None ; touch : requête privée, qui la prolonge."""
        session = S.private_sessions.get(self._private_token())
        if session and touch:
            session["seen"] = time.time()
        return session

    def _in_private(self):
        """Cet appareil est-il dans l'espace privé : session ouverte (sans la prolonger) et requête sûre, pour que rien
        de privé ne parte en clair même si le cookie de session suit une adresse http:// du même nom."""
        return HAVE_CRYPTO and self._secure() and self._private_session() is not None

    def _hidden(self, job, touch=False):
        """Génération privée que cet appareil ne peut ni suivre, ni prévisualiser, ni annuler : hors de l'espace privé
        (_in_private), elle est traitée comme un identifiant inconnu. touch : geste dans l'espace (annulation), qui
        prolonge la session ; le suivi, répété chaque seconde, ne la prolonge pas."""
        if not job.get("private"):
            return False
        if not self._in_private():
            return True
        if touch:
            self._private_session(touch=True)
        return False

    def _send_private(self, code, reply, token=""):
        """Réponse qui pose le cookie de session de l'espace privé (token), ou l'efface (token vide) : HttpOnly, sans
        durée de vie (perdu à la fermeture du navigateur), distinct du cookie d'accès."""
        self._send(code, reply, headers={"Set-Cookie": f"{PRIVATE_COOKIE}={token}; Path=/;{'' if token else ' Max-Age=0;'} HttpOnly; SameSite=Strict"})

    def _open_session(self, key):
        """Ouvre une session pour cet appareil et renvoie son jeton (cookie) : la clé privée reste en mémoire du serveur.
        Sous PRIVATE_LOCK : un changement de code qui suit ferme aussi cette session."""
        S.private_sessions.pop(self._private_token(), None)   # session précédente de l'appareil : sa clé ne reste pas
        token = secrets.token_urlsafe(32)
        S.private_sessions[token] = {"key": key, "seen": time.time()}
        return token

    def _private_get(self, path, q):
        """Lectures de l'espace privé, session exigée (elles la prolongent) : history, pile, thumb, image, input."""
        if not HAVE_CRYPTO:
            return self._send(503, {"error": "espace privé indisponible : bibliothèque cryptography non installée"})
        if not self._secure():
            return self._send(403, {"error": PRIVATE_HTTPS_ONLY})
        session = self._private_session(touch=True)
        if not session:
            return self._send(403, {"error": "espace privé verrouillé"})
        key, item, action = session["key"], q.get("id"), path[len("/api/private/"):]
        if action in ("history", "pile"):        # tirages ou pile de l'espace
            return self._send(200, private_items(key, pile=action == "pile"))
        if action == "prompts":                   # prompts enregistrés de l'espace, le dernier utilisé d'abord
            try:
                saved = sorted(private_prompts(key), key=lambda p: -p["used"])
            except StaleKey:
                return self._send(403, {"error": "espace privé verrouillé"})
            except OSError:                       # changement de code en cours de réparation, disque
                return self._send(500, {"error": "prompts privés indisponibles : réessayez dans un instant"})
            except (InvalidTag, ValueError):
                return self._send(500, {"error": "prompts privés illisibles"})
            return self._send(200, {"saved": saved, "types": prompt_types()})
        try:
            if action == "input":                 # images d'entrée : par leur nom dans meta (init.png, ref_N.png)
                meta = json.loads(read_private(key, item, "meta") or b"{}")
                names = meta.get("inputs") or []
                raw = read_private(key, item, f"input_{names.index(q.get('file'))}") if q.get("file") in names else None
                if raw and q.get("thumb"):
                    return self._send(200, thumb_jpeg(io.BytesIO(raw)), "image/jpeg")
            elif action in ("thumb", "image"):
                raw = read_private(key, item, action)
            else:
                return self._send(404, {"error": "not found"})
        except (InvalidTag, ValueError):
            return self._send(500, {"error": "image privée illisible"})
        if raw is None:
            return self._send(404, {"error": "image privée inconnue"})
        ctype = "image/jpeg" if action == "thumb" else "image/png"
        extra = {"Content-Disposition": f'attachment; filename="prive_{item[:8]}{"_" + q["file"][:-4] if action == "input" else ""}.png"'} if q.get("download") else None
        return self._send(200, raw, ctype, extra)

    def _private_post(self, path, raw):
        """Routes POST de l'espace privé : create, unlock, lock, code, reset, delete, keep, discard. Rien n'en va dans
        les journaux."""
        if not HAVE_CRYPTO:
            return self._send(503, {"error": "espace privé indisponible : bibliothèque cryptography non installée"})
        try:
            body = json.loads(raw)
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return self._send(400, {"error": "objet JSON attendu"})
        action = path[len("/api/private/"):]
        if action not in ("lock", "reset") and not self._secure():   # verrouiller : partout ; reset : le Mac seul
            return self._send(403, {"error": PRIVATE_HTTPS_ONLY})
        if action == "delete":                  # supprimer une image privée, session exigée
            if not self._private_session(touch=True):
                return self._send(403, {"error": "espace privé verrouillé"})
            item = body.get("id")
            with PRIVATE_LOCK:                  # jamais pendant un changement de code (l'image y serait recopiée)
                try:
                    finish_rekey()
                    if not (isinstance(item, str) and ITEM_RE.fullmatch(item)
                            and os.path.isdir(os.path.join(PRIVATE, "items", item))):
                        return self._send(404, {"error": "image privée inconnue"})
                    remove_private_item(item)
                except (OSError, ValueError):   # changement de code en cours de réparation, disque, space.json
                    return self._send(500, {"error": "image privée non supprimée : réessayez dans un instant"})
            return self._send(200, {"ok": True})
        if action in ("keep", "discard"):       # Garder, Jeter une image de la pile privée, session exigée
            session = self._private_session(touch=True)
            if not session:
                return self._send(403, {"error": "espace privé verrouillé"})
            try:
                return self._send(*sort_private(action, session["key"], body.get("id")))
            except StaleKey:
                return self._send(403, {"error": "espace privé verrouillé"})
            except (InvalidTag, ValueError):
                return self._send(500, {"error": "image privée illisible"})
            except OSError:                     # changement de code en cours de réparation, disque
                return self._send(500, {"error": "image privée non triée : réessayez dans un instant"})
        m = re.fullmatch(r"prompts(?:/(delete|used))?", action)
        if m:                                   # prompts enregistrés de l'espace, session exigée
            session = self._private_session(touch=True)
            if not session:
                return self._send(403, {"error": "espace privé verrouillé"})
            verb = m.group(1) or "save"            # save, delete ou used
            error = prompt_error(verb, body)
            if error:
                return self._send(400, {"error": error})
            try:
                return self._send(*change_prompt(verb, body, lambda update: private_prompts(session["key"], update)))
            except StaleKey:
                return self._send(403, {"error": "espace privé verrouillé"})
            except (OSError, InvalidTag, ValueError):
                return self._send(500, {"error": "prompts privés non modifiés"})
        if action == "lock":
            S.private_sessions.pop(self._private_token(), None)
            return self._send_private(200, {"ok": True})
        if action == "reset":                   # sans le code (oublié) : tout l'espace est effacé, sessions comprises
            if not self._local():               # depuis le Mac lui-même seulement (décision du porteur du 14/10/2026)
                return self._send(403, {"error": "l'espace privé ne se supprime sans le code que sur le Mac lui-même"})
            if body.get("confirm") != "SUPPRIMER":
                return self._send(400, {"error": "tapez SUPPRIMER pour confirmer"})
            with PRIVATE_LOCK:
                S.private_sessions.clear()
                try:
                    shutil.rmtree(PRIVATE)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    return self._send(500, {"error": f"espace privé non supprimé en entier : {e}"})
            return self._send_private(200, {"ok": True})
        if action not in ("create", "unlock", "code"):
            return self._send(404, {"error": "not found"})
        new = body.get("new" if action == "code" else "code")
        error = private_code_error(new) if action in ("create", "code") else None
        if error:
            return self._send(400, {"error": error})
        with PRIVATE_LOCK:                      # un essai à la fois : la dérivation coûte 256 Mio de mémoire
            try:
                finish_rekey()                  # changement de code interrompu : terminé ou abandonné avant tout
            except OSError:
                return self._send(500, {"error": "espace privé en cours de réparation : réessayez dans un instant"})
            space = read_space()
            if action == "create" and space:
                return self._send(409, {"error": "l'espace privé existe déjà"})
            if action == "create":
                key = X25519PrivateKey.generate()
                write_space(b64e(key.public_key().public_bytes_raw()), key, new)
            elif not space:
                return self._send(404, {"error": "aucun espace privé"})
            else:
                key = open_space(space, body.get("old" if action == "code" else "code"))
                if key and action == "code":    # nouvelle paire de clés, images rechiffrées, toutes les sessions fermées
                    try:
                        S.rekeyed[space["public"]] = rekey_space(key, new)
                    except Exception:
                        return self._send(500, {"error": "code privé inchangé : les images n'ont pas pu être rechiffrées"})
                    S.private_sessions.clear()
                    try:
                        finish_rekey()
                    except OSError:
                        return self._send_private(500, {"error": "code privé changé, mais images pas encore toutes rangées : "
                                                                 "elles le seront à la prochaine ouverture de l'espace"})
            # session ouverte sous le verrou : un changement de code ne peut pas se glisser entre la vérification du code
            # et l'ouverture, qui laisserait une session avec l'ancienne clé après S.private_sessions.clear()
            token = self._open_session(key) if key and action in ("create", "unlock") else ""
        if not key:
            time.sleep(1)                       # freine les essais en série (hors du verrou : n'en bloque pas d'autres)
            return self._send(403, {"error": "code privé incorrect"})
        return self._send_private(200, {"ok": True}, token)   # code : cookie effacé (toutes les sessions sont fermées)

    def _send_login(self):
        """Page du code d'accès ; pour l'ordinateur lui-même (_local), avec la phrase qui dit comment entrer."""
        return self._send(200, LOGIN_PAGE.replace("<!--mac-->", LOGIN_MAC if self._local() else ""),
                          "text/html; charset=utf-8")

    def _enter(self, query):
        """GET /entrer?jeton=… (page de redirection de launch.py --enter) : depuis l'ordinateur lui-même seulement
        (_local, qui exclut une requête relayée et le Wi-Fi), bon jeton de moins de ENTRY_TTL s → cookie d'accès et
        303 vers / ; refusée, un navigateur qui a déjà le cookie (adresse rouverte depuis l'historique, onglet d'un
        --enter plus ancien) est renvoyé vers / sans toucher au jeton, les autres reçoivent la page du code. Route tue
        par le journal (QUIET_ROUTES) : le jeton n'y va jamais."""
        entered = self._local() and S.access_token and use_entry_token(parse_qs(query).get("jeton", [""])[0])
        if not entered and not self._allowed():
            return self._send_login()
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        if entered:
            self.send_header("Set-Cookie", access_cookie_header())
        self.end_headers()

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "nom d'hôte refusé"})
        sweep()
        path, _, query = self.path.partition("?")
        if path == "/entrer":      # avant _allowed : le jeton d'entrée tient lieu de code (launch.py --enter)
            return self._enter(query)
        if path in PUBLIC_FILES:   # manifeste, icônes, service worker : demandés par le navigateur sans le cookie d'accès
            name, ctype = PUBLIC_FILES[path]
            return self._send(200, open(P("tools", "ui", name), "rb").read(), ctype)
        if not self._allowed():
            if path in ("/", "/index.html"):
                return self._send_login()
            return self._send(401, {"error": "code d'accès requis"})
        if path in ("/", "/index.html"):
            return self._send(200, open(P("tools", "ui", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if path == "/api/status":
            missing = [k for k, v in MODELS.items() if not os.path.exists(v)]
            # espace de l'appareil : la file, la génération en cours et la dernière image ne montrent que les siennes
            inside = self._in_private()
            # dernière génération normale (jamais une privée)
            last = None if inside else max((j for j in list(S.jobs.values()) if not secret(j)), key=lambda j: j["created"],
                                           default=None)
            # génération en cours lue une seule fois : relu plus bas, S.current pourrait déjà désigner la suivante (une
            # privée, dont l'identifiant partirait dans current_job hors de l'espace privé)
            current_id = S.current
            coefs, current = S.store.coefficients(S.backend, S.model, S.engine), S.jobs.get(current_id) or {}
            queue = queue_view(inside, coefs)
            return self._send(200, {"sd_ready": not missing, "backend": S.backend, "busy": current_id is not None,
                                    "detail": ("fichiers manquants : " + ", ".join(missing)) if missing else "prêt",
                                    "model": os.path.basename(MODELS["diffusion"]), "model_version": S.model,
                                    "queued": sum(e["status"] == "queued" for e in queue),
                                    "queue": queue,
                                    "current_job": current_id if current and in_space(current, inside) else None,
                                    "last_job": public(last) if last else None,
                                    "estimates": coefs,
                                    # pile et tirages de l'espace de l'appareil (hors de l'espace privé : le public)
                                    "rev": S.rev["private" if inside else "public"],
                                    # code servi (git) : l'interface maintenant, le serveur à son lancement
                                    "version": code_version(), "server_version": S.started,
                                    # adresse et code pour le téléphone : montrés seulement sur le Mac lui-même, avec
                                    # --lan (noms du Wi-Fi et de Tailscale admis)
                                    "phone": ({"urls": S.lan_urls, "code": S.access_code}
                                              if S.lan_hosts and self._local() else None),
                                    # espace privé : existe-t-il, est-on dedans sur cet appareil (sans prolonger la session),
                                    # peut-il s'ouvrir par cette adresse (HTTPS ou le Mac) et y être supprimé sans le code
                                    # (le Mac lui-même seulement)
                                    "private": {"available": HAVE_CRYPTO, "exists": HAVE_CRYPTO and os.path.exists(os.path.join(PRIVATE, "space.json")),
                                                "unlocked": inside, "secure": self._secure(), "local": self._local()}})
        m = re.match(r"^/api/job/([\w-]+)(/preview)?$", path)
        if m:
            job = S.jobs.get(m.group(1))
            if not job or self._hidden(job):
                return self._send(404, {"error": "job inconnu"})
            if m.group(2):                        # aperçu (privé : par une requête sûre seulement, _hidden)
                if not job.get("preview"):
                    return self._send(404, {"error": "pas d'aperçu"})
                try:
                    return self._send(200, open(job["preview"], "rb").read(), "image/png")
                except OSError:
                    return self._send(404, {"error": "aperçu en cours d'écriture"})
            return self._send(200, public(job))
        q = {k: v[0] for k, v in parse_qs(query).items()}
        if path.startswith("/api/private/"):
            return self._private_get(path, q)
        if path == "/api/result":                 # un tirage ou une image de la pile
            found = on_image(q.get("name"), lambda fp: (os.path.basename(fp), open(fp, "rb").read()))
            if not found:                         # inconnue, ou jetée entre-temps
                return self._send(404, {"error": "fichier inconnu"})
            name, data = found
            extra = {"Content-Disposition": f'attachment; filename="{name}"'} if q.get("download") else None
            return self._send(200, data, "image/png", extra)
        if path == "/api/history":
            return self._send(200, history())
        if path == "/api/pile":
            return self._send(200, pile())
        if path == "/api/prompts":                # prompts enregistrés, le dernier utilisé d'abord
            try:
                saved = sorted(saved_prompts(), key=lambda p: -p["used"])
            except (OSError, ValueError) as e:
                return self._send(500, {"error": f"prompts enregistrés illisibles : {e}"})
            return self._send(200, {"saved": saved, "types": prompt_types()})
        if path == "/api/push/key":
            key = push_public_key()
            return self._send(200, {"key": key}) if key else self._send(503, {"error": "pywebpush non installé"})
        if path == "/api/input":                  # image d'entrée d'un tirage ou d'une image de la pile
            out, f = image_path(q.get("name")), q.get("file", "")
            fp = os.path.join(INPUTS, os.path.basename(out)[:-4], f) if out and INPUT_RE.fullmatch(f) else None
            if not fp or not os.path.isfile(fp):
                return self._send(404, {"error": "image d'entrée inconnue"})
            if q.get("thumb"):
                try:   # l'envoi reste hors du try : une connexion coupée n'est pas une miniature impossible
                    th = thumbnail(fp, os.path.join(THUMBS, f"{os.path.basename(out)[:-4]}__{f[:-4]}.jpg"))
                    data = open(th, "rb").read()
                except FileNotFoundError:         # image jetée ou supprimée entre-temps
                    return self._send(404, {"error": "image d'entrée inconnue"})
                except Exception as e:
                    return self._send(500, {"error": f"miniature impossible : {e}"})
                return self._send(200, data, "image/jpeg")
            extra = {"Content-Disposition": f'attachment; filename="{os.path.basename(out)[:-4]}_{f}"'} if q.get("download") else None
            try:
                data = open(fp, "rb").read()
            except FileNotFoundError:             # image jetée ou supprimée entre-temps
                return self._send(404, {"error": "image d'entrée inconnue"})
            return self._send(200, data, "image/png", extra)
        if path == "/api/thumb":
            try:       # l'envoi reste hors du try : une connexion coupée n'est pas une miniature impossible
                data = on_image(q.get("name"), lambda fp: open(thumbnail(fp), "rb").read())
            except Exception as e:
                return self._send(500, {"error": f"miniature impossible : {e}"})
            if data is None:                      # inconnue, ou jetée entre-temps
                return self._send(404, {"error": "fichier inconnu"})
            return self._send(200, data, "image/jpeg")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "nom d'hôte refusé"})
        sweep()
        refused = self._post_refused()
        if refused:
            return self._send(refused[0], {"error": refused[1]})
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        # sans code chargé, pas de connexion possible : la requête va à _allowed, qui refuse tout (401)
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
            self.send_header("Set-Cookie", access_cookie_header())
            self.end_headers()
            self.wfile.write(body)
            return
        if not self._allowed():
            return self._send(401, {"error": "code d'accès requis"})
        if path.startswith("/api/private/"):
            return self._private_post(path, raw)
        if path in ("/api/delete", "/api/keep", "/api/discard"):   # Supprimer un tirage ; Garder, Jeter
            try:
                name = json.loads(raw).get("name")
            except Exception:                     # pas du JSON, pas un objet, trop imbriqué
                name = None
            return self._send(*sort_image(path[len("/api/"):], name))
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
        m = re.match(r"^/api/prompts(?:/(delete|used))?$", path)
        if m:                                    # prompts enregistrés : créer ou modifier, supprimer, marquer utilisé
            try:
                body = json.loads(raw)
            except ValueError:
                body = None
            if not isinstance(body, dict):
                return self._send(400, {"error": "objet JSON attendu"})
            action = m.group(1) or "save"
            error = prompt_error(action, body)
            if error:
                return self._send(400, {"error": error})
            try:       # l'envoi reste hors du try : une connexion coupée n'est pas un enregistrement manqué
                reply = change_prompt(action, body)
            except (OSError, ValueError) as e:
                return self._send(500, {"error": f"prompts enregistrés non modifiés : {e}"})
            return self._send(*reply)
        if path == "/api/generate":
            try:
                req = json.loads(raw)
            except Exception as e:
                return self._send(400, {"error": f"JSON invalide : {e}"})
            error = request_error(req)
            if error:
                return self._send(400, {"error": error})
            if req.get("private") and not HAVE_CRYPTO:
                return self._send(503, {"error": "espace privé indisponible : bibliothèque cryptography non installée"})
            if req.get("private") and not self._secure():   # prompt et images d'entrée privés : jamais en clair
                return self._send(403, {"error": PRIVATE_HTTPS_ONLY})
            if req.get("private") and not self._private_session(touch=True):
                return self._send(403, {"error": "espace privé verrouillé : entrez-y pour lancer une génération privée"})
            # campagne ou variantes : le mode ne le dit plus (des variantes d'édition sont aussi un lot du mode edit)
            campaign = req.get("campaign") is not None
            reqs = expand_request(req)
            n = len(reqs)
            # identifiant d'un lot privé : aussi impossible à deviner que ses générations
            lot = {"id": secrets.token_hex(16) if req.get("private") is True else uuid.uuid4().hex[:12], "size": n,
                   "campaign": campaign} if n > 1 else None
            # variantes : mêmes images d'entrée et dimensions pour toutes, lues une fois ; campagne : une photo chacune
            inputs = [request_inputs(r) for r in reqs] if campaign else [request_inputs(reqs[0])] * n
            jobs = [new_job(r, inputs[k], lot and {**lot, "rank": k + 1}) for k, r in enumerate(reqs)]
            if lot:
                S.lots[lot["id"]] = {"jobs": jobs, "campaign": campaign}
            with S.turn:                         # générations d'un lot : à la suite dans la file, dans l'ordre
                for job in jobs:
                    S.jobs[job["id"]] = job
                    S.pending.append(job)
                S.turn.notify()
            return self._send(202, {"lot": lot, "jobs": [public(j) for j in jobs]} if lot else public(jobs[0]))
        m = re.match(r"^/api/lot/([\w-]+)/(cancel|first)$", path)
        if m:                                    # toutes les générations non terminées du lot, ou celles qui attendent
            lot = S.lots.get(m.group(1))
            if not lot or self._hidden(lot["jobs"][0], touch=True):
                return self._send(404, {"error": "lot inconnu"})
            if m.group(2) == "first":            # testé après _hidden : l'état d'un lot privé ne se devine pas
                return self._send(*moved_first(lot["jobs"], "plus rien n'attend dans ce lot"))
            active = [j for j in lot["jobs"] if j.get("status") in ACTIVE]
            for job in active:
                cancel_job(job)
            return self._send(200, {"cancelled": len(active)})
        m = re.match(r"^/api/job/([\w-]+)/(cancel|forget|first)$", path)
        if m:
            job = S.jobs.get(m.group(1))
            # l'annulation et le passage en tête sont des gestes dans l'espace (session prolongée) ; l'oubli, envoyé
            # seul par la page à la fin d'une génération, ne la prolonge pas
            if not job or self._hidden(job, touch=m.group(2) != "forget"):
                return self._send(404, {"error": "job inconnu"})
            if m.group(2) == "first":            # testé après _hidden : l'état d'une génération privée ne se devine pas
                return self._send(*moved_first([job], "génération plus en attente"))
            if m.group(2) == "forget" and not secret(job):
                return self._send(400, {"error": "seul un job privé peut être oublié"})
            if m.group(2) == "forget":            # privée finie (rangée, en échec ou annulée) : plus rien en mémoire
                forget_job(job)
                return self._send(200, {"ok": True})
            cancel_job(job)
            return self._send(200, public(job))
        self._send(404, {"error": "not found"})


def exclude_from_backup(path):
    """Exclut le dossier de travail de Time Machine (tmutil, sans droits administrateur) : une sauvegarde faite pendant
    une génération privée ne capte pas ses fichiers de passage. Un échec est noté sans bloquer."""
    try:
        r = subprocess.run(["tmutil", "addexclusion", path], capture_output=True, text=True, timeout=15)
        if r.returncode:
            print(f"[launch] exclusion de Time Machine impossible : {(r.stderr or r.stdout).strip()}", flush=True)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[launch] exclusion de Time Machine impossible : {e}", flush=True)


def setup_state(cfg, backend, model):
    """Fixe le moteur et le modèle (repli si l'un n'est pas installé) et charge la calibration ; sort si sd-cli manque."""
    S.cfg = cfg
    if not os.path.exists(DIFFUSION[model]) and model != "q4":
        print(f"[launch] modèle {model} absent (setup.py {SETUP_FLAGS[model]} pour l'installer), repli sur q4",
              flush=True)
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


def restrict_new_files():
    """Tout ce que le processus crée ensuite, et sd-cli avec lui (PNG privé en clair, qui porte le prompt ; vignettes ;
    copies d'images d'entrée ; tirages ; dossiers de travail), n'est lisible que par le compte qui le fait tourner
    (masque 0o077 : fichiers en 0o600, dossiers en 0o700 ; décision du 23/10/2026). Les fichiers déjà créés gardent
    leurs droits ; les dossiers du serveur créés avant sont fermés par close_folders. Appelée en tête de main() et de
    tools/calibrate.py ; sans effet sous Windows."""
    os.umask(0o077)


def close_folders():
    """Ferme aux autres comptes (0o700) les dossiers du serveur créés avant le masque de restrict_new_files (par
    setup.py ou un serveur d'avant) : ils ne peuvent plus y lister les noms des images ni voir apparaître les dossiers
    de travail privés (décision du 23/10/2026). Un dossier absent est sauté ; un dossier qui refuse (autre propriétaire,
    volume sans droits Unix) est noté sans bloquer le démarrage ; sans effet sous Windows."""
    refused = False
    for d in (P("outputs"), PILE, THUMBS, INPUTS, P("jobs"), P("logs")):
        try:
            os.chmod(d, 0o700)
        except FileNotFoundError:
            pass
        except OSError:
            refused = True
    if refused:                                  # sans chemin : logs/ ne cite pas les dossiers du Mac
        print("[launch] dossiers non fermés aux autres comptes", flush=True)


def main():
    restrict_new_files()
    close_folders()                              # avant toute sortie précoce : logs/ fermé même si le lancement échoue
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=cfg["ui_port"])
    ap.add_argument("--backend", choices=PLATFORM_BACKENDS, default=default_backend(cfg))
    ap.add_argument("--model", choices=list(DIFFUSION), default=cfg.get("model", "q4"),
                    help="q4 (Q4_K_M, par défaut), q8 (Q8_0, plus fidèle, setup.py --q8) ; uc-q4, uc-q8 : variante "
                         "communautaire (setup.py --uc)")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--enter", action="store_true",
                    help="ouvre l'interface déjà lancée sans taper le code (jeton à usage unique), sans serveur")
    ap.add_argument("--lan", action="store_true", default=bool(cfg.get("lan")),
                    help="accessible aussi depuis le Wi-Fi (téléphone), avec le code d'accès ; Mac maintenu éveillé")
    a = ap.parse_args()
    if a.enter:                                  # raccourci, interface déjà lancée : seulement la page d'entrée
        open_entry(a.port)
        return
    S.ui_port = a.port
    setup_state(cfg, a.backend, a.model)
    S.started = code_version()
    for d in ("outputs", "logs", "jobs"):
        os.makedirs(P(d), exist_ok=True)
    try:                                               # changement de code privé interrompu par un arrêt brutal
        finish_rekey()                                 # (rien n'est écrit au journal sur l'espace privé)
    except (OSError, ValueError):                      # ValueError : space.json illisible ; le serveur démarre quand même
        pass
    # restes d'un job privé interrompu par un arrêt brutal, d'une image privée à moitié rangée ou jetée, et d'un job
    # incognito d'avant son retrait (images en clair : porteur, 22/10/2026)
    for old in (glob.glob(P("jobs", "private_*")) + glob.glob(os.path.join(PRIVATE, "items", ".*"))
                + glob.glob(P("jobs", "incognito_*"))):
        shutil.rmtree(old, ignore_errors=True)
    try:                                               # fiche à moitié réécrite par Garder (sort_private)
        os.remove(os.path.join(PRIVATE, META_TMP))
    except FileNotFoundError:
        pass
    restore_hidden_images()                            # PNG caché d'un effacement coupé : l'image revient
    if sys.platform == "darwin":
        exclude_from_backup(P("jobs"))
    # tirages antérieurs à la conservation des entrées, et images de la pile dont les entrées n'ont pas pu être
    # gardées (to_pile) : reprises depuis leur dossier de travail tant qu'il existe
    for fp in glob.glob(P("outputs", "*.png")) + glob.glob(os.path.join(PILE, "*.png")):
        stem = os.path.basename(fp)[:-4]
        if not os.path.isdir(os.path.join(INPUTS, stem)):
            try:
                save_inputs(P("jobs", stem.rsplit("_", 1)[0]), fp)
            except OSError:
                pass
    for old in sorted(glob.glob(P("jobs", "*")))[:-20]:   # ne garde que les 20 derniers dossiers de travail
        shutil.rmtree(old, ignore_errors=True)
    setup_access()                                     # avec ou sans --lan : le Mac aussi demande le code
    threading.Thread(target=worker, daemon=True).start()
    if a.lan:
        name, ip = lan_address()
        ts = tailscale_hosts()
        S.lan_urls = [f"http://{h}:{a.port}/" for h in dict.fromkeys(x for x in (name, ip, *ts) if x)]
        S.lan_hosts = {urlsplit(u).netloc.lower() for u in S.lan_urls}
        dns = next((h for h in ts if h.endswith(".ts.net")), None)
        if dns:
            S.lan_hosts.add(dns)                    # nom HTTPS de « tailscale serve », admis même s'il est activé plus tard
            S.https_hosts.add(dns)
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
    else:                                       # le Mac aussi demande le code : où le lire, jamais le code lui-même
        print("[launch] code d'accès dans tools/access_code.txt", flush=True)
    if not a.no_browser:                         # par la page d'entrée : le Mac aussi demande le code
        threading.Timer(1.0, lambda: open_browser(a.port)).start()
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
