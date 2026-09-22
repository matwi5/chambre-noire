r"""Tests de bout en bout via l'API du lanceur (127.0.0.1:7860, tools/launch.py → sd-cli).

  venv\Scripts\python.exe tests\run_tests.py [--base http://127.0.0.1:7860] [--only t2i|edit|mask|annot] [--steps 12] [--cfg 1]

Chaque test enregistre un PNG dans outputs/ et affiche chemin, dimensions, taille et durée.
- t2i   : texte vers image 512x512
- edit  : édition image + texte (référence = résultat t2i)
- mask  : édition guidée par masque (masque circulaire généré par tools/make_mask.py = équivalent d'un dessin)
- annot : édition guidée par annotation (cercle rouge tracé sur l'image, méthode « circle-guided » officielle)
"""
import argparse, base64, json, os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)


def data_url(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=7200) as r:
        return json.loads(r.read().decode())


def run(base, name, body):
    print(f"\n=== {name} ===")
    print("prompt :", body["prompt"])
    t0 = time.time()
    job = call(base, "/api/generate", body)
    while job["status"] in ("queued", "running"):
        time.sleep(2)
        job = call(base, f"/api/job/{job['id']}")
        step = f"étape {job['step']}/{job['total']} ({job['sec_per_it']} s/étape)" if job.get("step") else ""
        print(f"\r  {job['status']} · {job.get('phase') or ''} {step} … {time.time()-t0:6.1f} s   ", end="", flush=True)
    print()
    secs = time.time() - t0
    if job["status"] != "done":
        print("ÉCHEC :", job.get("error"))
        return None
    print(f"PNG      : {job['path']}")
    print(f"Dimensions: {job['dims'][0]}x{job['dims'][1]}  Taille : {job['size']:,} octets")
    print(f"Durée    : {secs:.1f} s (sd-cli : {job['seconds']} s, encodage {job.get('encode_seconds')} s)")
    return {"test": name, "file": job["path"], "size": job["size"], "dims": job["dims"], "seconds": round(secs, 1),
            "steps": body["steps"], "cfg": body["cfg"]}


def base_body(mode, prompt, w, h, steps, cfg, seed):
    return {"mode": mode, "prompt": prompt, "width": w, "height": h, "steps": steps, "cfg": cfg, "seed": seed, "preview": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:7860")
    ap.add_argument("--only", choices=["t2i", "edit", "mask", "annot"])
    ap.add_argument("--steps", type=int, default=12)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    os.makedirs(P("outputs"), exist_ok=True)
    results = []
    st = call(a.base, "/api/status")
    print("serveur :", st.get("model"), "| backend :", st.get("backend"), "|", st.get("detail"))

    t2i_out = None
    if a.only in (None, "t2i"):
        b = base_body("t2i", "A cozy wooden cabin in a snowy forest at dusk, warm light in the windows, photorealistic", 512, 512, a.steps, a.cfg, a.seed)
        r = run(a.base, "texte vers image 512x512", b)
        results.append(r)
        if r:
            t2i_out = r["file"]

    src = t2i_out or (P("outputs", "test_t2i_512.png") if os.path.exists(P("outputs", "test_t2i_512.png")) else P("tests", "test_scene.png"))
    if a.only in (None, "edit"):
        b = base_body("edit", "Replace the sky with a dramatic orange sunset, keep everything else unchanged", 512, 512, a.steps, a.cfg, a.seed)
        b["ref_images"] = [data_url(src)]
        results.append(run(a.base, f"édition image + texte (référence : {os.path.basename(src)})", b))

    mask = P("outputs", "test_mask_generated.png")
    annotated = P("outputs", "test_mask_annotated.png")
    overlay = P("outputs", "test_mask_overlay.png")
    if a.only in (None, "mask", "annot"):
        subprocess.run([sys.executable, P("tools", "make_mask.py"), src, mask, "--cx", "0.5", "--cy", "0.42", "--r", "0.30",
                        "--overlay", overlay, "--annotate", annotated], check=True)

    if a.only in (None, "mask"):
        b = base_body("mask", "Replace the object in the area painted in red with a large red hot air balloon standing on the snow, keep everything outside the painted area unchanged", 512, 512, a.steps, a.cfg, a.seed)
        b["init_image"] = data_url(src)
        b["mask_image"] = data_url(mask)
        b["ref_images"] = [data_url(overlay)]
        b["strength"] = 1.0
        results.append(run(a.base, "édition guidée par masque (masque généré par script)", b))

    if a.only in (None, "annot"):
        b = base_body("annot", "Replace the object inside the red circle with a large red hot air balloon standing on the snow, then remove the red circle; keep everything outside the circle unchanged", 512, 512, a.steps, a.cfg, a.seed)
        b["ref_images"] = [data_url(annotated)]
        results.append(run(a.base, "édition guidée par annotation (cercle rouge tracé par script)", b))

    print("\n=== Récapitulatif ===")
    for r in results:
        if r:
            print(f"{r['test']:<62} {r['seconds']:>7.1f} s  {r['size']:>9,} o  {r['file']}")
    prev = []
    if os.path.exists(P("outputs", "test_results.json")):
        try:
            prev = json.load(open(P("outputs", "test_results.json"), encoding="utf-8"))
        except Exception:
            prev = []
    names = {r["test"] for r in results if r}
    prev = [p for p in prev if p.get("test") not in names]
    json.dump(prev + [r for r in results if r], open(P("outputs", "test_results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
