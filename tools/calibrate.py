r"""Calibration des estimations de durée : trois courtes générations dont les mesures vont dans tools/calibration.json.

  Windows : venv\Scripts\python.exe tools\calibrate.py [--backend …] [--model q4|q8] [--steps 3] [--if-needed]
  macOS   : venv/bin/python tools/calibrate.py [--model q4|q8] [--steps 3] [--if-needed]

- texte → image 512×512 et 768×768 : deux tailles de séquence, pour ajuster les deux coûts d'une étape ;
- édition 512×512 avec une référence (l'image 512×512 produite juste avant) : coût de l'encodage des références.
Les images produites restent dans jobs/ (pas dans outputs/ ni dans le journal). --if-needed ne fait rien si ce
moteur et ce modèle ont déjà trois mesures. setup.py lance ce script à la fin de l'installation.
"""
import argparse, base64, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch

RUNS = [("t2i", 512, 512), ("t2i", 768, 768), ("edit", 512, 512)]
PROMPT = "A red bicycle leaning against a white brick wall, morning light, photorealistic"
EDIT = "Make the bicycle blue, keep everything else unchanged"


def main():
    cfg = launch.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=launch.PLATFORM_BACKENDS, default=launch.default_backend(cfg))
    ap.add_argument("--model", choices=list(launch.DIFFUSION), default=cfg.get("model", "q4"))
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--if-needed", action="store_true", help="ne rien faire si ce moteur et ce modèle sont déjà calibrés")
    a = ap.parse_args()
    launch.setup_state(cfg, a.backend, a.model)
    if a.if_needed and launch.S.store.count(launch.S.backend, launch.S.model) >= len(RUNS):
        print(f"[calibration] {launch.S.backend}/{launch.S.model} : déjà faite")
        return
    ref = None
    for i, (kind, w, h) in enumerate(RUNS, 1):
        jid = time.strftime("%Y%m%d_%H%M%S") + f"_calibration{i}"
        d = launch.P("jobs", jid)
        os.makedirs(d, exist_ok=True)
        req = {"mode": kind, "prompt": PROMPT if kind == "t2i" else EDIT, "width": w, "height": h, "steps": a.steps,
               "seed": 42, "ref_images": [ref] if kind == "edit" else []}
        job = {"id": jid, "req": req, "dir": d, "out": os.path.join(d, "calibration.png"), "status": "queued",
               "created": time.time(), "calibration": True}
        print(f"[calibration] {i}/{len(RUNS)} : {'édition' if kind == 'edit' else 'texte → image'} {w}×{h}, "
              f"{a.steps} étapes ({launch.S.backend}/{launch.S.model})", flush=True)
        launch.run_job(job)
        if job["status"] != "done":
            sys.exit(f"[calibration] échec : {job.get('error')} (détail : {os.path.join(d, 'sd-cli.log')})")
        print(f"[calibration] {i}/{len(RUNS)} : {job['seconds']} s", flush=True)
        if ref is None:
            ref = "data:image/png;base64," + base64.b64encode(open(job["out"], "rb").read()).decode()
    c = launch.S.store.coefficients(launch.S.backend, launch.S.model)
    print(f"[calibration] terminée : étape {c['a'] + c['b']:.1f} s à 512×512, encodage {c['e0']:.0f} s, "
          f"décodage {c['v'] * 0.262:.0f} s à 512×512")


if __name__ == "__main__":
    main()
