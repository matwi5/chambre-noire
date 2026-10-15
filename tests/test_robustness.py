"""Une demande invalide est refusée, une génération qui ne peut pas se préparer échoue seule : la file continue."""
import os, threading, time, unittest
from unittest import mock

import bench
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

    def test_unreadable_incognito_reference_leaves_nothing(self):
        bad = generate("make it blue", mode="edit", incognito=True, ref_images=["data:image/png;base64,!!!"])["id"]
        self.assertEqual(wait_job(bad)["status"], "failed")
        bench.wait_idle()
        self.assertEqual(bench.files("jobs", "incognito_*"), [])
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
    def test_cancel_while_inputs_are_prepared_stops_the_engine_at_once(self):
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
            t0 = time.time()
            bench.wait_idle()
        self.assertLess(time.time() - t0, 5)       # le moteur n'a pas tourné ses 20 s
        self.assertEqual(bench.job(jid)["status"], "cancelled")
        self.assertEqual(bench.files("outputs", "*.png"), [])
        self.assertEqual(bench.files("jobs", jid), [])


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

    def test_cancelling_a_finished_incognito_generation_keeps_its_image(self):
        jid = generate("secret", incognito=True)["id"]
        wait_job(jid)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "done")
        self.assertEqual(call("GET", f"/api/job/{jid}/result")[0], 200)


if __name__ == "__main__":
    unittest.main()
