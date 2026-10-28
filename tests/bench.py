"""Banc de test du serveur, sans GPU : tools/launch.py servi sur un port libre, avec un faux moteur (fake_sdcli.py).

  venv/bin/python -m unittest discover -s tests -v

start() importe le serveur, repointe tous ses dossiers vers un dossier temporaire (rien n'est écrit dans le dépôt :
ni outputs/, ni jobs/, ni journal, ni calibration, ni clé de notification, ni espace privé), y installe le faux sd-cli,
puis sert launch.H sur 127.0.0.1 avec son thread de calcul. Un seul serveur par processus : l'état du serveur (launch.S)
est global ; BenchCase attend avant chaque test que la file soit vide et oublie les générations précédentes, l'espace
privé et ses sessions.

Outils : call() (trois origines : le Mac, par défaut ; remote=True, HTTPS relayé par « tailscale serve »,
HTTPS_HOST ; wifi=True, http:// direct d'un autre appareil, WIFI_HOST), call_full() (avec les en-têtes),
generate(), wait_job() (pour un statut final, attend aussi que worker() en ait fini : settled), wait_until(cond),
wait_idle() (tout le Mac au repos), capture_push() (notifications interceptées ; sent.decided complet après
wait_idle()), release(nom), journal(), files(), LOG (sorties du serveur). Faux moteur (tests/fake_sdcli.py) : FAIL,
SLOW[=s], FAILSEED=<n>, HOLD[=nom][@k] dans le prompt (HOLD garde une génération en cours sans dépendre du temps ;
@k : une fois l'étape k annoncée, aperçus d'avant vus).
"""
import atexit, base64, contextlib, glob, json, os, shutil, signal, sys, tempfile, threading, time, unittest, warnings
import urllib.error, urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import estimate, launch   # noqa: E402

S = launch.S
ACCESS_CODE = "test-code"
HTTPS_HOST = "qwen-banc.example.ts.net"             # nom fictif de « tailscale serve » (HTTPS, relayé depuis 127.0.0.1)
WIFI_HOST = "mac-du-banc.local"                     # nom fictif du Mac sur le Wi-Fi (http:// direct)
LOG = []                                            # sorties du serveur (print et journal des requêtes), hors de l'écran
SHOWN = 200                                         # caractères au plus d'une réponse recopiée dans un message d'échec
_server = None


def short(value, limit=SHOWN):
    """Texte d'une valeur pour un message d'échec, coupé à limit caractères (une réponse peut être une image)."""
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= limit else text[:limit] + f"… [{len(text)} caractères]"


class Raw(bytes):
    """Réponse non JSON (image, page) : se montre en quelques octets dans un message d'échec, jamais en entier."""
    def __repr__(self):
        return f"<{len(self)} octets : {bytes(self[:40])!r}…>" if len(self) > 40 else bytes.__repr__(self)
    __str__ = __repr__


def _cleanup_on_sigterm(root):
    """Un banc tué (SIGTERM : fin de session, kill) supprime aussi son dossier temporaire, comme à la sortie normale."""
    if threading.current_thread() is not threading.main_thread():
        return                                      # signal.signal n'est permis que dans le thread principal
    previous = signal.getsignal(signal.SIGTERM)

    def on_term(signum, frame):
        shutil.rmtree(root, True)
        signal.signal(signal.SIGTERM, previous if callable(previous) else signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)        # puis la fin habituelle (code de sortie d'un processus tué)
    signal.signal(signal.SIGTERM, on_term)


def start():
    """Démarre le serveur du banc une fois par processus ; renvoie son adresse (http://127.0.0.1:<port>)."""
    global _server
    if _server:
        return f"http://127.0.0.1:{S.ui_port}"
    root = tempfile.mkdtemp(prefix="qwen-banc-")
    atexit.register(shutil.rmtree, root, True)
    _cleanup_on_sigterm(root)
    launch.ROOT = root                              # P() lit ROOT à chaque appel ; les chemins figés à l'import suivent
    launch.CONFIG, launch.CALIB = launch.P("tools", "config.json"), launch.P("tools", "calibration.json")
    launch.CONFIG_LOCAL = launch.P("tools", "config.local.json")
    launch.THUMBS, launch.INPUTS = launch.P("outputs", ".thumbs"), launch.P("outputs", ".inputs")
    launch.PILE = launch.P("outputs", ".pile")
    launch.PUSH_KEY, launch.PUSH_SUBS = launch.P("tools", "push_vapid.pem"), launch.P("tools", "push_subscriptions.json")
    launch.ACCESS_FILE = launch.P("tools", "access_code.txt")
    launch.ENTRY_TOKEN, launch.ENTRY_PAGE = launch.P("tools", "entry_token"), launch.P("tools", "entry.html")
    launch.PROMPTS_FILE = launch.P("tools", "saved_prompts.json")
    launch.PRIVATE = launch.P("private")
    launch.SCRYPT_N = 2 ** 10                       # dérivation du code privé rapide au banc (2**18 en vrai)
    # launch.PROMPT_TYPES_FILE reste le fichier du dépôt : le serveur le lit sans jamais l'écrire
    for d in ("tools", "outputs", "jobs", "logs", "models", "hold"):
        os.makedirs(launch.P(d))
    for table in (launch.MODELS, launch.DIFFUSION):   # modèles en fichiers vides : /api/status dit le moteur prêt
        for k, path in table.items():
            table[k] = launch.P("models", os.path.basename(path))
            open(table[k], "w").close()
    ui = os.path.join(os.path.dirname(HERE), "tools", "ui")   # l'interface du dépôt, relue à chaque requête
    try:
        os.symlink(ui, launch.P("tools", "ui"))
    except OSError:                                 # Windows sans droit de créer un lien : copie
        shutil.copytree(ui, launch.P("tools", "ui"))
    S.backend, S.model, S.engine = launch.PLATFORM_BACKENDS[0], "q4", "master-959-0000000"
    S.cfg = {"cfg_scale": 1.0, "extra_args": []}
    S.store = estimate.Store(launch.CALIB)
    install_fake_engine()
    launch.print = lambda *a, **kw: LOG.append(" ".join(str(x) for x in a))
    launch.H.log_message = lambda self, fmt, *a: None if launch.quiet_request(fmt % a) else LOG.append(fmt % a)
    # code d'accès, que main() pose toujours : tout appareil, le Mac compris, présente le cookie (call, cookie=True)
    S.access_code = ACCESS_CODE
    S.access_token = launch.access_token(ACCESS_CODE)
    _server = launch.Server(("127.0.0.1", 0), launch.H)
    S.ui_port = _server.server_address[1]
    S.lan_hosts = {f"{WIFI_HOST}:{S.ui_port}", HTTPS_HOST}   # comme main() avec --lan et Tailscale
    S.https_hosts = {HTTPS_HOST}
    threading.Thread(target=_server.serve_forever, daemon=True).start()
    threading.Thread(target=launch.worker, daemon=True).start()
    atexit.register(_server.shutdown)
    return f"http://127.0.0.1:{S.ui_port}"


def install_fake_engine():
    """Place le faux moteur là où build_cmd cherche sd-cli : sdcpp/<moteur>/sd-cli (sd-cli.cmd sous Windows)."""
    d = launch.P("sdcpp", S.backend)
    os.makedirs(d)
    fake = os.path.join(HERE, "fake_sdcli.py")
    if os.name == "nt":                             # non vérifié sous Windows : un .exe ne peut pas être un script
        launch.EXE = "sd-cli.cmd"
        with open(os.path.join(d, launch.EXE), "w") as f:
            f.write(f'@set "QWEN_FAKE_HOLD={hold_dir()}"\n@"{sys.executable}" "{fake}" %*\n')
        return
    exe = os.path.join(d, launch.EXE)
    with open(exe, "w") as f:
        f.write(f'#!/bin/sh\nQWEN_FAKE_HOLD="{hold_dir()}" exec "{sys.executable}" "{fake}" "$@"\n')
    os.chmod(exe, 0o755)


def hold_dir():
    """Dossier des libérations du faux moteur (HOLD, voir fake_sdcli.py), dans le dossier temporaire du banc."""
    return launch.P("hold")


def release(name="hold"):
    """Libère les générations dont le prompt porte HOLD=<name> (HOLD seul : « hold »), jusqu'au test suivant."""
    open(os.path.join(hold_dir(), name), "w").close()


def call(method, path, body=None, remote=False, cookie=True, headers=None, private=None, wifi=False):
    """Requête HTTP au serveur du banc : (code, réponse JSON ou octets). Trois origines : le Mac lui-même (par défaut) ;
    remote, un autre appareil par l'adresse HTTPS de Tailscale (relayée par « tailscale serve » depuis 127.0.0.1) ;
    wifi, un autre appareil en http:// direct sur le Wi-Fi (adresse source qui n'est pas celle du Mac). Toutes portent
    le cookie d'accès si cookie est vrai, le Mac compris ; private : valeur du cookie de session de l'espace privé.
    Les POST portent Content-Type: application/json."""
    return call_full(method, path, body, remote, cookie, headers, private, wifi)[:2]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Une redirection est rendue telle quelle (code 3xx, Location), pas suivie."""
    def redirect_request(self, *args, **kwargs):
        return None


def call_full(method, path, body=None, remote=False, cookie=True, headers=None, private=None, wifi=False, follow=True):
    """Comme call(), avec en plus les en-têtes de la réponse : (code, réponse, en-têtes). follow=False : une redirection
    est rendue telle quelle (303 et Location de /entrer), pas suivie."""
    h = {"Content-Type": "application/json"} if method == "POST" else {}
    cookies = []
    if remote:
        h["Host"], h["X-Forwarded-For"] = HTTPS_HOST, "192.0.2.10"
    if wifi:
        h["Host"] = f"{WIFI_HOST}:{S.ui_port}"
    if cookie:
        cookies.append(f"{launch.ACCESS_COOKIE}={S.access_token}")
    if private:
        cookies.append(f"{launch.PRIVATE_COOKIE}={private}")
    if cookies:
        h["Cookie"] = "; ".join(cookies)
    h.update(headers or {})
    data = json.dumps(body if body is not None else {}).encode() if method == "POST" else None
    req = urllib.request.Request(f"http://127.0.0.1:{S.ui_port}{path}", data=data, method=method, headers=h)
    # un appareil du Wi-Fi arrive d'une autre adresse que 127.0.0.1 : le serveur ne voit plus d'adresse locale
    with mock.patch.object(launch, "LOCAL_CLIENTS", ()) if wifi else contextlib.nullcontext():
        try:
            opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
            with opener.open(req, timeout=30) as r:
                code, raw, hdrs = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            code, raw, hdrs = e.code, e.read(), e.headers
    return code, json.loads(raw) if hdrs.get("Content-Type", "").startswith("application/json") else Raw(raw), hdrs


def cookie_of(headers):
    """Session de l'espace privé posée par une réponse (Set-Cookie), ou None."""
    for v in headers.get_all("Set-Cookie") or []:
        name, _, rest = v.partition("=")
        if name == launch.PRIVATE_COOKIE and "Max-Age=0" not in rest:
            return rest.split(";")[0]
    return None


def create_private(code, remote=False):
    """Crée l'espace privé ; renvoie la session ouverte pour ce client."""
    status, reply, headers = call_full("POST", "/api/private/create", {"code": code}, remote=remote)
    assert status == 200, short((status, reply))
    return cookie_of(headers)


def unlock_private(code, remote=False):
    status, reply, headers = call_full("POST", "/api/private/unlock", {"code": code}, remote=remote)
    assert status == 200, short((status, reply))
    return cookie_of(headers)


def private_status(session=None, remote=False, wifi=False):
    """État de l'espace privé vu par un client : {available, exists, unlocked, secure, local}."""
    return call("GET", "/api/status", remote=remote, private=session, wifi=wifi)[1]["private"]


def private_entries():
    """Fichiers et dossiers de private/ (dossier temporaire du banc) : deux listes de chemins relatifs à private/."""
    root, files, dirs = launch.P("private"), [], []
    for here, subdirs, names in os.walk(root):
        dirs += [os.path.relpath(os.path.join(here, d), root) for d in subdirs]
        files += [os.path.relpath(os.path.join(here, n), root) for n in names]
    return files, (["."] + dirs if os.path.isdir(root) else [])


def assert_private_owner_only(test):
    """Contrôle à la fin d'un test de l'espace privé : tout fichier de private/ (restes et fichiers temporaires compris)
    est lisible par son seul propriétaire (0o600), tout dossier en 0o700. Renvoie le nombre de fichiers examinés.
    Sans objet sous Windows (droits POSIX)."""
    if os.name != "posix":
        return 0
    files, dirs = private_entries()
    root = launch.P("private")
    for rel, mode in [(f, 0o600) for f in files] + [(d, 0o700) for d in dirs]:
        test.assertEqual(oct(os.stat(os.path.join(root, rel)).st_mode & 0o777), oct(mode), f"private/{rel}")
    return len(files)


def sealed_label(rel):
    """Étiquette de seal() d'un fichier de private/ (relatif) : « <id>/<rôle> » pour une image (dans items/ ou
    .rekey/items/, dossier caché .<id> compris), « prompts » pour les prompts (et leur .tmp) ; None si non scellé."""
    parts = rel.split(os.sep)
    if parts[0] == launch.REKEY:
        parts = parts[1:]
    if len(parts) == 3 and parts[0] == "items":
        return f"{parts[1].lstrip('.')}/{parts[2]}"
    if parts in (["prompts"], ["prompts.tmp"]):
        return "prompts"
    return None


def assert_old_key_opens_nothing(test, old_key, new_key=None):
    """Après un changement de code : aucun fichier scellé de private/ (restes .tmp et .rekey/ compris) ne s'ouvre avec
    old_key, la clé privée d'avant ; chacun s'ouvre avec new_key si elle est donnée (contrôle que l'étiquette est la
    bonne : avec une mauvaise, unseal échouerait pour toute clé). Renvoie le nombre de fichiers scellés examinés."""
    from cryptography.exceptions import InvalidTag
    root, n = launch.P("private"), 0
    for rel in private_entries()[0]:
        label = sealed_label(rel)
        if label is None:
            continue
        n += 1
        with open(os.path.join(root, rel), "rb") as f:
            blob = f.read()
        with test.assertRaises((InvalidTag, ValueError), msg=f"private/{rel} s'ouvre avec l'ancienne clé"):
            launch.unseal(blob, old_key, label)
        if new_key is not None:
            launch.unseal(blob, new_key, label)
    return n


class PrivateFilesCheck:
    """À mettre avant BenchCase dans les tests de l'espace privé : assert_private_owner_only() à la fin de chaque test,
    et au moins un fichier examiné sur toute la classe (sinon le contrôle ne vérifiait rien)."""
    checked = 0

    def tearDown(self):
        type(self).checked += assert_private_owner_only(self)
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if os.name == "posix" and not cls.checked:
            raise AssertionError(f"{cls.__name__} : aucun fichier de private/ examiné à la fin des tests")


def gen_body(prompt="a red car", mode="t2i", **kw):
    """Corps de /api/generate tel que l'envoie l'interface (512×512, 4 étapes, sans aperçu)."""
    body = {"mode": mode, "prompt": prompt, "width": 512, "height": 512, "steps": 4, "cfg": 1, "seed": -1,
            "preview": False, "preview_interval": 5, "ref_images": [], "init_image": None, "mask_image": None,
            "strength": 1.0}
    body.update(kw)
    return body


def generate(prompt="a red car", **kw):
    code, job = call("POST", "/api/generate", gen_body(prompt, **kw))
    assert code == 202, short((code, job))
    return job


def job(jid, private=None):
    """Suivi d'une génération ; private : session de l'espace privé, exigée pour une génération privée. Échoue tout de
    suite, avec le code et la réponse, si le suivi répond autre chose que 200 (un refus attendu se teste par call())."""
    code, reply = call("GET", f"/api/job/{jid}", private=private)
    if code != 200:
        raise AssertionError(f"génération {jid} : suivi refusé ({code}) : {short(reply)}")
    return reply


FINAL = ("done", "failed", "cancelled")


def settled(jid):
    """Vrai quand le thread de calcul en a fini avec la génération jid : elle n'est plus en cours (worker() rend
    S.current en dernier : fichiers rangés, ligne du journal écrite, notification décidée) et, annulée ou privée,
    son dossier de travail est supprimé. Une génération annulée encore en file (derrière une autre) compte comme
    finie : worker() ne la jettera qu'à son tour."""
    j = S.jobs.get(jid)
    if j is None or any(p is j for p in S.pending):
        return True
    if S.current == jid:
        return False
    return not ((j.get("status") == "cancelled" or j.get("private")) and os.path.exists(j["dir"]))


def wait_job(jid, until=FINAL, timeout=30, check=None, private=None, settle=True):
    """Attend qu'une génération atteigne un des statuts until (et que check(job) soit vrai) ; renvoie la génération.
    Pour un statut final, attend aussi que le thread de calcul en ait fini avec elle (settled : « done » est posé avant
    la ligne du journal, « cancelled » avant l'arrêt du moteur), sauf settle=False. private : session de l'espace
    privé, pour suivre une génération privée. Échoue tout de suite, avec le code et la réponse, si le suivi répond
    autre chose que 200 (génération inconnue, refus) : attendre n'y changerait rien."""
    end = time.time() + timeout
    while time.time() < end:
        j = job(jid, private)
        if j.get("status") in until and (check is None or check(j)):
            if settle and j.get("status") in FINAL:
                wait_until(lambda: settled(jid), max(end - time.time(), 1), f"génération {jid} rangée par worker()")
            return j
        time.sleep(0.05)
    raise AssertionError(f"génération {jid} : toujours {j.get('status')} après {timeout} s")


def wait_until(cond, timeout=10, what="la condition"):
    """Attend que cond() soit vraie (interrogée toutes les 20 ms) ; échoue après timeout secondes. Un test se
    synchronise ainsi sur ce qu'il observe, jamais sur un time.sleep au jugé."""
    end = time.time() + timeout
    while not cond():
        if time.time() > end:
            raise AssertionError(f"{what} : toujours fausse après {timeout} s")
        time.sleep(0.02)


def idle():
    """Thread de calcul au repos : file vide, aucune génération en cours (worker() ne rend S.current qu'après avoir
    rangé les fichiers et décidé la notification d'un lot), et dossiers de travail des générations annulées ou
    privées déjà supprimés."""
    jobs = list(S.jobs.values())
    return (S.current is None and not S.pending and not any(j.get("status") in ("queued", "running") for j in jobs)
            and not any(os.path.exists(j["dir"]) for j in jobs if j.get("status") == "cancelled" or j.get("private")))


def wait_idle(timeout=30):
    end = time.time() + timeout
    while not idle():
        if time.time() > end:
            raise AssertionError("le thread de calcul n'est pas revenu au repos")
        time.sleep(0.05)


def png_bytes(w=64, h=48, fmt="PNG"):
    """Image valide, en mémoire (pour les images d'entrée) : PNG, ou un autre format de Pillow (fmt="WEBP")."""
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, fmt)
    return buf.getvalue()


def data_url(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def all_files():
    """Tous les fichiers du dossier du banc (sauf le lien vers l'interface du dépôt), triés."""
    root = launch.ROOT
    return sorted(fp for fp in glob.glob(os.path.join(root, "**", "*"), recursive=True)
                  if os.path.isfile(fp) and not fp.startswith(os.path.join(root, "tools", "ui")))


def files(*pattern):
    """Fichiers du dossier temporaire qui répondent au motif (chemin relatif à la racine du banc)."""
    return sorted(glob.glob(launch.P(*pattern)))


def journal():
    """Lignes du journal des images, lues sous JOURNAL_LOCK : une génération passe « done » dans le même bloc que sa
    ligne (to_pile), qui est donc écrite quand le suivi le dit."""
    try:
        with launch.JOURNAL_LOCK, open(launch.P("outputs", "journal.jsonl"), encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []


@contextlib.contextmanager
def capture_push():
    """Intercepte les notifications Web Push sans réseau : un appareil abonné fictif et pywebpush.webpush remplacé.
    Donne la liste des messages envoyés (dictionnaires décodés) ; sent.wait(n) attend le n-ième. sent.decided reçoit
    chaque notification au moment où le serveur décide de l'envoyer (avant le thread d'envoi) : après wait_idle(),
    elle est complète, ce qui permet d'affirmer qu'aucune autre ne partira."""
    try:
        import pywebpush  # noqa: F401
    except ImportError:
        raise unittest.SkipTest("pywebpush non installé : pas de notifications")
    sent = Sent()
    with open(launch.PUSH_SUBS, "w", encoding="utf-8") as f:
        json.dump([{"endpoint": "https://push.example.invalid/abonnement", "keys": {"p256dh": "x", "auth": "y"}}], f)
    real = launch.push_notify

    def decide(payload):
        sent.decided.append(dict(payload))
        real(payload)
    try:
        with mock.patch("pywebpush.webpush", side_effect=lambda sub, data, **kw: sent.add(json.loads(data))), \
                mock.patch.object(launch, "push_notify", decide):
            yield sent
    finally:
        os.remove(launch.PUSH_SUBS)


class Sent(list):
    def __init__(self):
        super().__init__()
        self.cond = threading.Condition()
        self.decided = []

    def add(self, msg):
        with self.cond:
            self.append(msg)
            self.cond.notify_all()

    def wait(self, n=1, timeout=10):
        with self.cond:
            if not self.cond.wait_for(lambda: len(self) >= n, timeout):
                raise AssertionError(f"{len(self)} notification(s) reçue(s), {n} attendue(s)")
        return self


class BenchCase(unittest.TestCase):
    """Test sur le serveur du banc : au début de chaque test, file vide, générations précédentes oubliées, outputs/ et
    jobs/ vidés."""

    def _formatMessage(self, msg, standardMsg):
        # le message passé par un test (msg=reply…) peut porter une réponse entière : coupé comme les réponses (Raw) ;
        # _formatMessage est la méthode d'unittest qui assemble ce message (interne, mais stable depuis Python 3.1)
        return super()._formatMessage(None if msg is None else short(msg), standardMsg)

    @classmethod
    def setUpClass(cls):
        start()
        # fichiers ouverts sans être refermés explicitement par le serveur (open(...).read()) : bruit sans effet
        warnings.simplefilter("ignore", ResourceWarning)

    def setUp(self):
        release("ALL")                              # générations retenues (HOLD) par un test précédent
        for j in list(S.jobs.values()):            # restes d'un test précédent interrompu par un échec
            if j.get("status") in ("queued", "running"):
                call("POST", f"/api/job/{j['id']}/cancel")
        wait_idle()
        shutil.rmtree(hold_dir())                   # chaque test part sans libération
        os.makedirs(hold_dir())
        S.jobs.clear()
        S.lots.clear()
        S.private_sessions.clear()
        for d in ("outputs", "jobs"):
            shutil.rmtree(launch.P(d))
            os.makedirs(launch.P(d))
        shutil.rmtree(launch.P("private"), ignore_errors=True)
