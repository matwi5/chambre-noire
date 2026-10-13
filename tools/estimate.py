r"""Estimation des durées de génération, calibrée sur les mesures de la machine.

Modèle de coût (en secondes) d'une image de W×H pixels, avec ses images de référence :

  étape     = a·n + b·n²     n = jetons du transformeur / 1024 (sortie + références) ; 1024 jetons = 512×512 px.
                             a : couches ordinaires, proportionnelles aux jetons ; b : attention, au carré des jetons.
  encodage  = e0 + e1·R      R = mégapixels des références, lues aussi par l'encodeur Qwen3-VL.
  VAE       = u·(R + I)      encodage des références et de l'image de départ I (dessin guidé, mode masque) ;
            + v·M            décodage de la sortie de M mégapixels, et de chaque aperçu.
  fixe      = o              chargement du modèle, premier pas plus lent, divers.

  total = o + e0 + e1·R + u·(R + I) + étapes·(a·n + b·n²) + (1 + aperçus)·v·M

Cache de préfixe (sd.cpp à partir de la release master-903) : la première étape garde les clés et valeurs du texte
et des références, les suivantes ne calculent plus que les nt jetons de la sortie (n = nt + nr) :

  étape     = a·nt + b·nt·n  les couches ne traitent que la sortie ; son attention porte sur toute la séquence ;
  préfixe   = a·nr + b·nr·n  calculé une fois, à la première étape (soit étape·nr/nt).

sd.cpp ramène chaque référence à la surface de la sortie (proportions gardées, côtés multiples de 32) et compte
(W/16)·(H/16) jetons pour une image de W×H pixels. tools/ui/index.html applique la même formule avec les
coefficients que /api/status lui envoie : les deux doivent rester identiques.

Calibration : chaque génération terminée ajoute une mesure à tools/calibration.json (les 40 dernières par moteur et
par modèle), étiquetée avec la release de sd.cpp qui l'a produite ; seules comptent les mesures de la release
installée, si bien qu'une mise à jour du moteur repart des valeurs de départ. Les coefficients sont recalculés à partir
de ces mesures, par des médianes qui ignorent une génération anormale (machine occupée, premier chargement du modèle
depuis le disque) :
- a et b : médiane du temps d'étape par taille de séquence, puis ajustement des deux coefficients dès que deux tailles
  assez différentes ont été mesurées ; avec une seule taille, la forme des valeurs de départ est gardée et mise à
  l'échelle ;
- e0, e1, u, v, o : médianes des mesures qui les concernent ; les valeurs de départ restent tant qu'aucune mesure
  ne les touche. Avec le cache de préfixe, la première étape d'une édition dure plus que celle d'un texte → image ;
  le surcoût est retiré de o d'après le modèle (préfixe = étape·nr/nt), le reste de l'écart y demeure.
"""
import json, math, os, re, time

# Valeurs de départ par moteur, avant toute mesure sur la machine.
# Windows : conversion des anciennes valeurs de départ (étape à 512×512 en texte → image et en édition avec une
# référence de 512×512, soit n = 1 et n = 2) ; u estimé à la moitié du décodage, faute de mesure.
PRIORS = {
    "vulkan": {"a": 10.0, "b": 6.0,  "e0": 58.0, "e1": 141.0, "u": 42.0,  "v": 84.0,  "o": 5.0},   # Radeon intégré (RDNA2) mesuré
    "cuda":   {"a": 0.30, "b": 0.05, "e0": 4.0,  "e1": 15.0,  "u": 3.0,   "v": 5.7,   "o": 8.0},   # estimation RTX 40xx
    "cpu":    {"a": 85.0, "b": 45.0, "e0": 45.0, "e1": 590.0, "u": 170.0, "v": 343.0, "o": 5.0},
    # Apple M6 mesuré (Q4_K_M, sd.cpp master-959, encodeur GGUF et VAE sur Metal, cache de préfixe)
    "metal":  {"a": 2.71, "b": 0.284, "e0": 1.3, "e1": 5.2,  "u": 3.4,   "v": 10.4,  "o": 2.3},
}
KEEP = 40          # mesures conservées par moteur et par modèle
PATCH_PX = 16 * 16  # pixels par jeton du transformeur
LEGACY_ENGINE = "master-890-74988b2"   # release des mesures enregistrées avant leur étiquetage
PREFIX_CACHE_FROM = 903                # première release de sd.cpp avec le cache de préfixe (commit 2dc7f54)


def prefix_cache(engine):
    """Vrai si la release de sd.cpp (par exemple « master-959-d637cfb ») a le cache de préfixe de Qwen-Image 2.1."""
    m = re.match(r"master-(\d+)-", engine or "")
    return bool(m) and int(m.group(1)) >= PREFIX_CACHE_FROM


def tokens(w, h, refs=()):
    """(nt, n) : jetons de la sortie et de toute la séquence (sortie + références), par paquets de 1024."""
    return w * h / PATCH_PX / 1024, (w * h + sum(refs)) / PATCH_PX / 1024


def step_cost(c, nt, n):
    """Durée d'une étape avec les coefficients c : a·n + b·n², ou a·nt + b·nt·n avec le cache de préfixe."""
    p = nt if c.get("kv") else n
    return c["a"] * p + c["b"] * p * n


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


def make_sample(job, engine=LEGACY_ENGINE):
    """Mesure d'une génération terminée (dictionnaire de tools/launch.py) par la release engine, ou None s'il manque
    une durée."""
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
    nt, n = tokens(w, h, refs)
    kv = prefix_cache(engine)
    prefix = step * (n - nt) / nt if kv else 0.0      # première étape : calcul du préfixe texte + références
    over = job["seconds"] - enc - venc - vae * (1 + previews) - steps * step - prefix
    return {"w": w, "h": h, "steps": steps, "n": round(n, 4), "nt": round(nt, 4), "kv": kv,
            "R": round(sum(refs) / 1e6, 4), "I": round(init / 1e6, 4), "M": round(w * h / 1e6, 4),
            "step": round(step, 3), "enc": round(enc, 2), "venc": round(venc, 2), "vae": round(vae, 2),
            "over": round(over, 2), "sd": engine, "t": int(time.time())}


def fit(samples, prior, kv=False):
    """Coefficients du modèle de coût ajustés sur les mesures (voir l'en-tête du module) ; kv : cache de préfixe."""
    c = dict(prior)
    c["samples"] = len(samples)
    c["kv"] = kv
    if not samples:
        return c
    # étape = a·p + b·p·n, avec p = n, ou p = nt (jetons de la sortie) avec le cache de préfixe ; les mesures
    # antérieures à l'étiquetage n'ont ni nt ni cache de préfixe
    groups = {}                                # tailles (p, n) à ±6 % près
    for s in samples:
        p, n = (s["nt"] if s.get("kv") else s["n"]), s["n"]
        groups.setdefault((round(math.log2(p) * 6), round(math.log2(n) * 6)), []).append((p, n, s["step"]))
    pts = [tuple(median([v[i] for v in g]) for i in range(3)) for g in groups.values()]
    ns = [n for _, n, _ in pts]
    a = b = None
    if len(pts) >= 2 and max(ns) >= 1.5 * min(ns):
        # moindres carrés sur l'erreur relative : (a·p + b·p·n) / t ≈ 1 pour chaque taille mesurée
        x = [p / t for p, _, t in pts]
        y = [p * n / t for p, n, t in pts]
        sxx, syy = sum(i * i for i in x), sum(j * j for j in y)
        sxy, sx, sy = sum(i * j for i, j in zip(x, y)), sum(x), sum(y)
        det = sxx * syy - sxy * sxy
        if det > 1e-12:
            a, b = (sx * syy - sy * sxy) / det, (sy * sxx - sx * sxy) / det
        if a is None or a < 0 or b < 0:        # mesures incohérentes : repli sur la forme des valeurs de départ
            a = b = None
    if a is None:
        k = median([t / (prior["a"] * p + prior["b"] * p * n) for p, n, t in pts])
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
    nt, n = tokens(w, h, refs)
    step = step_cost(c, nt, n)
    prefix = step * (n - nt) / nt if c.get("kv") else 0.0
    return c["o"] + c["e0"] + c["e1"] * R + c["u"] * (R + I) + prefix + steps * step + (1 + previews) * c["v"] * M


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

    def current(self, backend, model, engine):
        """Mesures de ce moteur et de ce modèle faites par la release engine de sd.cpp."""
        return [s for s in self.samples.get(f"{backend}/{model}", []) if s.get("sd", LEGACY_ENGINE) == engine]

    def count(self, backend, model, engine):
        return len(self.current(backend, model, engine))

    def coefficients(self, backend, model, engine):
        return fit(self.current(backend, model, engine), PRIORS.get(backend, PRIORS["vulkan"]), prefix_cache(engine))
