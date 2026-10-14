"""Générations privées et galerie privée : session exigée au lancement, image et tout ce qui s'y rattache chiffrés sur le
disque (aucun octet en clair nulle part), lisibles avec la session seulement, gardés même si l'espace se verrouille
avant la fin."""
import glob, os, unittest

import bench
from bench import call, files, wait_job

CODE = "Mot2passe!"


def all_files():
    """Tous les fichiers du dossier du banc (sauf le lien vers l'interface du dépôt)."""
    root = bench.launch.ROOT
    return [fp for fp in glob.glob(os.path.join(root, "**", "*"), recursive=True)
            if os.path.isfile(fp) and not fp.startswith(os.path.join(root, "tools", "ui"))]


class PrivateGenerationTest(bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def generate(self, prompt="zq9private secret prompt", session=None, **kw):
        code, job = call("POST", "/api/generate", bench.gen_body(prompt, private=True, **kw), private=session or self.session)
        self.assertEqual(code, 202, job)
        return job

    def history(self, session=None):
        code, items = call("GET", "/api/private/history", private=session or self.session)
        self.assertEqual(code, 200, items)
        return items

    def test_private_generation_needs_a_session(self):
        self.assertEqual(call("POST", "/api/generate", bench.gen_body("x", private=True))[0], 403)
        self.assertEqual(call("POST", "/api/generate", bench.gen_body("x", private=True, incognito=True), private=self.session)[0], 400)
        self.assertEqual(job_count(), 0)

    def test_nothing_in_clear_on_disk_after_a_private_generation(self):
        ref, calib_before = bench.png_bytes(80, 60), calibration()
        job = self.generate(mode="edit", ref_images=[bench.data_url(ref)], preview=True, steps=10)
        self.assertRegex(job["id"], r"^[0-9a-f]{32}$")
        self.assertTrue(job["private"])
        done = wait_job(job["id"])
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["path"])
        bench.wait_idle()
        [item] = self.history()
        code, png = call("GET", f"/api/private/image?id={item['id']}", private=self.session)
        self.assertEqual((code, png[:4]), (200, b"\x89PNG"))
        code, thumb = call("GET", f"/api/private/thumb?id={item['id']}", private=self.session)
        self.assertEqual((code, thumb[:2]), (200, b"\xff\xd8"))
        code, inp = call("GET", f"/api/private/input?id={item['id']}&file=ref_1.png", private=self.session)
        self.assertEqual((code, inp), (200, ref))
        # aucun octet de l'image, de sa miniature, de son entrée ni du prompt, nulle part sur le disque
        clear_bytes = [png[len(png) // 2:len(png) // 2 + 64], thumb[len(thumb) // 2:len(thumb) // 2 + 64],
                    ref[len(ref) // 2:len(ref) // 2 + 64], b"zq9private"]
        for fp in all_files():
            raw = open(fp, "rb").read()
            for s in clear_bytes:
                self.assertNotIn(s, raw, fp)
        self.assertEqual(files("outputs", "*.png"), [])
        self.assertEqual(bench.journal(), [])
        self.assertEqual(files("jobs", "*"), [])
        self.assertEqual(calibration(), calib_before)
        self.assertFalse([line for line in bench.LOG if "zq9private" in line or job["id"] in line])

    def test_history_lists_settings_and_reads_need_the_session(self):
        job = self.generate("zq9 a fox", seed=1234, steps=6)
        wait_job(job["id"])
        [item] = self.history()
        self.assertEqual((item["prompt"], item["mode"], item["width"], item["height"], item["steps"], item["seed"]),
                         ("zq9 a fox", "t2i", 512, 512, 6, 1234))
        self.assertEqual(item["inputs"], [])
        self.assertEqual(wait_job(job["id"])["item"], item["id"])
        for path in ("/api/private/history", f"/api/private/image?id={item['id']}", f"/api/private/thumb?id={item['id']}"):
            self.assertEqual(call("GET", path)[0], 403, path)
            self.assertEqual(call("GET", path, remote=True)[0], 403, path)
        other = bench.unlock_private(CODE, remote=True)          # un autre appareil, avec son propre code
        self.assertEqual(len(self.history(other)), 1)

    def test_download_gives_an_attachment(self):
        wait_job(self.generate()["id"])
        [item] = self.history()
        code, _, headers = bench.call_full("GET", f"/api/private/image?id={item['id']}&download=1", private=self.session)
        self.assertEqual(code, 200)
        self.assertIn("attachment", headers.get("Content-Disposition", ""))

    def test_generation_finished_after_locking_is_kept_and_read_after_unlocking(self):
        job = self.generate("SLOW=0.05 zq9 long one", steps=10)
        wait_job(job["id"], ("running",))
        call("POST", "/api/private/lock", private=self.session)
        self.assertEqual(wait_job(job["id"])["status"], "done")
        self.assertEqual(call("GET", "/api/private/history", private=self.session)[0], 403)
        again = bench.unlock_private(CODE)
        self.assertEqual([i["prompt"] for i in self.history(again)], ["SLOW=0.05 zq9 long one"])

    def test_delete_removes_the_image(self):
        wait_job(self.generate()["id"])
        [item] = self.history()
        self.assertEqual(call("POST", "/api/private/delete", {"id": item["id"]})[0], 403)
        self.assertEqual(call("POST", "/api/private/delete", {"id": item["id"]}, private=self.session)[0], 200)
        self.assertEqual(self.history(), [])
        self.assertEqual(call("GET", f"/api/private/image?id={item['id']}", private=self.session)[0], 404)
        self.assertEqual(files("private", "items", "*"), [])

    def test_bad_item_ids_are_refused(self):
        for bad in ("../space.json", "abc", "x" * 32):
            self.assertEqual(call("GET", f"/api/private/image?id={bad}", private=self.session)[0], 404)

    def test_queue_and_status_say_nothing_about_a_private_generation(self):
        job = self.generate("SLOW=0.1 zq9marker", steps=10, page="pagePriv1")
        wait_job(job["id"], ("running",))
        s = call("GET", "/api/status", remote=True)[1]
        self.assertIsNone(s["current_job"])
        self.assertEqual(s["queue"][0]["kind"], "private")
        self.assertEqual(s["queue"][0]["page"], "pagePriv1")
        self.assertNotIn(job["id"], str(s))
        self.assertNotIn("zq9marker", str(s))
        wait_job(job["id"])
        self.assertIsNone(call("GET", "/api/status")[1]["last_job"])

    def test_failed_private_generation_leaves_nothing(self):
        job = self.generate("FAIL zq9private")
        self.assertEqual(wait_job(job["id"])["status"], "failed")
        bench.wait_idle()
        self.assertEqual(files("jobs", "*"), [])
        self.assertEqual(self.history(), [])
        self.assertFalse([line for line in bench.LOG if "zq9private" in line])

    def test_notification_is_the_same_as_for_a_normal_image(self):
        with bench.capture_push() as sent:
            wait_job(self.generate()["id"])
            sent.wait(1)
            wait_job(call("POST", "/api/generate", bench.gen_body("a normal image"))[1]["id"])
            sent.wait(2)
        private, normal = sent
        self.assertEqual(private["title"], "Image prête")
        self.assertEqual(sorted(private), sorted(normal))
        self.assertRegex(private["body"], r"^Générée en \d+ s · 512×512$")
        self.assertNotIn("zq9", str(private))
        self.assertNotIn("priv", str(private).lower())

    def test_page_can_forget_a_finished_private_generation(self):
        job = self.generate()
        wait_job(job["id"])
        self.assertEqual(call("POST", f"/api/job/{job['id']}/forget")[0], 200)
        self.assertEqual(call("GET", f"/api/job/{job['id']}")[0], 404)
        self.assertEqual(len(self.history()), 1)              # l'image reste dans l'espace privé

    def test_page_close_does_not_cancel_a_private_generation(self):
        job = self.generate("SLOW=0.05 keep me", steps=8)
        wait_job(job["id"], ("running",))
        self.assertEqual(call("POST", "/api/forget", {"ids": [job["id"]]})[1]["forgotten"], 0)
        self.assertEqual(wait_job(job["id"])["status"], "done")

    def test_reset_during_generation_discards_the_image(self):
        job = self.generate("SLOW=0.05 zq9 reset", steps=10)
        wait_job(job["id"], ("running",))
        call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})
        bench.create_private("Un-autre-code")
        self.assertEqual(wait_job(job["id"])["status"], "failed")
        self.assertEqual(files("private", "items", "*"), [])


def calibration():
    try:
        return open(bench.launch.CALIB, "rb").read()
    except OSError:
        return None


def job_count():
    return len(bench.S.jobs)


if __name__ == "__main__":
    unittest.main()
