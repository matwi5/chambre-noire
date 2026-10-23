"""Une demande invalide est refusée, une génération qui ne peut pas se préparer échoue seule : la file continue."""
import contextlib, io, os, sys, threading, time, unittest
from unittest import mock

import bench
import calibrate
from bench import call, gen_body, generate, wait_job


class ValidationTest(bench.BenchCase):
    def refused(self, **kw):
        """Envoie une demande modifiée par kw (valeur ... : champ retiré) ; vérifie le refus et renvoie son motif."""
        body = gen_body()
        body.update(kw)
        for k in [k for k, v in kw.items() if v is ...]:
            del body[k]
        code, reply = call("POST", "/api/generate", body)
        self.assertEqual(code, 400, reply)
        return reply["error"]

    def test_invalid_numbers_are_refused(self):
        self.assertIn("largeur", self.refused(width=...))
        self.assertIn("étapes", self.refused(steps="vingt"))
        self.assertIn("hauteur", self.refused(height=10_000))
        self.assertIn("hauteur", self.refused(height=512.5))
        self.assertIn("graine", self.refused(seed="42"))
        self.assertIn("étapes", self.refused(steps=True))

    def test_prompt_must_be_text(self):
        self.assertIn("prompt", self.refused(prompt=["a", "list"]))
        self.assertIn("prompt", self.refused(prompt="   "))

    def test_image_fields_must_be_text(self):
        self.assertIn("ref_images", self.refused(ref_images="data:image/png;base64,AAAA"))
        self.assertIn("init_image", self.refused(init_image=12))
        self.assertIn("cfg", self.refused(cfg=float("nan")))

    def test_nothing_is_queued_when_refused(self):
        self.refused(width=...)
        self.assertEqual(bench.S.jobs, {})

    def test_valid_request_without_seed_is_accepted(self):
        body = gen_body()
        del body["seed"]
        code, j = call("POST", "/api/generate", body)
        self.assertEqual(code, 202)
        self.assertEqual(wait_job(j["id"])["status"], "done")


class PreparationFailureTest(bench.BenchCase):
    def test_unreadable_reference_fails_alone_and_the_queue_goes_on(self):
        bad = generate("make it blue", mode="edit", ref_images=["data:image/png;base64,bm90IGFuIGltYWdl"])["id"]
        good = generate("a red car")["id"]
        j = wait_job(bad)
        self.assertEqual(j["status"], "failed")
        self.assertIn("illisible", j["error"])
        self.assertEqual(wait_job(good)["status"], "done")

    def test_unreadable_private_reference_leaves_nothing(self):
        session = bench.create_private("Mot2passe!")
        code, reply = call("POST", "/api/generate", gen_body("make it blue", mode="edit", private=True,
                                                             ref_images=["data:image/png;base64,!!!"]), private=session)
        self.assertEqual(code, 202, reply)
        self.assertEqual(wait_job(reply["id"], private=session)["status"], "failed")
        bench.wait_idle()
        self.assertEqual(bench.files("jobs", "*"), [])
        self.assertFalse(any("make it blue" in line for line in bench.LOG))
        self.assertEqual(wait_job(generate("next one")["id"])["status"], "done")

    def test_unreadable_mask_fails_with_a_readable_message(self):
        image = bench.data_url(bench.png_bytes())
        for mask in ("data:image/png;base64,abc", "data:image/png;base64,AAAA"):   # base64 invalide, puis pas une image
            j = wait_job(generate("fill it", mode="mask", init_image=image, mask_image=mask)["id"])
            self.assertEqual((j["status"], j["error"]), ("failed", "génération impossible : masque illisible"))

    def test_failure_is_notified(self):
        with bench.capture_push() as sent:
            wait_job(generate("make it blue", mode="edit", ref_images=["data:image/png;base64,bm9u"])["id"])
            sent.wait(1)
        self.assertEqual(sent[0]["title"], "Échec de la génération")


class CancelDuringPreparationTest(bench.BenchCase):
    def test_cancel_while_inputs_are_prepared_does_not_start_the_engine(self):
        preparing, cancelled, real = threading.Event(), threading.Event(), bench.launch.build_cmd

        def slow_build(job):                    # préparation longue (grosses images d'entrée), jusqu'à l'annulation
            preparing.set()
            cancelled.wait(5)
            return real(job)
        with mock.patch.object(bench.launch, "build_cmd", slow_build):
            jid = generate("SLOW=1 long one", steps=20)["id"]
            self.assertTrue(preparing.wait(5))
            self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "cancelled")
            cancelled.set()
            bench.wait_idle()
        done = bench.job(jid)
        self.assertEqual((done["status"], done["seconds"]), ("cancelled", None))   # seconds : posé après le moteur
        self.assertIsNotNone(done["finished"])
        self.assertEqual(bench.files("outputs", "*.png"), [])
        self.assertEqual(bench.files("jobs", jid), [])

    def test_cancel_as_the_engine_starts_stops_it_at_once(self):
        real = bench.launch.subprocess.Popen

        started = []

        def start_then_cancel(*a, **kw):        # annulation arrivée pendant le lancement du moteur
            proc = real(*a, **kw)
            if a and str(a[0][0]).endswith(bench.launch.EXE):
                # génération lancée lue dans S.current : le thread de calcul peut arriver ici avant que la réponse
                # de /api/generate ait rendu son identifiant au test
                started.append(bench.launch.S.current)
                self.assertEqual(call("POST", f"/api/job/{started[-1]}/cancel")[1]["status"], "cancelled")
            return proc
        with mock.patch.object(bench.launch.subprocess, "Popen", start_then_cancel):
            code, reply = call("POST", "/api/generate", gen_body("HOLD=jamais long one", steps=20))
            jid = reply["id"]
            bench.wait_idle()                      # HOLD : sans l'arrêt du moteur, il ne finirait jamais
        self.assertEqual(started, [jid])
        self.assertEqual(bench.job(jid)["status"], "cancelled")
        self.assertEqual((bench.files("outputs", "*.png"), bench.files("jobs", jid)), ([], []))


class CancelAtStartTest(bench.BenchCase):
    """Annulation posée au moment où worker() vient de prendre la génération en tête de file, avant son lancement."""

    def cancel_at_start(self, body, session=None):
        """Lance la demande ; à la prise en tête de sa première génération, lit sa ligne de la file et l'annule (par
        son identifiant, que la page qui l'a lancée connaît ; session : celle de l'espace privé, pour une génération
        privée). Renvoie la réponse de /api/generate et cette ligne."""
        real, done = bench.launch.run_job, threading.Event()
        entry = cancelled = None

        def cancel_then_run(job):               # fenêtre entre le passage en cours (sous S.turn) et run_job
            nonlocal entry, cancelled
            if not done.is_set():
                queue = call("GET", "/api/status", private=session)[1]["queue"]
                entry = next((e for e in queue if e["id"] == job["id"]), None)
                cancelled = call("POST", f"/api/job/{job['id']}/cancel", private=session)[1]
                done.set()
            return real(job)
        with mock.patch.object(bench.launch, "run_job", cancel_then_run):
            code, reply = call("POST", "/api/generate", body, private=session)
            self.assertEqual(code, 202, reply)
            self.assertTrue(done.wait(10), "génération jamais prise en tête")
            bench.wait_idle()
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIsNotNone(entry, "ligne de la génération absente de la file")
        return reply, entry

    def assert_never_computed(self, jid, session=None):
        j = bench.job(jid, session)
        self.assertEqual((j["status"], j["seconds"]), ("cancelled", None))   # seconds : posé après le moteur
        self.assertIsNotNone(j["finished"])

    def test_cancel_as_a_lot_image_starts_stops_it_and_notifies_the_lot_once(self):
        with bench.capture_push() as sent:
            reply, entry = self.cancel_at_start(gen_body("lot", count=2))
            first, second = reply["jobs"]
            self.assertEqual((entry["status"], entry["position"]), ("running", 0))   # plus de « 0e en attente »
            self.assert_never_computed(first["id"])
            self.assertEqual(bench.job(second["id"])["status"], "done")
            self.assertEqual(len(sent.decided), 1, sent.decided)
        self.assertEqual(len(bench.files("outputs", "*.png")), 1)
        self.assertEqual(bench.files("jobs", first["id"]), [])
        self.assertEqual([e.get("seed") for e in bench.journal()], [bench.job(second["id"])["seed"]])

    def test_cancel_as_a_private_generation_starts_leaves_nothing(self):
        session = bench.create_private("Mot2passe!")
        bench.LOG.clear()
        reply, entry = self.cancel_at_start(gen_body("zq9secret", private=True), session)
        self.assertEqual(entry["status"], "running")
        self.assert_never_computed(reply["id"], session)
        self.assertEqual((bench.files("outputs", "*"), bench.files("jobs", "*"), bench.journal()), ([], [], []))
        # requêtes réussies tues, annulation sans ligne : rien au journal (hors notifications d'un test précédent)
        self.assertEqual([line for line in bench.LOG if not line.startswith("[push]")], [])


class RankWhileFinishingTest(bench.BenchCase):
    def test_next_generation_stays_first_in_line_while_the_previous_one_is_put_away(self):
        real, seen = bench.launch.notify_job, []

        def look_then_notify(job):              # fin de génération : statut done, S.current encore posé
            seen.extend(e for e in call("GET", "/api/status")[1]["queue"] if e.get("id") == second)
            return real(job)
        with mock.patch.object(bench.launch, "notify_job", look_then_notify):
            first = generate("HOLD=rang first")["id"]
            wait_job(first, ("running",))
            second = generate("second")["id"]
            bench.release("rang")
            wait_job(second)
            bench.wait_idle()
        self.assertTrue(seen, "seconde génération absente de la file pendant le rangement de la première")
        self.assertEqual((seen[0]["status"], seen[0]["position"]), ("queued", 1))   # jamais « 0e en attente »


class CalibrationTest(bench.BenchCase):
    """tools/calibrate.py lance ses trois générations par run_job, hors de la file (sur le faux moteur)."""

    def test_calibration_runs_its_three_generations(self):
        S, launch = bench.S, bench.launch
        saved = (S.cfg, S.backend, S.model, S.engine, S.store, dict(launch.MODELS))
        argv = ["calibrate.py", "--backend", S.backend, "--model", "q4", "--steps", "2"]
        out = io.StringIO()
        try:
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
                calibrate.main()                   # échec : sys.exit, qui fait échouer le test avec son message
        finally:
            S.cfg, S.backend, S.model, S.engine, S.store, models = saved
            launch.MODELS.update(models)
        self.assertIn("[calibration] terminée", out.getvalue())


class CancelFinishedTest(bench.BenchCase):
    def test_cancelling_a_finished_generation_changes_nothing(self):
        jid = generate("a red car")["id"]
        done = wait_job(jid)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "done")
        bench.wait_idle()
        self.assertEqual(bench.job(jid)["status"], "done")
        self.assertTrue(os.path.isfile(done["path"]))

    def test_cancelling_a_failed_generation_changes_nothing(self):
        jid = generate("FAIL")["id"]
        wait_job(jid)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "failed")

    def test_cancelling_twice_changes_nothing(self):
        a, b = generate("SLOW running")["id"], generate("waiting")["id"]
        call("POST", f"/api/job/{b}/cancel")
        self.assertEqual(call("POST", f"/api/job/{b}/cancel")[1]["status"], "cancelled")
        self.assertEqual(wait_job(a)["status"], "done")


if __name__ == "__main__":
    unittest.main()
