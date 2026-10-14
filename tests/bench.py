"""Banc de test du serveur, sans GPU : tools/launch.py servi sur un port libre, avec un faux moteur (fake_sdcli.py).

  venv/bin/python -m unittest discover -s tests -v

start() importe le serveur, repointe tous ses dossiers vers un dossier temporaire (rien n'est écrit dans le dépôt :
ni outputs/, ni jobs/, ni journal, ni calibration, ni clé de notification), y installe le faux sd-cli, puis sert
launch.H sur 127.0.0.1 avec son thread de calcul. Un seul serveur par processus : l'état du serveur (launch.S) est
global ; BenchCase attend avant chaque test que la file soit vide et oublie les générations précédentes.
"""
import atexit, base64, contextlib, glob, json, os, shutil, sys, tempfile, threading, time, unittest, warnings
import urllib.error, urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import estimate, launch   # noqa: E402

S = launch.S
ACCESS_CODE = "test-code"
LOG = []                                            # sorties du serveur (print et journal des requêtes), hors de l'écran
_server = None


def start():
    """Démarre le serveur du banc une fois par processus ; renvoie son adresse (http://127.0.0.1:<port>)."""
    global _server
    if _server:
        return f"http://127.0.0.1:{S.ui_port}"
    root = tempfile.mkdtemp(prefix="qwen-banc-")
    atexit.register(shutil.rmtree, root, True)
    launch.ROOT = root                              # P() lit ROOT à chaque appel ; les chemins figés à l'import suivent
    launch.CONFIG, launch.CALIB = launch.P("tools", "config.json"), launch.P("tools", "calibration.json")
    launch.THUMBS, launch.INPUTS = launch.P("outputs", ".thumbs"), launch.P("outputs", ".inputs")
    launch.PUSH_KEY, launch.PUSH_SUBS = launch.P("tools", "push_vapid.pem"), launch.P("tools", "push_subscriptions.json")
    launch.ACCESS_FILE = launch.P("tools", "access_code.txt")
    for d in ("tools", "outputs", "jobs", "logs", "models"):
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
    launch.H.log_message = lambda self, fmt, *a: LOG.append(fmt % a)
    # code d'accès actif, comme avec --lan : le client local passe, un autre appareil doit présenter le cookie
    S.access_code = ACCESS_CODE
    S.access_token = launch.access_token(ACCESS_CODE)
    _server = launch.Server(("127.0.0.1", 0), launch.H)
    S.ui_port = _server.server_address[1]
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
            f.write(f'@"{sys.executable}" "{fake}" %*\n')
        return
    exe = os.path.join(d, launch.EXE)
    with open(exe, "w") as f:
        f.write(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
    os.chmod(exe, 0o755)


def call(method, path, body=None, remote=False, cookie=True, headers=None):
    """Requête HTTP au serveur du banc : (code, réponse JSON ou octets). remote : venue d'un autre appareil (relayée par
    Tailscale), avec le cookie d'accès si cookie est vrai. Les POST portent Content-Type: application/json."""
    h = {"Content-Type": "application/json"} if method == "POST" else {}
    if remote:
        h["X-Forwarded-For"] = "192.0.2.10"
        if cookie:
            h["Cookie"] = f"{launch.ACCESS_COOKIE}={S.access_token}"
    h.update(headers or {})
    data = json.dumps(body if body is not None else {}).encode() if method == "POST" else None
    req = urllib.request.Request(f"http://127.0.0.1:{S.ui_port}{path}", data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code, raw, ctype = r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        code, raw, ctype = e.code, e.read(), e.headers.get("Content-Type", "")
    return code, json.loads(raw) if ctype.startswith("application/json") else raw


def gen_body(prompt="a red car", mode="t2i", **kw):
    """Corps de /api/generate tel que l'envoie l'interface (512×512, 4 étapes, sans aperçu)."""
    body = {"mode": mode, "prompt": prompt, "width": 512, "height": 512, "steps": 4, "cfg": 1, "seed": -1,
            "preview": False, "preview_interval": 5, "ref_images": [], "init_image": None, "mask_image": None,
            "strength": 1.0, "incognito": False}
    body.update(kw)
    return body


def generate(prompt="a red car", **kw):
    code, job = call("POST", "/api/generate", gen_body(prompt, **kw))
    assert code == 202, (code, job)
    return job


def job(jid):
    return call("GET", f"/api/job/{jid}")[1]


def wait_job(jid, until=("done", "failed", "cancelled"), timeout=30, check=None):
    """Attend qu'une génération atteigne un des statuts until (et que check(job) soit vrai) ; renvoie la génération."""
    end = time.time() + timeout
    while time.time() < end:
        j = job(jid)
        if j.get("status") in until and (check is None or check(j)):
            return j
        time.sleep(0.05)
    raise AssertionError(f"génération {jid} : toujours {j.get('status')} après {timeout} s")


def idle():
    """Thread de calcul au repos : file vide, aucune génération en cours, et dossiers de travail des générations annulées
    ou incognito déjà supprimés (worker() les supprime après avoir rendu S.current)."""
    jobs = list(S.jobs.values())
    return (S.current is None and S.q.empty() and not any(j.get("status") in ("queued", "running") for j in jobs)
            and not any(os.path.exists(j["dir"]) for j in jobs if j.get("status") == "cancelled" or j.get("incognito")))


def wait_idle(timeout=30):
    end = time.time() + timeout
    while not idle():
        if time.time() > end:
            raise AssertionError("le thread de calcul n'est pas revenu au repos")
        time.sleep(0.05)


def png_bytes(w=64, h=48):
    """Image PNG valide, en mémoire (pour les images d'entrée)."""
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def data_url(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def files(*pattern):
    """Fichiers du dossier temporaire qui répondent au motif (chemin relatif à la racine du banc)."""
    return sorted(glob.glob(launch.P(*pattern)))


def journal():
    try:
        with open(launch.P("outputs", "journal.jsonl"), encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []


@contextlib.contextmanager
def capture_push():
    """Intercepte les notifications Web Push sans réseau : un appareil abonné fictif et pywebpush.webpush remplacé.
    Donne la liste des messages envoyés (dictionnaires décodés) ; sent.wait(n) attend le n-ième."""
    try:
        import pywebpush  # noqa: F401
    except ImportError:
        raise unittest.SkipTest("pywebpush non installé : pas de notifications")
    sent = Sent()
    with open(launch.PUSH_SUBS, "w", encoding="utf-8") as f:
        json.dump([{"endpoint": "https://push.example.invalid/abonnement", "keys": {"p256dh": "x", "auth": "y"}}], f)
    try:
        with mock.patch("pywebpush.webpush", side_effect=lambda sub, data, **kw: sent.add(json.loads(data))):
            yield sent
    finally:
        os.remove(launch.PUSH_SUBS)


class Sent(list):
    def __init__(self):
        super().__init__()
        self.cond = threading.Condition()

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

    @classmethod
    def setUpClass(cls):
        start()
        # fichiers ouverts sans être refermés explicitement par le serveur (open(...).read()) : bruit sans effet
        warnings.simplefilter("ignore", ResourceWarning)

    def setUp(self):
        for j in list(S.jobs.values()):            # restes d'un test précédent interrompu par un échec
            if j.get("status") in ("queued", "running"):
                call("POST", f"/api/job/{j['id']}/cancel")
        wait_idle()
        S.jobs.clear()
        S.lots.clear()
        for d in ("outputs", "jobs"):
            shutil.rmtree(launch.P(d))
            os.makedirs(launch.P(d))
