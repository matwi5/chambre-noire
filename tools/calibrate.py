r"""Calibration des estimations de durée : trois courtes générations dont les mesures vont dans tools/calibration.json.

  Windows : venv\Scripts\python.exe tools\calibrate.py [--backend …] [--model q4|q8] [--steps 3] [--if-needed]
  macOS   : venv/bin/python tools/calibrate.py [--model q4|q8|h3] [--steps 3] [--if-needed]

Qwen (--model q4, q8, uc-q4 ou uc-q8 : la version à calibrer ; défaut : celle de config.json) :
- texte → image 512×512 et 768×768 : deux tailles de séquence, pour ajuster les deux coûts d'une étape ;
- édition 512×512 avec une référence (l'image 512×512 produite juste avant) : coût de l'encodage des références.
MiniMax H3 (--model h3 : sa version installée, h3-q4 ou h3-q8, prise comme le serveur la prend ; ses 6 étapes fixes,
--steps ne compte pas), environ 9 minutes sur le Mac :
- texte → image 1024×1024 et 512×512 ;
- édition 1024×1024 avec une référence (l'image 1024×1024 produite juste avant) : lecture de l'image par le VAE.
Les images produites restent dans jobs/ (pas dans outputs/ ni dans le journal). --if-needed ne fait rien si ce
moteur et ce modèle ont déjà trois mesures faites avec la release de sd.cpp installée : après une mise à jour du
moteur, la calibration est refaite. setup.py lance ce script à la fin de l'installation, pour Qwen seulement :
MiniMax H3 se calibre à la main, et se recalibre de même après une mise à jour du moteur. Une mesure qui n'a pas pu
être gardée (tools/calibration.json illisible, verrou tenu trop longtemps) arrête le script en échec. Un serveur déjà
lancé ne prend ces mesures qu'à sa relance ou après sa prochaine mesure gardée (génération finie hors de l'espace
privé) : il garde les mesures lues au lancement.
"""
import argparse, base64, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch

RUNS = [("t2i", 512, 512), ("t2i", 768, 768), ("edit", 512, 512)]
H3_RUNS = [("t2i", 1024, 1024), ("t2i", 512, 512), ("edit", 1024, 1024)]   # même nombre de mesures que RUNS
PROMPT = "A red bicycle leaning against a white brick wall, morning light, photorealistic"
EDIT = "Make the bicycle blue, keep everything else unchanged"


def main():
    launch.restrict_new_files()
    cfg = launch.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=launch.PLATFORM_BACKENDS, default=launch.default_backend(cfg))
    ap.add_argument("--model", choices=list(launch.DIFFUSION) + ["h3"], default=cfg.get("model", "q4"))
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--if-needed", action="store_true", help="ne rien faire si ce moteur et ce modèle sont déjà calibrés")
    a = ap.parse_args()
    h3 = a.model == "h3"
    launch.setup_state(cfg, a.backend, cfg.get("model", "q4") if h3 else a.model)
    # modèle de la calibration (clé et version, comme une demande du serveur : job_model) : Qwen à la version du
    # serveur, ou MiniMax H3 à sa version installée
    key, version = ("h3", launch.model_version("h3")) if h3 else ("qwen", launch.S.model)
    if not version:
        sys.exit("[calibration] MiniMax H3 n'est pas installé, ou le moteur est trop ancien : lancez setup.py --h3")
    runs, steps = (H3_RUNS, launch.MODEL_TABLE["h3"]["steps"][0]) if h3 else (RUNS, a.steps)
    if a.if_needed and launch.S.store.count(launch.S.backend, version, launch.S.engine) >= len(runs):
        print(f"[calibration] {launch.S.backend}/{version} : déjà faite ({launch.S.engine})")
        return
    try:                                      # un fichier illisible n'est jamais écrasé : rien ne serait gardé
        launch.S.store.read(strict=True)
    except Exception as e:
        sys.exit(f"[calibration] {launch.CALIB} illisible ({e}) : supprimez-le pour repartir de zéro")
    ref = None
    for i, (kind, w, h) in enumerate(runs, 1):
        jid = time.strftime("%Y%m%d_%H%M%S") + f"_calibration{i}"
        d = launch.P("jobs", jid)
        os.makedirs(d, exist_ok=True)
        req = {"mode": kind, "prompt": PROMPT if kind == "t2i" else EDIT, "width": w, "height": h, "steps": steps,
               "seed": 42, "ref_images": [ref] if kind == "edit" else []}
        job = {"id": jid, "req": req, "dir": d, "out": os.path.join(d, "calibration.png"), "status": "queued",
               "created": time.time(), "calibration": True, "model": key, "version": version}
        print(f"[calibration] {i}/{len(runs)} : {'édition' if kind == 'edit' else 'texte → image'} {w}×{h}, "
              f"{steps} étapes ({launch.S.backend}/{version})", flush=True)
        launch.start_job(job)
        launch.run_job(job)
        if job["status"] != "done":
            sys.exit(f"[calibration] échec : {job.get('error')} (détail : {os.path.join(d, 'sd-cli.log')})")
        if not job.get("measured"):           # mesure introuvable ou non gardée (message « ignorée » plus haut)
            sys.exit(f"[calibration] échec : mesure de la génération {i} non gardée dans {launch.CALIB}")
        print(f"[calibration] {i}/{len(runs)} : {job['seconds']} s", flush=True)
        if ref is None:
            ref = "data:image/png;base64," + base64.b64encode(open(job["out"], "rb").read()).decode()
    c = launch.S.store.coefficients(launch.S.backend, version, launch.S.engine, key)
    print(f"[calibration] terminée : étape {c['a'] + c['b']:.1f} s à 512×512, encodage {c['e0']:.0f} s, "
          f"décodage {c['v'] * 0.262:.0f} s à 512×512 (un serveur déjà lancé les prend à sa relance ou après sa "
          "prochaine mesure)")


if __name__ == "__main__":
    main()
