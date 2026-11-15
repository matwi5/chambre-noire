"""Estimations et calibration de la vidéo (ticket 12 de MiniMax H3) : formule sur les mégapixels-images (largeur ×
hauteur × nombre d'images), valeurs de départ tirées de l'essai, image de départ, mesures rangées sous h3-video sans
toucher aux autres ni rien garder d'une vidéo privée, estimation de la file, calibration par tools/calibrate.py
--model video. Sur le banc à faux moteur (voir bench.py), la vidéo installée par bench.video() le temps d'un test."""
import contextlib, io, os, sys, unittest
from unittest import mock

import bench
from bench import S, call, gen_body, wait_job

launch, estimate = bench.launch, bench.estimate
import calibrate  # noqa: E402  (tools/ est dans le chemin par bench)

VIDEO = {"model": "video", "steps": 4, "width": 480, "height": 288, "frames": 56}   # vidéo Petite de 2 s
METAL = {**estimate.VIDEO_PRIORS["metal"], "kv": False}
ENGINE = "master-1090-8b1e9df"
MP = 1024 * 1024


def step(c, w, h, frames):
    """Durée d'une étape d'une vidéo de w×h et frames images avec les coefficients c."""
    nt, n = estimate.tokens(w, h, (), 1, frames)
    return estimate.step_cost(c, nt, n)


def samples():
    return S.store.read()


class VideoFormulaTest(unittest.TestCase):
    """Valeurs de départ de la vidéo sur Metal (spec, « Avancement et estimations » ; RESULTATS de l'essai)."""

    def test_the_priors_redo_the_essay_step_times(self):
        # temps d'étape de la spec : génération / 4 étapes de v7, v9, v4 et v10
        for name, (w, h, frames), measured in (("v7 480×288, 22 images", (480, 288, 22), 9.7),
                                               ("v9 480×288, 124 images", (480, 288, 124), 57.0),
                                               ("v4 864×480, 56 images", (864, 480, 56), 93.0),
                                               ("v10 864×480, 124 images", (864, 480, 124), 264.0)):
            with self.subTest(name):
                self.assertAlmostEqual(step(METAL, w, h, frames) / measured, 1, delta=0.1)

    def test_the_priors_redo_the_one_run_made_with_the_installed_encoder(self):
        # v12 : 480×288, 73 images, encodeur Q4_K_M, 223,0 s au total
        self.assertAlmostEqual(estimate.predict(METAL, 480, 288, 4, frames=73) / 223.0, 1, delta=0.1)

    def test_a_start_image_adds_about_45_seconds_in_small_size(self):
        # v8 contre v7 : 111,5 s contre 66,3 s, en 480×288 et 22 images
        plain = estimate.predict(METAL, 480, 288, 4, frames=22)
        start = estimate.predict(METAL, 480, 288, 4, [], 480 * 288, frames=22)
        self.assertAlmostEqual(start - plain, 45, delta=1)

    def test_an_image_estimate_is_the_same_as_before(self):
        # valeurs de predict à la base du lot (estimate.py du commit 1901c10), mêmes demandes
        qwen = {**estimate.PRIORS["metal"], "kv": True}
        h3 = {**estimate.H3_PRIORS["metal"], "kv": False, "rw": 2, "rmin": 1024}
        self.assertAlmostEqual(estimate.predict(qwen, 512, 512, 8, [512 * 512], 0, 1), 40.8090336, places=6)
        self.assertAlmostEqual(estimate.predict(h3, 1024, 1024, 6, [MP], MP, 3), 621.3583232, places=6)

    def test_an_image_sample_without_its_start_image_reading_still_counts_for_o(self):
        base = {"w": 512, "h": 512, "steps": 8, "R": 0.0, "venc": 0.0, "enc": 2.0, "vae": 3.0, "kv": True,
                "n": 1.0, "nt": 1.0, "M": 0.2621, "step": 3.0}
        image = [{**base, "I": 0.2621, "over": 9.0}, {**base, "I": 0.0, "over": 3.0}]
        self.assertEqual(estimate.fit(image, estimate.PRIORS["metal"], True)["o"], 6.0)   # médiane des deux

    def test_a_video_sample_counts_its_frames(self):
        job = {"req": {"width": 480, "height": 288, "steps": 4, "frames": 56}, "encode_seconds_net": 62.0,
               "sampling_seconds": 90.0, "vae_seconds": 14.0, "seconds": 170.0, "step_times": {}}
        s = estimate.make_sample(job, ENGINE, "video")
        px = 480 * 288 * 56
        self.assertEqual((s["F"], s["n"], s["nt"], s["M"], s["kv"]),
                         (56, round(px / 262144, 4), round(px / 262144, 4), round(px / 1e6, 4), False))
        self.assertNotIn("F", estimate.make_sample({**job, "req": {"width": 512, "height": 512, "steps": 4}},
                                                   ENGINE, "h3"))

    def test_a_start_image_sample_moves_neither_the_steps_nor_the_fixed_part(self):
        """Le moteur ne chronomètre pas la lecture de l'image de départ d'une vidéo (pas de ligne
        « encode_first_stage completed », journal v8 de l'essai) : son temps reste dans « over », qui ne compte pas
        pour o ; ses étapes, plus lentes (v8), ne comptent pas pour a et b ; u garde sa valeur de départ, qui couvre
        les deux."""
        base = {"w": 480, "h": 288, "steps": 4, "F": 56, "R": 0.0, "venc": 0.0, "enc": 62.0, "vae": 14.0, "kv": False,
                "sd": ENGINE}
        plain = [{**base, "n": n, "nt": n, "M": m, "I": 0.0, "step": t, "over": 1.3}
                 for n, m, t in ((29.5, 7.74, 25.0), (65.4, 17.14, 57.0))]
        start = {**base, "n": 29.5, "nt": 29.5, "M": 7.74, "I": 0.1382, "step": 26.0, "over": 38.0}
        alone = estimate.fit(plain, estimate.VIDEO_PRIORS["metal"])
        both = estimate.fit(plain + [start], estimate.VIDEO_PRIORS["metal"])
        self.assertEqual((both["a"], both["b"], both["o"], both["u"]),
                         (alone["a"], alone["b"], alone["o"], estimate.VIDEO_PRIORS["metal"]["u"]))
        only = estimate.fit([start], estimate.VIDEO_PRIORS["metal"])
        self.assertEqual((only["a"], only["b"], only["o"]), tuple(estimate.VIDEO_PRIORS["metal"][k] for k in "abo"))


class VideoCase(bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.enterContext(bench.video())


def make_video(prompt="zve a boat", **kw):
    code, reply = call("POST", "/api/generate", gen_body(prompt, **{**VIDEO, **kw}))
    assert code == 202, bench.short((code, reply))
    return reply


class VideoSamplesTest(VideoCase):
    def test_a_video_records_its_sample_under_h3_video_only(self):
        before = samples()
        self.assertEqual(wait_job(make_video("zve1 une barque", frames=73)["id"])["status"], "done")
        after = samples()
        key = f"{S.backend}/h3-video"
        # une seule mesure de plus ; celles d'avant restent, au plus la plus ancienne sortie (les 40 dernières)
        self.assertEqual(after[key][:-1], before.get(key, [])[-(estimate.KEEP - 1):])
        last = after[key][-1]
        self.assertEqual((last["w"], last["h"], last["F"], last["M"]), (480, 288, 73, round(480 * 288 * 73 / 1e6, 4)))
        self.assertEqual({k: v for k, v in after.items() if k != key}, {k: v for k, v in before.items() if k != key})

    def test_a_private_video_records_no_sample(self):
        session = bench.create_private("Mot2passe!")
        before = samples()
        code, j = call("POST", "/api/generate", gen_body("zve2 secrète", private=True, **VIDEO), private=session)
        self.assertEqual(code, 202, j)
        self.assertEqual(wait_job(j["id"], private=session)["status"], "done")
        bench.wait_idle()
        self.assertEqual(samples(), before)


class VideoQueueTest(VideoCase):
    def test_the_queue_estimates_a_video_with_its_frames_size_and_start_image(self):
        a = bench.generate("HOLD=video-file zve3 qwen")["id"]
        try:
            wait_job(a, ("running",))
            img = bench.data_url(bench.png_bytes())
            b = make_video("zve3 normale", width=864, height=480, frames=124, init_image=img, preview=True,
                           preview_interval=1)["id"]
            s = call("GET", "/api/status")[1]
            video = s["model_estimates"]["video"]
            entry = next(e for e in s["queue"] if e["id"] == b)
            self.assertEqual((entry["model"], entry["frames"]), ("video", 124))
            # sans aperçu, même demandé (la vidéo n'en a pas) ; l'image de départ comptée à la taille de la sortie
            self.assertAlmostEqual(entry["estimate"],
                                   estimate.predict(video, 864, 480, 4, [], 864 * 480, 0, frames=124), delta=0.1)
            # (coefficients du moment : ajustés sur les mesures du faux moteur quand d'autres tests en ont gardé)
            self.assertGreater(entry["estimate"], estimate.predict(video, 864, 480, 4, [], 864 * 480, 0, frames=56))
            self.assertGreater(entry["estimate"], estimate.predict(video, 864, 480, 4, frames=124))
        finally:
            bench.release("video-file")
        bench.wait_idle()

    def test_status_sends_the_video_coefficients(self):
        by_key = call("GET", "/api/status")[1]["model_estimates"]
        self.assertEqual(by_key["video"], S.store.coefficients(S.backend, "h3-video", S.engine, "video"))
        self.assertEqual((by_key["video"]["kv"], by_key["video"]["rw"], by_key["video"]["rmin"]), (False, 1, 0))


class PrivateVideoAheadTest(VideoCase):
    """Vu de l'espace public, une vidéo privée placée devant compte comme une image de Qwen de sa taille (une seule
    image, sans les siennes) : l'ahead ne dit pas qu'elle est une vidéo."""

    def test_a_private_video_counts_as_one_qwen_image_in_the_public_ahead(self):
        session = bench.create_private("Mot2passe!")
        a = bench.generate("SLOW=1 zve4 public", steps=20)["id"]
        wait_job(a, ("running",))
        code, p = call("POST", "/api/generate", gen_body("zve4 secrète", private=True, **{**VIDEO, "frames": 124}),
                       private=session)
        self.assertEqual(code, 202, p)
        n = bench.generate("zve4 public waiting")["id"]
        s = call("GET", "/api/status")[1]
        ahead = next(e["ahead"] for e in s["queue"] if e["id"] == n)
        self.assertAlmostEqual(ahead, estimate.predict(s["estimates"], 480, 288, 4), delta=0.2)
        self.assertGreater(abs(estimate.predict(s["estimates"], 480, 288, 4, frames=124) - ahead), 1,
                           "cas qui ne distingue pas une image d'une vidéo")
        for jid in (a, n):
            wait_job(jid)
        self.assertEqual(wait_job(p["id"], private=session)["status"], "done")


class VideoCalibrationTest(VideoCase):
    """tools/calibrate.py --model video : deux vidéos de 480×288 (56 et 124 images), en 4 étapes, mesurées sous
    h3-video ; les autres clés intactes."""

    def test_calibrating_the_video_measures_its_two_videos(self):
        saved = (S.cfg, S.backend, S.model, S.engine, S.store, dict(launch.MODELS))
        before, old = samples(), set(os.listdir(launch.P("jobs")))
        argv = ["calibrate.py", "--backend", S.backend, "--model", "video", "--steps", "2"]
        out, umask = io.StringIO(), os.umask(0o022)
        os.umask(umask)
        try:
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
                calibrate.main()
        finally:
            S.cfg, S.backend, S.model, S.engine, S.store, models = saved
            launch.MODELS.update(models)
            os.umask(umask)
        self.assertIn("[calibration] terminée", out.getvalue())
        self.assertNotIn("512×512", out.getvalue())
        key = f"{S.backend}/h3-video"
        added = samples()[key][len(before.get(key, [])):]
        self.assertEqual([(x["w"], x["h"], x["F"], x["steps"]) for x in added], [(480, 288, 56, 4), (480, 288, 124, 4)])
        others = lambda d: {k: v for k, v in d.items() if k != key}
        self.assertEqual(others(samples()), others(before))
        runs = sorted(set(os.listdir(launch.P("jobs"))) - old)          # dossiers des deux vidéos de calibration
        self.assertEqual(len(runs), 2, runs)
        made = [n for d in runs for n in os.listdir(launch.P("jobs", d))]
        self.assertIn("calibration.webp", made)
        self.assertNotIn("calibration.png", made)


if __name__ == "__main__":
    unittest.main()
