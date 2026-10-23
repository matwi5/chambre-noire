"""Générations privées et galerie privée : session exigée au lancement, image et tout ce qui s'y rattache chiffrés sur le
disque (aucun octet en clair nulle part), lisibles avec la session seulement, gardés même si l'espace se verrouille
avant la fin."""
import glob, os, time, unittest
from unittest import mock

import bench
from bench import call, files, wait_job

CODE = "Mot2passe!"


class PrivateGenerationTest(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def generate(self, prompt="zq9private secret prompt", session=None, **kw):
        code, job = call("POST", "/api/generate", bench.gen_body(prompt, private=True, **kw), private=session or self.session)
        self.assertEqual(code, 202, job)
        return job

    def wait_job(self, jid, *args, **kw):
        """Suivi d'une génération (privée : avec la session de l'espace)."""
        return wait_job(jid, *args, private=self.session, **kw)

    def pile(self, session=None):
        """Pile de l'espace privé : où arrive une génération privée terminée."""
        code, items = call("GET", "/api/private/pile", private=session or self.session)
        self.assertEqual(code, 200, items)
        return items

    def test_private_generation_needs_a_session(self):
        self.assertEqual(call("POST", "/api/generate", bench.gen_body("x", private=True))[0], 403)
        self.assertEqual(job_count(), 0)

    def test_nothing_in_clear_on_disk_after_a_private_generation(self):
        ref, calib_before = bench.png_bytes(80, 60), calibration()
        job = self.generate(mode="edit", ref_images=[bench.data_url(ref)], preview=True, steps=10)
        self.assertRegex(job["id"], r"^[0-9a-f]{32}$")
        self.assertTrue(job["private"])
        done = self.wait_job(job["id"])
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["path"])
        bench.wait_idle()
        [item] = self.pile()
        code, png = call("GET", f"/api/private/image?id={item['id']}", private=self.session)
        self.assertEqual((code, png[:4]), (200, b"\x89PNG"))
        code, thumb = call("GET", f"/api/private/thumb?id={item['id']}", private=self.session)
        self.assertEqual((code, thumb[:2]), (200, b"\xff\xd8"))
        code, inp = call("GET", f"/api/private/input?id={item['id']}&file=ref_1.png", private=self.session)
        self.assertEqual((code, inp), (200, ref))
        # aucun octet de l'image, de sa miniature, de son entrée ni du prompt, nulle part sur le disque
        clear_bytes = [png[len(png) // 2:len(png) // 2 + 64], thumb[len(thumb) // 2:len(thumb) // 2 + 64],
                    ref[len(ref) // 2:len(ref) // 2 + 64], b"zq9private"]
        for fp in bench.all_files():
            raw = open(fp, "rb").read()
            for s in clear_bytes:
                self.assertNotIn(s, raw, fp)
        self.assertEqual(files("outputs", "*.png"), [])
        self.assertEqual(bench.journal(), [])
        self.assertEqual(files("jobs", "*"), [])
        self.assertEqual(calibration(), calib_before)
        self.assertFalse([line for line in bench.LOG if "zq9private" in line or job["id"] in line])

    def test_reference_the_engine_cannot_read_is_kept_as_png(self):
        # cas vu sur le téléphone : une référence WebP faisait échouer l'édition privée (« load image … failed »)
        job = self.generate(mode="edit", ref_images=[bench.data_url(bench.png_bytes(fmt="WEBP"))])
        done = self.wait_job(job["id"])
        self.assertEqual(done["status"], "done", done.get("error"))
        bench.wait_idle()
        [item] = self.pile()
        code, inp = call("GET", f"/api/private/input?id={item['id']}&file=ref_1.png", private=self.session)
        self.assertEqual((code, inp[:8]), (200, b"\x89PNG\r\n\x1a\n"))

    def test_pile_lists_settings_and_reads_need_the_session(self):
        job = self.generate("zq9 a fox", seed=1234, steps=6)
        self.wait_job(job["id"])
        [item] = self.pile()
        self.assertEqual((item["prompt"], item["mode"], item["width"], item["height"], item["steps"], item["seed"]),
                         ("zq9 a fox", "t2i", 512, 512, 6, 1234))
        self.assertEqual(item["inputs"], [])
        self.assertEqual(self.wait_job(job["id"])["item"], item["id"])
        for path in ("/api/private/history", "/api/private/pile", f"/api/private/image?id={item['id']}",
                     f"/api/private/thumb?id={item['id']}"):
            self.assertEqual(call("GET", path)[0], 403, path)
            self.assertEqual(call("GET", path, remote=True)[0], 403, path)
        other = bench.unlock_private(CODE, remote=True)          # un autre appareil, avec son propre code
        self.assertEqual(len(self.pile(other)), 1)

    def test_download_gives_an_attachment(self):
        self.wait_job(self.generate()["id"])
        [item] = self.pile()
        code, _, headers = bench.call_full("GET", f"/api/private/image?id={item['id']}&download=1", private=self.session)
        self.assertEqual(code, 200)
        self.assertIn("attachment", headers.get("Content-Disposition", ""))

    def test_generation_finished_after_locking_is_kept_and_read_after_unlocking(self):
        job = self.generate("SLOW=0.05 zq9 long one", steps=10)
        self.wait_job(job["id"], ("running",))
        call("POST", "/api/private/lock", private=self.session)
        # hors de l'espace, la page ne la suit plus ; elle continue sur le Mac
        self.assertEqual(call("GET", f"/api/job/{job['id']}", private=self.session)[0], 404)
        bench.wait_idle()
        self.assertEqual(call("GET", "/api/private/pile", private=self.session)[0], 403)
        again = bench.unlock_private(CODE)
        self.assertEqual(wait_job(job["id"], private=again)["status"], "done")
        self.assertEqual([i["prompt"] for i in self.pile(again)], ["SLOW=0.05 zq9 long one"])

    def test_delete_removes_the_image(self):
        self.wait_job(self.generate()["id"])
        [item] = self.pile()
        self.assertEqual(call("POST", "/api/private/delete", {"id": item["id"]})[0], 403)
        self.assertEqual(call("POST", "/api/private/delete", {"id": item["id"]}, private=self.session)[0], 200)
        self.assertEqual(self.pile(), [])
        self.assertEqual(call("GET", f"/api/private/image?id={item['id']}", private=self.session)[0], 404)
        self.assertEqual(files("private", "items", "*"), [])

    def test_bad_item_ids_are_refused(self):
        for bad in ("../space.json", "abc", "x" * 32):
            self.assertEqual(call("GET", f"/api/private/image?id={bad}", private=self.session)[0], 404)

    def test_public_space_sees_nothing_of_a_private_generation(self):
        job = self.generate("SLOW=0.1 zq9marker", steps=10, page="pagePriv1")
        self.wait_job(job["id"], ("running",))
        # autre appareil hors de l'espace, ou cet appareil par http:// sur le Wi-Fi malgré sa session : ni ligne, ni
        # génération en cours, ni rien qui trahisse l'espace privé ; seul busy dit que le Mac calcule
        for s in (call("GET", "/api/status", remote=True)[1], call("GET", "/api/status", wifi=True, private=self.session)[1]):
            self.assertEqual((s["queue"], s["queued"], s["current_job"], s["busy"]), ([], 0, None, True))
            self.assertFalse(s["private"]["unlocked"])
            self.assertNotIn(job["id"], str(s))
            self.assertNotIn("zq9marker", str(s))
            self.assertNotIn("pagePriv1", str(s))
        self.wait_job(job["id"])
        self.assertIsNone(call("GET", "/api/status")[1]["last_job"])

    def test_failed_private_generation_leaves_nothing(self):
        job = self.generate("FAIL zq9private")
        self.assertEqual(self.wait_job(job["id"])["status"], "failed")
        bench.wait_idle()
        self.assertEqual(files("jobs", "*"), [])
        self.assertEqual(self.pile(), [])
        self.assertFalse([line for line in bench.LOG if "zq9private" in line])

    def test_notification_is_the_same_as_for_a_normal_image(self):
        with bench.capture_push() as sent:
            self.wait_job(self.generate()["id"])
            sent.wait(1)
            self.wait_job(call("POST", "/api/generate", bench.gen_body("a normal image"))[1]["id"])
            sent.wait(2)
        private, normal = sent
        self.assertEqual(private["title"], "Image prête")
        self.assertEqual(sorted(private), sorted(normal))
        self.assertRegex(private["body"], r"^Générée en \d+ s · 512×512$")
        self.assertNotIn("zq9", str(private))
        self.assertNotIn("priv", str(private).lower())

    def test_page_can_forget_a_finished_private_generation(self):
        job = self.generate()
        self.wait_job(job["id"])
        self.assertEqual(call("POST", f"/api/job/{job['id']}/forget", {}, private=self.session)[0], 200)
        self.assertEqual(call("GET", f"/api/job/{job['id']}", private=self.session)[0], 404)
        self.assertEqual(len(self.pile()), 1)              # l'image reste dans l'espace privé

    def test_a_finished_private_generation_its_page_never_forgot_is_forgotten_after_the_delay(self):
        with mock.patch("launch.PRIVATE_JOB_TTL", 0.4):
            done = self.generate("never forgotten")["id"]
            failed = self.generate("FAIL never seen")["id"]
            self.assertEqual(self.wait_job(done)["status"], "done")
            self.assertEqual(self.wait_job(failed)["status"], "failed")
            # chaque requête fait le ménage (sweep) : on interroge jusqu'à l'oubli, passé le délai
            bench.wait_until(lambda: all(call("GET", f"/api/job/{jid}", private=self.session)[0] == 404
                                         for jid in (done, failed)), what="générations privées oubliées")
            self.assertNotIn(done, bench.S.jobs)
        self.assertEqual(len(self.pile()), 1)              # l'image reste dans l'espace privé

    def test_a_running_or_waiting_private_generation_is_not_expired(self):
        with mock.patch("launch.PRIVATE_JOB_TTL", 0.1):
            running = self.generate("HOLD long")["id"]
            waiting = self.generate("waiting")["id"]
            job = lambda: bench.S.jobs[running]   # en cours depuis plus que le délai, sans être oubliée
            bench.wait_until(lambda: job().get("status") == "running" and time.time() - job()["created"] > 0.2,
                             what="génération en cours depuis plus que le délai")
            for jid in (running, waiting):
                self.assertEqual(call("GET", f"/api/job/{jid}", private=self.session)[0], 200)
        # délai rendu avant la fin : avec 0,1 s, la génération finie serait oubliée entre deux interrogations
        bench.release()
        self.assertEqual(self.wait_job(running)["status"], "done")
        self.assertEqual(self.wait_job(waiting)["status"], "done")

    def test_reset_during_generation_discards_the_image(self):
        job = self.generate("SLOW=0.05 zq9 reset", steps=10)
        self.wait_job(job["id"], ("running",))
        call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})
        self.session = bench.create_private("Un-autre-code")      # espace recréé : seule session qui suit encore
        self.assertEqual(self.wait_job(job["id"])["status"], "failed")
        self.assertEqual(files("private", "items", "*"), [])


class PrivateTrackingTest(bench.PrivateFilesCheck, bench.BenchCase):
    """Suivi, aperçu et annulation d'une génération ou d'un lot privés : requête sûre et session exigées, sinon la
    réponse d'un identifiant inconnu (404), qui ne dit pas que la génération existe."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def launch(self, prompt="SLOW=0.05 zq9 tracked", **kw):
        code, reply = call("POST", "/api/generate", bench.gen_body(prompt, private=True, **kw), private=self.session)
        self.assertEqual(code, 202, reply)
        return reply

    def outsiders(self):
        """Requêtes hors de l'espace privé : le Mac sans session, un autre appareil sans session, cet appareil par
        http:// sur le Wi-Fi malgré sa session, et une session fermée."""
        closed = bench.unlock_private(CODE, remote=True)
        self.assertEqual(call("POST", "/api/private/lock", {}, remote=True, private=closed)[0], 200)
        return [{}, {"remote": True}, {"wifi": True, "private": self.session}, {"remote": True, "private": closed}]

    def test_following_a_private_generation_needs_the_private_space(self):
        job = self.launch(preview=True, steps=12)
        jid = job["id"]
        wait_job(jid, ("running",), check=lambda j: j.get("preview_version"), private=self.session)
        for who in self.outsiders():
            for method, path in (("GET", f"/api/job/{jid}"), ("GET", f"/api/job/{jid}/preview"),
                                 ("POST", f"/api/job/{jid}/cancel"), ("POST", f"/api/job/{jid}/forget")):
                code, reply = call(method, path, {} if method == "POST" else None, **who)
                self.assertEqual((code, reply), (404, {"error": "job inconnu"}), (method, path, who))
        self.assertEqual(call("GET", f"/api/job/{jid}", private=self.session)[1]["status"], "running")
        self.assertEqual(call("GET", f"/api/job/{jid}/preview", private=self.session)[0], 200)
        other = bench.unlock_private(CODE, remote=True)          # autre appareil dans l'espace
        self.assertEqual(call("GET", f"/api/job/{jid}", remote=True, private=other)[0], 200)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel", {}, private=self.session)[1]["status"], "cancelled")

    def test_cancelling_a_private_lot_needs_the_private_space(self):
        lot = self.launch(count=2, steps=8)["lot"]["id"]
        for who in self.outsiders():
            self.assertEqual(call("POST", f"/api/lot/{lot}/cancel", {}, **who), (404, {"error": "lot inconnu"}), who)
        self.assertEqual(call("POST", f"/api/lot/{lot}/cancel", {}, private=self.session)[1]["cancelled"], 2)
        self.assertNotIn(lot, "\n".join(bench.LOG), "rien de l'espace privé dans le journal du serveur")

    def test_following_does_not_keep_the_session_alive_but_cancelling_does(self):
        jid = self.launch("SLOW=0.2 zq9 long", steps=40)["id"]
        with mock.patch("launch.PRIVATE_IDLE", 0.5):
            # annuler est un geste dans l'espace : il prolonge la session (l'annulation d'une génération finie ne
            # change rien d'autre)
            end = time.time() + 1.2
            while time.time() < end:
                self.assertEqual(call("POST", f"/api/job/{jid}/cancel", {}, private=self.session)[0], 200)
            self.assertIn(self.session, bench.S.private_sessions)
            # suivre ne la prolonge pas : la session se ferme et le suivi devient « inconnu »
            bench.wait_until(lambda: call("GET", f"/api/job/{jid}", private=self.session)[0] == 404,
                             timeout=5, what="suivi refusé après la fermeture de la session")
        self.assertNotIn(self.session, bench.S.private_sessions)

    def test_normal_generations_are_followed_as_before(self):
        a = bench.generate("SLOW=0.05 normal", steps=6)["id"]
        self.assertEqual(call("GET", f"/api/job/{a}", remote=True)[0], 200)
        self.assertEqual(call("POST", f"/api/job/{a}/cancel", {}, remote=True)[1]["status"], "cancelled")


def calibration():
    try:
        return open(bench.launch.CALIB, "rb").read()
    except OSError:
        return None


def job_count():
    return len(bench.S.jobs)


if __name__ == "__main__":
    unittest.main()
