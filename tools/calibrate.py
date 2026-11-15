r"""Calibration des estimations de durée : de courtes générations dont les mesures vont dans tools/calibration.json.

  Windows : venv\Scripts\python.exe tools\calibrate.py [--backend …] [--model q4|q8] [--steps 3] [--if-needed]
  macOS   : venv/bin/python tools/calibrate.py [--model q4|q8|h3|video] [--steps 3] [--if-needed]

Qwen (--model q4, q8, uc-q4 ou uc-q8 : la version à calibrer ; défaut : celle de config.json) :
- texte → image 512×512 et 768×768 : deux tailles de séquence, pour ajuster les deux coûts d'une étape ;
- édition 512×512 avec une référence (l'image 512×512 produite juste avant) : coût de l'encodage des références.
MiniMax H3 (--model h3 : sa version installée, h3-q4 ou h3-q8, prise comme le serveur la prend ; ses 6 étapes fixes,
--steps ne compte pas), environ 9 minutes sur le Mac :
- texte → image 1024×1024 et 512×512 ;
- édition 1024×1024 avec une référence (l'image 1024×1024 produite juste avant) : lecture de l'image par le VAE.
Vidéo (--model video : sa version h3-video ; ses 4 étapes fixes), deux vidéos de 480×288, environ 9 minutes sur le
Mac :
- 56 puis 124 images (2 et 5 s) : deux tailles de séquence assez différentes pour ajuster les deux coûts d'une étape.
Les images et vidéos produites restent dans jobs/ (pas dans outputs/ ni dans le journal). --if-needed ne fait rien
si ce moteur et ce modèle ont déjà autant de mesures que de générations à faire (trois, deux pour la vidéo), faites
avec la release de sd.cpp installée : après une mise à jour du moteur, la calibration est refaite. setup.py lance ce
script à la fin de l'installation, pour Qwen seulement : MiniMax H3 et la vidéo se calibrent à la main, et se
recalibrent de même après une mise à jour du moteur. Une mesure qui n'a pas pu être gardée (verrou tenu trop
longtemps, fichier d'un format plus récent, erreur du disque) arrête le script en échec ; un fichier illisible est mis
de côté et la calibration repart d'un fichier neuf. Un serveur déjà lancé ne prend ces mesures qu'à sa relance ou
après sa prochaine mesure gardée (génération finie hors de l'espace privé) : il garde les mesures lues au lancement.
"""
import argparse, base64, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import launch

RUNS = [("t2i", 512, 512), ("t2i", 768, 768), ("edit", 512, 512)]
H3_RUNS = [("t2i", 1024, 1024), ("t2i", 512, 512), ("edit", 1024, 1024)]   # même nombre de mesures que RUNS
VIDEO_RUNS = [("t2i", 480, 288, 56), ("t2i", 480, 288, 124)]   # (mode, largeur, hauteur, images)
VIDEO_PROMPT = "A small fishing boat leaving a harbour at sunrise, seagulls flying, slow camera move forward"
PROMPT = "A red bicycle leaning against a white brick wall, morning light, photorealistic"
EDIT = "Make the bicycle blue, keep everything else unchanged"


def main():
    launch.restrict_new_files()
    cfg = launch.load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=launch.PLATFORM_BACKENDS, default=launch.default_backend(cfg))
    ap.add_argument("--model", choices=list(launch.DIFFUSION) + ["h3", "video"], default=cfg.get("model", "q4"))
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--if-needed", action="store_true", help="ne rien faire si ce moteur et ce modèle sont déjà calibrés")
    a = ap.parse_args()
    other = a.model in ("h3", "video")              # un modèle choisi par sa clé, à sa version installée
    launch.setup_state(cfg, a.backend, cfg.get("model", "q4") if other else a.model)
    # modèle de la calibration (clé et version, comme une demande du serveur : job_model) : Qwen à la version du
    # serveur, ou MiniMax H3 et la vidéo à leur version installée
    key, version = (a.model, launch.model_version(a.model)) if other else ("qwen", launch.S.model)
    spec = launch.MODEL_TABLE[key]
    if not version:
        sys.exit(f"[calibration] {spec['name']} : non installé, ou moteur trop ancien : lancez setup.py "
                 f"{spec['setup']}")
    if key == "video":
        runs = VIDEO_RUNS
    else:
        runs = [run + (None,) for run in (H3_RUNS if other else RUNS)]
    steps = spec["steps"][0] if other else a.steps
    if a.if_needed and launch.S.store.count(launch.S.backend, version, launch.S.engine) >= len(runs):
        print(f"[calibration] {launch.S.backend}/{version} : déjà faite ({launch.S.engine})")
        return
    ref = None
    for i, (kind, w, h, frames) in enumerate(runs, 1):
        jid = time.strftime("%Y%m%d_%H%M%S") + f"_calibration{i}"
        d = launch.P("jobs", jid)
        os.makedirs(d, exist_ok=True)
        prompt = VIDEO_PROMPT if frames else PROMPT if kind == "t2i" else EDIT
        req = {"mode": kind, "prompt": prompt, "width": w, "height": h, "steps": steps,
               "seed": 42, "ref_images": [ref] if kind == "edit" else []}
        if frames:
            req["frames"] = frames
        job = {"id": jid, "req": req, "dir": d, "out": os.path.join(d, "calibration" + spec["ext"]),
               "status": "queued", "created": time.time(), "calibration": True, "model": key, "version": version}
        what = f"vidéo {w}×{h}, {frames} images" if frames else \
            f"{'édition' if kind == 'edit' else 'texte → image'} {w}×{h}"
        print(f"[calibration] {i}/{len(runs)} : {what}, {steps} étapes ({launch.S.backend}/{version})", flush=True)
        launch.start_job(job)
        launch.run_job(job)
        if job["status"] != "done":
            sys.exit(f"[calibration] échec : {job.get('error')} (détail : {os.path.join(d, 'sd-cli.log')})")
        if not job.get("measured"):           # mesure introuvable ou non gardée (message « ignorée » plus haut)
            sys.exit(f"[calibration] échec : mesure de la génération {i} non gardée dans {launch.CALIB}")
        print(f"[calibration] {i}/{len(runs)} : {job['seconds']} s", flush=True)
        if ref is None and not frames:             # référence des éditions qui suivent (jamais pour la vidéo)
            ref = "data:image/png;base64," + base64.b64encode(open(job["out"], "rb").read()).decode()
    c = launch.S.store.coefficients(launch.S.backend, version, launch.S.engine, key)
    _, w, h, frames = runs[0]                      # résumé à la taille de la première génération
    nt, n = launch.estimate.tokens(w, h, (), 1, frames or 1)
    size = f"{w}×{h}" + (f", {frames} images" if frames else "")
    print(f"[calibration] terminée : étape {launch.estimate.step_cost(c, nt, n):.1f} s à {size}, encodage "
          f"{c['e0']:.0f} s, décodage {c['v'] * w * h * (frames or 1) / 1e6:.0f} s à {size} (un serveur déjà lancé "
          "les prend à sa relance ou après sa prochaine mesure)")


if __name__ == "__main__":
    main()
