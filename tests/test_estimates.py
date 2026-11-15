"""Estimations de durée par modèle (ticket 06 de MiniMax H3) : valeurs de départ de MiniMax H3 tirées de l'essai,
formule de sa famille (sans cache de préfixe, références portées à 1024 px et comptées deux fois dans une étape),
mesures rangées sous la clé de version de chaque génération sans toucher à celles de Qwen, coefficients de chaque
modèle installé dans /api/status, estimation de la file selon le modèle, travail privé compté comme Qwen dans l'ahead
vu de l'espace public, calibration de MiniMax H3 par tools/calibrate.py. Sur le banc à faux moteur (voir bench.py)."""
import contextlib, glob, io, json, os, sys, tempfile, unittest
from unittest import mock

import bench
from bench import S, call, gen_body, generate, wait_job

launch, estimate = bench.launch, bench.estimate
import calibrate  # noqa: E402  (tools/ est dans le chemin par bench)

H3 = {"model": "h3", "steps": 6}
MP = 1024 * 1024
H3_METAL = {**estimate.H3_PRIORS["metal"], "kv": False, "rw": 2, "rmin": 1024}


class H3FormulaTest(unittest.TestCase):
    """Valeurs de départ de MiniMax H3 sur Metal : elles redonnent les durées de l'essai (RESULTATS de la mission) à
    10 % près."""

    def test_the_priors_redo_the_essay_durations(self):
        ref = estimate.ref_px(1024, 1024, 1024, 1024, 1024)
        cases = [("r1 texte → image 1024²", 71.6, (1024, 1024, 6)),
                 ("r2 texte → image 2048²", 239.8, (2048, 2048, 6)),
                 ("r3 édition, une référence, 3 aperçus", 429.5, (1024, 1024, 6, [ref], 0, 3)),
                 ("r26 édition, deux références", 749.4, (1024, 1024, 6, [ref, ref]))]
        for name, measured, args in cases:
            with self.subTest(name):
                self.assertAlmostEqual(estimate.predict(H3_METAL, *args) / measured, 1, delta=0.1)

    def test_a_reference_is_raised_to_1024_pixels_for_h3_only(self):
        self.assertEqual(estimate.ref_px(512, 512, 512, 512, 1024), MP)
        self.assertEqual(estimate.ref_px(2048, 1024, 512, 512, 1024), 2048 * 1024)   # petit côté porté à 1024
        self.assertEqual(estimate.ref_px(512, 512, 512, 512), 512 * 512)             # Qwen : surface de la sortie
        self.assertEqual(estimate.ref_px(1536, 1536, 1024, 1024, 1024), MP)          # déjà assez grande : inchangée

    def test_an_h3_sample_counts_each_reference_twice_without_prefix_cache(self):
        job = {"req": {"width": 1024, "height": 1024, "steps": 6}, "encode_seconds_net": 54.5,
               "sampling_seconds": 150.0, "vae_seconds": 1.4, "venc_seconds": 215.0, "seconds": 429.5,
               "ref_px": [MP], "step_times": {}}
        h3 = estimate.make_sample(job, "master-1090-8b1e9df", "h3")
        qwen = estimate.make_sample(job, "master-1090-8b1e9df")
        self.assertEqual((h3["kv"], h3["n"], h3["R"]), (False, 12.0, round(MP / 1e6, 4)))
        self.assertEqual((qwen["kv"], qwen["n"]), (True, 8.0))               # Qwen : inchangé

    def test_qwen_coefficients_keep_their_fields(self):
        with tempfile.TemporaryDirectory() as d:
            store = estimate.Store(os.path.join(d, "calibration.json"))
            c = store.coefficients("metal", "q4", "master-1090-8b1e9df")
            self.assertEqual(c, estimate.fit([], estimate.PRIORS["metal"], True))
            self.assertNotIn("rw", c)
            h3 = store.coefficients("metal", "h3-q4", "master-1090-8b1e9df", "h3")
            self.assertEqual({k: h3[k] for k in ("a", "b", "e0", "kv", "rw", "rmin")},
                             {"a": 1.4596, "b": 0.03871, "e0": 25.0, "kv": False, "rw": 2, "rmin": 1024})


class StoreKeepsQwenTest(unittest.TestCase):
    """Une mesure de MiniMax H3 s'ajoute sous sa clé de version ; celles de Qwen restent telles quelles."""

    def test_adding_an_h3_sample_leaves_the_qwen_samples_as_they_were(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "calibration.json")
            qwen = {"metal/uc-q8": [{"w": 512, "h": 512, "step": 2.9, "sd": "master-959-d637cfb"}],
                    "metal/q4": [{"w": 768, "h": 768, "step": 5.1}]}
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "samples": qwen}, f)
            estimate.Store(path).add("metal", "h3-q4", {"w": 1024, "h": 1024, "step": 6.2})
            saved = json.load(open(path, encoding="utf-8"))
            self.assertEqual(saved["version"], 2)
            self.assertEqual({k: v for k, v in saved["samples"].items() if k != "metal/h3-q4"}, qwen)
            self.assertEqual(saved["samples"]["metal/h3-q4"], [{"w": 1024, "h": 1024, "step": 6.2}])


def samples():
    return S.store.read()


class H3SamplesTest(bench.BenchCase):
    def test_an_h3_generation_records_its_sample_under_its_version(self):
        before = samples()
        self.assertEqual(wait_job(generate("zes1 h3", width=384, height=256, **H3)["id"])["status"], "done")
        after = samples()
        key = f"{S.backend}/h3-q4"
        self.assertEqual((after[key][-1]["w"], after[key][-1]["h"], after[key][-1]["kv"]), (384, 256, False))
        self.assertEqual({k: v for k, v in after.items() if k != key}, {k: v for k, v in before.items() if k != key})

    def test_an_h3_edit_sample_counts_its_reference_raised_and_twice(self):
        ref = bench.data_url(bench.png_bytes(64, 48))
        j = wait_job(generate("zes1 édition", mode="edit", ref_images=[ref], **H3)["id"])
        self.assertEqual(j["status"], "done", j)
        last = samples()[f"{S.backend}/h3-q4"][-1]
        px = estimate.ref_px(64, 48, 512, 512, 1024)
        self.assertEqual(px, 1376 * 1024)
        self.assertEqual((last["R"], last["n"]), (round(px / 1e6, 4), round((512 * 512 + 2 * px) / 262144, 4)))


class StatusEstimatesTest(bench.BenchCase):
    def test_status_sends_the_estimates_of_each_installed_model(self):
        s = call("GET", "/api/status")[1]
        by_key = s["model_estimates"]
        self.assertEqual(sorted(by_key), sorted(m["key"] for m in s["models"]))
        self.assertEqual(by_key["qwen"], s["estimates"])                      # les champs d'aujourd'hui : Qwen
        self.assertEqual(s["estimates"], S.store.coefficients(S.backend, S.model, S.engine))
        self.assertEqual((by_key["h3"]["rw"], by_key["h3"]["rmin"], by_key["h3"]["kv"]), (2, 1024, False))
        self.assertEqual(by_key["h3"], S.store.coefficients(S.backend, "h3-q4", S.engine, "h3"))

    def test_the_queue_estimates_an_h3_generation_with_its_coefficients(self):
        a = generate("HOLD=estimations zes2 qwen")["id"]
        wait_job(a, ("running",))
        b = generate("zes2 h3", preview=True, **H3)["id"]
        s = call("GET", "/api/status")[1]
        h3 = s["model_estimates"]["h3"]
        entry = next(e for e in s["queue"] if e["id"] == b)
        self.assertEqual([e["model"] for e in s["queue"] if e["id"] in (a, b)], ["qwen", "h3"])   # suivi par la page
        self.assertAlmostEqual(entry["estimate"], estimate.predict(h3, 512, 512, 6, [], 0, 3), delta=0.1)
        bench.release("estimations")
        wait_job(b)


class PrivateAheadTest(bench.BenchCase):
    """Vu de l'espace public, une génération privée de MiniMax H3 placée devant compte comme une génération de Qwen
    (coefficients, références, aperçus de la demande) : l'ahead ne dit pas son modèle."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private("Mot2passe!")

    def test_a_private_h3_generation_counts_as_qwen_in_the_public_ahead(self):
        key = f"{S.backend}/h3-q4"
        kept = samples().get(key, [])
        a = generate("SLOW=1 zes3 public", steps=20)["id"]
        wait_job(a, ("running",))
        ref = bench.data_url(bench.png_bytes(64, 48))
        body = gen_body("zes3 secret", private=True, mode="edit", ref_images=[ref], preview=True, **H3)
        code, p = call("POST", "/api/generate", body, private=self.session)
        self.assertEqual(code, 202, p)
        n = generate("zes3 public waiting")["id"]
        s = call("GET", "/api/status")[1]
        qwen = s["estimates"]
        as_qwen = estimate.predict(qwen, 512, 512, 6, [estimate.ref_px(64, 48, 512, 512)], 0, 6 // 5)
        ahead = next(e["ahead"] for e in s["queue"] if e["id"] == n)
        self.assertAlmostEqual(ahead, as_qwen, delta=0.2)
        h3 = s["model_estimates"]["h3"]
        own = estimate.predict(h3, 512, 512, 6, [estimate.ref_px(64, 48, 512, 512, 1024)], 0, 3)
        self.assertGreater(abs(own - as_qwen), 1, "cas qui ne distingue pas les deux estimations")
        inside = call("GET", "/api/status", private=self.session)[1]["queue"]
        self.assertAlmostEqual(next(e["estimate"] for e in inside if e["id"] == p["id"]), own, delta=0.2)
        for jid in (a, n):
            wait_job(jid)
        self.assertEqual(wait_job(p["id"], private=self.session)["status"], "done")
        self.assertEqual(samples().get(key, []), kept, "mesure d'une génération privée")


class H3CalibrationTest(bench.BenchCase):
    """tools/calibrate.py --model h3 : trois générations MiniMax H3 (deux textes vers image, une édition à une
    référence), en 6 étapes, mesurées sous la clé de sa version ; celles de Qwen intactes."""

    def test_calibrating_h3_measures_its_three_generations(self):
        saved = (S.cfg, S.backend, S.model, S.engine, S.store, dict(launch.MODELS))
        before = samples()
        argv = ["calibrate.py", "--backend", S.backend, "--model", "h3", "--steps", "2"]
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
        key = f"{S.backend}/h3-q4"
        added = samples()[key][len(before.get(key, [])):]
        self.assertEqual([(x["w"], x["steps"], x["R"] > 0) for x in added],
                         [(1024, 6, False), (512, 6, False), (1024, 6, True)])
        others = lambda d: {k: v for k, v in d.items() if k != key}
        self.assertEqual(others(samples()), others(before))

    def calibrate(self):
        """Lance tools/calibrate.py --model h3 sur le banc ; renvoie le message de son arrêt (None : fini) et sa
        sortie."""
        saved = (S.cfg, S.backend, S.model, S.engine, S.store, dict(launch.MODELS))
        argv = ["calibrate.py", "--backend", S.backend, "--model", "h3"]
        out, umask = io.StringIO(), os.umask(0o022)
        os.umask(umask)
        try:
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
                calibrate.main()
            stop = None
        except SystemExit as e:
            stop = str(e.code)
        finally:
            S.cfg, S.backend, S.model, S.engine, S.store, models = saved
            launch.MODELS.update(models)
            os.umask(umask)
        return stop, out.getvalue()

    def test_an_unreadable_file_is_set_aside_and_the_calibration_goes_on(self):
        kept = open(launch.CALIB, "rb").read() if os.path.exists(launch.CALIB) else None

        def restore():
            if kept is None:
                os.remove(launch.CALIB)
            else:
                with open(launch.CALIB, "wb") as f:
                    f.write(kept)
        self.addCleanup(restore)
        with open(launch.CALIB, "w", encoding="utf-8") as f:
            f.write("{abîmé")
        stop, out = self.calibrate()
        aside = glob.glob(launch.CALIB + ".illisible-*")
        self.addCleanup(lambda: [os.remove(f) for f in aside])
        self.assertEqual((stop, len(samples()[f"{S.backend}/h3-q4"])), (None, 3), out)
        self.assertEqual([open(f, encoding="utf-8").read() for f in aside], ["{abîmé"])

    def test_a_lost_sample_makes_the_calibration_fail(self):
        with mock.patch.object(estimate.Store, "add", side_effect=TimeoutError("verrou tenu")):
            stop, out = self.calibrate()
        self.assertIn("non gardée", stop or "")
        self.assertNotIn("terminée", out)


# un processus qui ajoute N mesures sous sa propre clé (StoreLockTest) : python - <fichier> <clé> <N>
ADDER = """import os, sys
sys.path.insert(0, {tools!r})
import estimate
store = estimate.Store(sys.argv[1])
for i in range(int(sys.argv[3])):
    store.add("metal", sys.argv[2], {{"i": i}})
"""


class StoreLockTest(unittest.TestCase):
    """Le serveur et tools/calibrate.py écrivent le même fichier : chaque ajout se fait sous un verrou entre processus,
    et rien n'est écrit quand le fichier est illisible ou que le verrou ne vient pas (mesures gardées jamais
    perdues)."""

    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = os.path.join(d.name, "calibration.json")
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "samples": {"metal/uc-q8": [{"step": 2.9}]}}, f)

    def test_two_processes_adding_at_once_lose_no_sample(self):
        import subprocess
        code = ADDER.format(tools=os.path.dirname(estimate.__file__))
        procs = [subprocess.Popen([sys.executable, "-c", code, self.path, k, "30"]) for k in ("q4", "h3-q4")]
        self.assertEqual([p.wait(timeout=60) for p in procs], [0, 0])
        saved = json.load(open(self.path, encoding="utf-8"))["samples"]
        self.assertEqual({k: len(v) for k, v in saved.items()}, {"metal/uc-q8": 1, "metal/q4": 30, "metal/h3-q4": 30})

    def aside(self):
        d = os.path.dirname(self.path)
        return sorted(os.path.join(d, f) for f in os.listdir(d) if ".illisible-" in f)

    def test_an_unreadable_file_is_set_aside_and_a_new_one_started(self):
        for content in (b'{"version": 2, "samples": {"metal/uc-q8": [', b"\xff\xfe pas de l'UTF-8", b"[1, 2]",
                        b'{"version": 2, "samples": [1]}'):
            with self.subTest(content=content):
                for f in self.aside():
                    os.remove(f)
                with open(self.path, "wb") as f:
                    f.write(content)                               # écriture coupée, ou fichier abîmé
                estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
                [aside] = self.aside()
                self.assertEqual(open(aside, "rb").read(), content)   # gardé tel quel, jamais supprimé
                self.assertEqual(estimate.Store(self.path).samples, {"metal/h3-q4": [{"step": 6.2}]})

    def test_a_file_already_set_aside_this_second_stops_the_sample(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{abîmé")
        with mock.patch.object(estimate.time, "strftime", return_value="20261114-120000"):
            with open(self.path + ".illisible-20261114-120000", "w", encoding="utf-8") as f:
                f.write("{déjà")
            with self.assertRaises(estimate.Unreadable):
                estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
        self.assertEqual(open(self.path, encoding="utf-8").read(), "{abîmé")
        self.assertEqual(open(self.path + ".illisible-20261114-120000", encoding="utf-8").read(), "{déjà")

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "droits POSIX, compte ordinaire")
    def test_a_file_the_disk_refuses_is_neither_moved_nor_overwritten(self):
        kept = open(self.path, "rb").read()
        os.chmod(self.path, 0)
        self.addCleanup(os.chmod, self.path, 0o600)
        with self.assertRaises(PermissionError):
            estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
        os.chmod(self.path, 0o600)
        self.assertEqual((open(self.path, "rb").read(), self.aside()), (kept, []))

    def test_a_held_lock_writes_nothing_then_lets_the_sample_in(self):
        store = estimate.Store(self.path)
        kept = open(self.path, "rb").read()
        with estimate.file_lock(self.path + ".lock"), mock.patch.object(estimate, "LOCK_WAIT", 0.2):
            with self.assertRaises(TimeoutError):
                store.add("metal", "h3-q4", {"step": 6.2})
            self.assertEqual(open(self.path, "rb").read(), kept)
        store.add("metal", "h3-q4", {"step": 6.2})
        self.assertEqual(store.read()["metal/h3-q4"], [{"step": 6.2}])
        self.assertEqual(store.read()["metal/uc-q8"], [{"step": 2.9}])

    def test_a_newer_format_is_never_overwritten(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"version": 3, "samples": {"metal/uc-q8": [{"step": 2.9}]}}, f)
        kept = open(self.path, "rb").read()
        with self.assertRaises(ValueError):
            estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
        self.assertEqual((open(self.path, "rb").read(), self.aside()), (kept, []))

    def test_a_failed_write_keeps_the_file_and_leaves_no_temporary(self):
        kept = open(self.path, "rb").read()
        for failure in (OSError("disque plein"), KeyboardInterrupt()):
            for at in ("json.dump", "os.replace"):
                with self.subTest(failure=type(failure).__name__, at=at):
                    store = estimate.Store(self.path)
                    target = estimate.json if at == "json.dump" else estimate.os
                    with mock.patch.object(target, at.split(".")[1], side_effect=failure), \
                            self.assertRaises(type(failure)):
                        store.add("metal", "h3-q4", {"step": 6.2})
                    self.assertEqual(open(self.path, "rb").read(), kept)
                    self.assertEqual(store.samples, {"metal/uc-q8": [{"step": 2.9}]})
                    left = [f for f in os.listdir(os.path.dirname(self.path)) if f.endswith(".tmp")]
                    self.assertEqual(left, [])

    def test_the_file_is_on_disk_before_its_rename(self):
        calls, real_replace = [], os.replace
        with mock.patch.object(estimate, "sync_fd", side_effect=lambda fd: calls.append("sync")), \
                mock.patch.object(estimate.os, "replace", side_effect=lambda a, b: (calls.append("replace"),
                                                                                    real_replace(a, b))):
            estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
        self.assertEqual(calls, ["sync", "replace", "sync"])        # le fichier, le renommage, puis son dossier

    @unittest.skipIf(estimate.fcntl is None, "flock : macOS et Linux")
    def test_a_filesystem_without_lock_still_records(self):
        import errno
        with mock.patch.object(estimate.fcntl, "flock", side_effect=OSError(errno.ENOTSUP, "non pris en charge")):
            estimate.Store(self.path).add("metal", "h3-q4", {"step": 6.2})
        self.assertEqual(estimate.Store(self.path).samples["metal/h3-q4"], [{"step": 6.2}])


class FamiliesTest(unittest.TestCase):
    def test_each_model_of_the_table_has_its_family(self):
        # sans famille, /api/status (model_estimates) et l'estimation de la file lèveraient pour ce modèle
        self.assertEqual(sorted(estimate.FAMILIES), sorted(launch.MODEL_TABLE))


if __name__ == "__main__":
    unittest.main()
