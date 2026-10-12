r"""Estimation des durées de génération, calibrée sur les mesures de la machine.

Modèle de coût (en secondes) d'une image de W×H pixels, avec ses images de référence :

  étape     = a·n + b·n²     n = jetons du transformeur / 1024 (sortie + références) ; 1024 jetons = 512×512 px.
                             a : couches ordinaires, proportionnelles aux jetons ; b : attention, au carré des jetons.
  encodage  = e0 + e1·R      R = mégapixels des références, lues aussi par l'encodeur Qwen3-VL.
  VAE       = u·(R + I)      encodage des références et de l'image de départ I (dessin guidé, mode masque) ;
            + v·M            décodage de la sortie de M mégapixels, et de chaque aperçu.
  fixe      = o              chargement du modèle, premier pas plus lent, divers.

  total = o + e0 + e1·R + u·(R + I) + étapes·(a·n + b·n²) + (1 + aperçus)·v·M

sd.cpp 74988b2 ramène chaque référence à la surface de la sortie (proportions gardées, côtés multiples de 32) et
compte (W/16)·(H/16) jetons pour une image de W×H pixels. tools/ui/index.html applique la même formule avec les
coefficients que /api/status lui envoie : les deux doivent rester identiques.

Calibration : chaque génération terminée ajoute une mesure à tools/calibration.json (les 40 dernières par moteur et
par modèle). Les coefficients sont recalculés à partir de ces mesures, par des médianes qui ignorent une génération
anormale (machine occupée, premier chargement du modèle depuis le disque) :
- a et b : médiane du temps d'étape par taille de séquence, puis ajustement des deux coefficients dès que deux tailles
  assez différentes ont été mesurées ; avec une seule taille, la forme des valeurs de départ est gardée et mise à
  l'échelle ;
- e0, e1, u, v, o : médianes des mesures qui les concernent ; les valeurs de départ restent tant qu'aucune mesure
  ne les touche.
"""
import json, math, os, time

# Valeurs de départ par moteur, avant toute mesure sur la machine.
# Windows : conversion des anciennes valeurs de départ (étape à 512×512 en texte → image et en édition avec une
# référence de 512×512, soit n = 1 et n = 2) ; u estimé à la moitié du décodage, faute de mesure.
PRIORS = {
    "vulkan": {"a": 10.0, "b": 6.0,  "e0": 58.0, "e1": 141.0, "u": 42.0,  "v": 84.0,  "o": 5.0},   # Radeon intégré (RDNA2) mesuré
    "cuda":   {"a": 0.30, "b": 0.05, "e0": 4.0,  "e1": 15.0,  "u": 3.0,   "v": 5.7,   "o": 8.0},   # estimation RTX 40xx
    "cpu":    {"a": 85.0, "b": 45.0, "e0": 45.0, "e1": 590.0, "u": 170.0, "v": 343.0, "o": 5.0},
    "metal":  {"a": 3.09, "b": 0.26, "e0": 7.0,  "e1": 485.0, "u": 25.0,  "v": 130.0, "o": 7.0},   # Apple M6 mesuré (Q4_K_M)
}
KEEP = 40          # mesures conservées par moteur et par modèle
PATCH_PX = 16 * 16  # pixels par jeton du transformeur


def ref_px(rw, rh, w, h):
    """Pixels d'une référence de rw×rh telle que sd.cpp la donne au modèle pour une sortie de w×h."""
    vw = math.sqrt(w * h * rw / rh)
    vh = vw * rh / rw
    snap = lambda x: max(32, int(math.floor(x / 32 + 0.5)) * 32)
    return snap(vw) * snap(vh)


def median(xs):
    xs = sorted(xs)
    k = len(xs)
    if not k:
        return None
    return xs[k // 2] if k % 2 else (xs[k // 2 - 1] + xs[k // 2]) / 2


def make_sample(job):
    """Mesure d'une génération terminée (dictionnaire de tools/launch.py), ou None s'il manque une durée."""
    r = job["req"]
    w, h, steps = int(r["width"]), int(r["height"]), int(r["steps"])
    enc, samp, vae = job.get("encode_seconds_net"), job.get("sampling_seconds"), job.get("vae_seconds")
    if not (enc and samp and vae and steps):
        return None
    refs, init = job.get("ref_px") or [], job.get("init_px") or 0
    previews = steps // job["preview_interval"] if job.get("preview_interval") else 0
    times = [t for _, t in sorted((job.get("step_times") or {}).items())]
    if len(times) > 2:
        times = times[1:]                     # le premier pas charge les poids sur le GPU : compté dans « fixe »
    step = median(times) if times else max(0.01, (samp - previews * vae) / steps)
    venc = job.get("venc_seconds") or 0.0
    over = job["seconds"] - enc - venc - vae * (1 + previews) - steps * step
    return {"w": w, "h": h, "steps": steps, "n": round((w * h + sum(refs)) / PATCH_PX / 1024, 4),
            "R": round(sum(refs) / 1e6, 4), "I": round(init / 1e6, 4), "M": round(w * h / 1e6, 4),
            "step": round(step, 3), "enc": round(enc, 2), "venc": round(venc, 2), "vae": round(vae, 2),
            "over": round(over, 2), "t": int(time.time())}


def fit(samples, prior):
    """Coefficients du modèle de coût ajustés sur les mesures (voir l'en-tête du module)."""
    c = dict(prior)
    c["samples"] = len(samples)
    if not samples:
        return c
    groups = {}                                # tailles de séquence à ±6 % près
    for s in samples:
        groups.setdefault(round(math.log2(s["n"]) * 6), []).append(s)
    pts = [(median([s["n"] for s in g]), median([s["step"] for s in g])) for g in groups.values()]
    ns = [n for n, _ in pts]
    a = b = None
    if len(pts) >= 2 and max(ns) >= 1.5 * min(ns):
        # moindres carrés sur l'erreur relative : (a·n + b·n²) / t ≈ 1 pour chaque taille mesurée
        x = [n / t for n, t in pts]
        y = [n * n / t for n, t in pts]
        sxx, syy = sum(i * i for i in x), sum(j * j for j in y)
        sxy, sx, sy = sum(i * j for i, j in zip(x, y)), sum(x), sum(y)
        det = sxx * syy - sxy * sxy
        if det > 1e-12:
            a, b = (sx * syy - sy * sxy) / det, (sy * sxx - sx * sxy) / det
        if a is None or a < 0 or b < 0:        # mesures incohérentes : repli sur la forme des valeurs de départ
            a = b = None
    if a is None:
        k = median([t / (prior["a"] * n + prior["b"] * n * n) for n, t in pts])
        a, b = prior["a"] * k, prior["b"] * k
    c["a"], c["b"] = round(a, 4), round(b, 5)
    plain = [s for s in samples if not s["R"]]
    if plain:
        c["e0"] = median([s["enc"] for s in plain])
    refs = [s for s in samples if s["R"]]
    if refs:
        c["e1"] = round(max(0.0, median([(s["enc"] - c["e0"]) / s["R"] for s in refs])), 2)
    vin = [s for s in samples if s["R"] + s["I"] > 0 and s["venc"]]
    if vin:
        c["u"] = round(median([s["venc"] / (s["R"] + s["I"]) for s in vin]), 2)
    c["v"] = round(median([s["vae"] / s["M"] for s in samples]), 2)
    c["o"] = round(max(0.0, median([s["over"] for s in samples])), 2)
    return c


def predict(c, w, h, steps, refs=(), init_px=0, previews=0):
    """Durée estimée (s) avec les coefficients c ; même formule que parts() dans tools/ui/index.html."""
    R, I, M = sum(refs) / 1e6, init_px / 1e6, w * h / 1e6
    n = (w * h + sum(refs)) / PATCH_PX / 1024
    return c["o"] + c["e0"] + c["e1"] * R + c["u"] * (R + I) + steps * (c["a"] * n + c["b"] * n * n) + (1 + previews) * c["v"] * M


class Store:
    """Mesures conservées dans tools/calibration.json, par « moteur/modèle »."""

    def __init__(self, path):
        self.path = path
        self.samples = self.read()

    def read(self):
        try:
            d = json.load(open(self.path, encoding="utf-8"))
        except Exception:
            d = {}
        # l'ancien format (moyennes par moteur, sans version) est ignoré : la calibration repart de zéro
        return d.get("samples", {}) if d.get("version") == 2 else {}

    def add(self, backend, model, sample):
        self.samples = self.read()             # tools/calibrate.py a pu écrire pendant que le lanceur tournait
        key = f"{backend}/{model}"
        self.samples[key] = (self.samples.get(key, []) + [sample])[-KEEP:]
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "samples": self.samples}, f, indent=1)
        os.replace(tmp, self.path)

    def count(self, backend, model):
        return len(self.samples.get(f"{backend}/{model}", []))

    def coefficients(self, backend, model):
        return fit(self.samples.get(f"{backend}/{model}", []), PRIORS.get(backend, PRIORS["vulkan"]))
