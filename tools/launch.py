r"""Lanceur unique : interface web locale + moteur stable-diffusion.cpp (sd-cli lancé à chaque génération).

  venv\Scripts\python.exe tools\launch.py [--port 7860] [--backend vulkan|cpu] [--no-browser]

- L'interface écoute sur 127.0.0.1:<port> et sert tools/ui/index.html.
- Chaque génération lance sd-cli.exe (rechargement quasi instantané grâce à --mmap et au cache disque de Windows),
  lit sa progression (étape k/N, secondes par étape), expose des aperçus intermédiaires optionnels et enregistre
  le PNG final dans outputs/.
- API : POST /api/generate, GET /api/job/<id>, GET /api/job/<id>/preview, POST /api/job/<id>/cancel,
        GET /api/result?name=<png>, GET /api/status.
Aucun droit administrateur, aucune modification système : tout reste dans ce dossier.
"""
import argparse, base64, datetime, glob, json, os, queue, re, shutil, subprocess, sys, threading, time, uuid, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
CONFIG = P("tools", "config.json")
MODELS = {
    "diffusion": P("models", "diffusion_models", "qwen-image-2.1-Q4_K_M.gguf"),
    "vae": P("models", "vae", "qwen_image_2.1_vae_bf16.safetensors"),
    "llm": P("models", "text_encoders", "qwen3vl_8b_int8_convrot_embfix.safetensors"),
}
PROGRESS_RE = re.compile(r"(\d+)/(\d+)\s*-\s*([\d.]+)s/it")


def load_config():
    cfg = {"backend": "vulkan", "ui_port": 7860, "cfg_scale": 1.0, "extra_args": []}
    if os.path.exists(CONFIG):
        cfg.update(json.load(open(CONFIG, encoding="utf-8")))
    return cfg


class State:
    backend = "vulkan"
    cfg = {}
    ui_port = 7860
    jobs = {}
    q = queue.Queue()
    current = None


S = State()


def write_data_url(data_url, path):
    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    return path


def build_cmd(job):
    d = job["dir"]
    r = job["req"]
    be = {"vulkan": "diffusion=vulkan0,vae=vulkan0,te=cpu", "cpu": "cpu"}[S.backend]
    cmd = [P("sdcpp", S.backend, "sd-cli.exe"),
           "--diffusion-model", MODELS["diffusion"], "--vae", MODELS["vae"], "--llm", MODELS["llm"],
           "--backend", be, "--offload-to-cpu", "--mmap",
           "-p", r["prompt"], "-W", str(r["width"]), "-H", str(r["height"]),
           "--steps", str(r["steps"]), "--cfg-scale", str(r.get("cfg", S.cfg.get("cfg_scale", 1.0))),
           "--sampling-method", "euler", "-s", str(r.get("seed", -1)), "-o", job["out"]]
    if r.get("negative_prompt"):
        cmd += ["-n", r["negative_prompt"]]
    for i, ref in enumerate(r.get("ref_images") or []):
        cmd += ["-r", write_data_url(ref, os.path.join(d, f"ref_{i+1}.png"))]
    if r.get("init_image"):
        cmd += ["-i", write_data_url(r["init_image"], os.path.join(d, "init.png")), "--strength", str(r.get("strength", 1.0))]
    if r.get("mask_image"):
        cmd += ["--mask", write_data_url(r["mask_image"], os.path.join(d, "mask.png"))]
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
    logf = open(os.path.join(job["dir"], "sd-cli.log"), "wb")
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
                job["step"], job["total"], job["sec_per_it"] = int(pm.group(1)), int(pm.group(2)), float(pm.group(3))
                job["phase"] = "génération"
                if job.get("preview_interval"):
                    latest_preview(job)
            elif "loading llm" in text or "loading diffusion model" in text:
                job["phase"] = "chargement du modèle"
            elif "computing condition graph" in text or "Version:" in text:
                job["phase"] = "encodage du prompt" + (" et des images" if job["req"].get("ref_images") else "")
            elif "get_learned_condition completed" in text:
                job["phase"] = "génération"
                job["encode_seconds"] = round(time.time() - job["started"], 1)
            elif "sampling completed" in text:
                job["phase"] = "décodage VAE"
            elif "[ERROR" in text or "GGML_ASSERT" in text:
                job["error_lines"] = (job.get("error_lines") or []) + [text]
    rc = proc.wait()
    logf.close()
    job["finished"] = time.time()
    job["seconds"] = round(job["finished"] - job["started"], 1)
    if job.get("status") == "cancelled":
        return
    if rc == 0 and os.path.exists(job["out"]):
        job["status"] = "done"
        job["phase"] = "terminé"
        try:
            from PIL import Image
            with Image.open(job["out"]) as im:
                job["dims"] = list(im.size)
        except Exception:
            job["dims"] = [job["req"]["width"], job["req"]["height"]]
        job["size"] = os.path.getsize(job["out"])
        meta = {"mode": job["req"].get("mode"), "prompt": job["req"]["prompt"], "width": job["req"]["width"], "height": job["req"]["height"],
                "steps": job["req"]["steps"], "seed": job["req"].get("seed"), "seconds": job["seconds"], "encode_seconds": job.get("encode_seconds"),
                "sec_per_it": job.get("sec_per_it"), "file": job["out"], "size": job["size"], "backend": S.backend}
        with open(P("outputs", "journal.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        print(f"[job] PNG enregistré : {job['out']} ({job['size']} octets, {job['seconds']} s)", flush=True)
    else:
        job["status"] = "failed"
        job["error"] = "sd-cli code " + str(rc) + " — " + " | ".join((job.get("error_lines") or tail)[-4:])
        print("[job] échec : " + job["error"], flush=True)


def worker():
    while True:
        job = S.q.get()
        if job.get("status") == "cancelled":
            continue
        S.current = job["id"]
        try:
            run_job(job)
        finally:
            S.current = None
            job.pop("proc", None)


def public(job):
    keys = ("id", "status", "phase", "step", "total", "sec_per_it", "started", "finished", "seconds", "encode_seconds",
            "preview_version", "preview_interval", "size", "dims", "error", "queue_position")
    d = {k: job.get(k) for k in keys}
    d["elapsed"] = round(time.time() - job["started"], 1) if job.get("started") and not job.get("finished") else job.get("seconds")
    d["path"] = job["out"] if job.get("status") == "done" else None
    d["name"] = os.path.basename(job["out"])
    return d


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        msg = fmt % args
        if "/api/status" in msg or "/api/job/" in msg:
            return
        sys.stderr.write("[ui] " + msg + "\n")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path in ("/", "/index.html"):
            return self._send(200, open(P("tools", "ui", "index.html"), "rb").read(), "text/html; charset=utf-8")
        if path == "/api/status":
            missing = [k for k, v in MODELS.items() if not os.path.exists(v)]
            last = max(S.jobs.values(), key=lambda j: j["created"], default=None)
            return self._send(200, {"sd_ready": not missing, "backend": S.backend, "busy": S.current is not None,
                                    "detail": ("fichiers manquants : " + ", ".join(missing)) if missing else "prêt",
                                    "model": "qwen-image-2.1-Q4_K_M.gguf", "queued": S.q.qsize(),
                                    "current_job": S.current, "last_job": public(last) if last else None})
        m = re.match(r"^/api/job/([\w-]+)(/preview)?$", path)
        if m:
            job = S.jobs.get(m.group(1))
            if not job:
                return self._send(404, {"error": "job inconnu"})
            if m.group(2):
                if not job.get("preview"):
                    return self._send(404, {"error": "pas d'aperçu"})
                try:
                    return self._send(200, open(job["preview"], "rb").read(), "image/png")
                except OSError:
                    return self._send(404, {"error": "aperçu en cours d'écriture"})
            return self._send(200, public(job))
        if path == "/api/result":
            name = os.path.basename(query.replace("name=", "").replace("%20", " "))
            fp = P("outputs", name)
            if os.path.isfile(fp):
                return self._send(200, open(fp, "rb").read(), "image/png")
            return self._send(404, {"error": "fichier inconnu"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if path == "/api/generate":
            try:
                req = json.loads(raw)
            except Exception as e:
                return self._send(400, {"error": f"JSON invalide : {e}"})
            if not str(req.get("prompt", "")).strip():
                return self._send(400, {"error": "prompt vide"})
            jid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            mode = re.sub(r"[^a-z0-9]", "", str(req.get("mode", "img"))) or "img"
            d = P("jobs", jid)
            os.makedirs(d, exist_ok=True)
            job = {"id": jid, "req": req, "dir": d, "out": P("outputs", f"{jid}_{mode}.png"), "status": "queued", "created": time.time(),
                   "queue_position": S.q.qsize() + (1 if S.current else 0)}
            S.jobs[jid] = job
            S.q.put(job)
            return self._send(202, public(job))
        m = re.match(r"^/api/job/([\w-]+)/cancel$", path)
        if m:
            job = S.jobs.get(m.group(1))
            if not job:
                return self._send(404, {"error": "job inconnu"})
            job["status"] = "cancelled"
            job["phase"] = "annulé"
            proc = job.get("proc")
            if proc and proc.poll() is None:
                proc.kill()
            return self._send(200, public(job))
        self._send(404, {"error": "not found"})


def main():
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=cfg["ui_port"])
    ap.add_argument("--backend", choices=["vulkan", "cpu"], default=cfg["backend"])
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    S.cfg = cfg
    S.backend = a.backend
    S.ui_port = a.port
    for d in ("outputs", "logs", "jobs"):
        os.makedirs(P(d), exist_ok=True)
    for old in sorted(glob.glob(P("jobs", "*")))[:-20]:   # ne garde que les 20 derniers dossiers de travail
        shutil.rmtree(old, ignore_errors=True)
    exe = P("sdcpp", a.backend, "sd-cli.exe")
    if not os.path.exists(exe):
        sys.exit(f"binaire introuvable : {exe}")
    threading.Thread(target=worker, daemon=True).start()
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{a.port}/"
    print(f"[launch] backend {a.backend} — interface : {url}  (Ctrl+C pour arrêter)", flush=True)
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
