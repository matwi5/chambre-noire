"""Vidéo dans l'espace privé (ticket 11), sur le banc à faux moteur (voir bench.py) : une vidéo privée est chiffrée
comme une image privée (fiche, vignette, image de départ), servie sous le type que disent ses premiers octets, sans
rien en clair hors du dossier de travail de sa génération ni rien d'elle dans les journaux du serveur ; Garder, Jeter
et le changement de code la traitent comme une image."""
import os, unittest
from unittest import mock

import bench
from bench import S, call, call_full, files, gen_body, wait_job

launch = bench.launch
CODE = "Mot2passe!"
VIDEO = {"model": "video", "steps": 4, "width": 480, "height": 288, "frames": 56}   # vidéo Petite de 2 s


def is_webp(raw):
    return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"


class PrivateVideoTest(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.enterContext(bench.video())
        self.session = bench.create_private(CODE)

    def start(self, prompt="zv11private une barque", session=None, **kw):
        code, job = call("POST", "/api/generate", gen_body(prompt, private=True, **{**VIDEO, **kw}),
                         private=session or self.session)
        self.assertEqual(code, 202, job)
        return job["id"]

    def generate(self, prompt="zv11private une barque", **kw):
        done = wait_job(self.start(prompt, **kw), private=self.session)
        self.assertEqual(done["status"], "done")
        return done

    def list(self, what, session=None):
        code, items = call("GET", f"/api/private/{what}", private=session or self.session)
        self.assertEqual(code, 200, items)
        return items

    def served(self, item, session=None, query=""):
        code, raw, headers = call_full("GET", f"/api/private/image?id={item}{query}", private=session or self.session)
        self.assertEqual(code, 200, raw)
        return raw, headers

    def test_a_private_video_is_sealed_with_its_record_thumbnail_and_start_image(self):
        start = bench.png_bytes(80, 60)
        done = self.generate(init_image=bench.data_url(start), frames=73)
        self.assertIsNone(done["path"])
        [item] = self.list("pile")
        self.assertEqual((item["id"], item["model"], item.get("frames"), item["inputs"], item["private"]),
                         (done["item"], "h3-video", 73, ["init.png"], True))
        video, headers = self.served(item["id"])
        self.assertTrue(is_webp(video), video)
        self.assertEqual(headers["Content-Type"], "image/webp")
        code, thumb = call("GET", f"/api/private/thumb?id={item['id']}", private=self.session)
        self.assertEqual((code, thumb[:2]), (200, b"\xff\xd8"))               # vignette fixe : JPEG
        code, inp = call("GET", f"/api/private/input?id={item['id']}&file=init.png", private=self.session)
        self.assertEqual((code, inp), (200, start))
        _, headers = self.served(item["id"], query="&download=1")
        self.assertIn(f'filename="prive_{item["id"][:8]}.webp"', headers["Content-Disposition"])
        # aucun octet de la vidéo, de sa vignette, de son image de départ ni du prompt, nulle part sur le disque du
        # banc, dossiers cachés compris
        clear = [video[len(video) // 2:len(video) // 2 + 64], thumb[len(thumb) // 2:len(thumb) // 2 + 64],
                 start[len(start) // 2:len(start) // 2 + 64], b"zv11private"]
        for fp in bench.all_files(hidden=True):
            with open(fp, "rb") as f:
                raw = f.read()
            for s in clear:
                self.assertNotIn(s, raw, fp)
        self.assertEqual((files("outputs", "*.webp"), bench.journal(), files("jobs", "*")), ([], [], []))
        self.assertFalse([line for line in bench.LOG if "zv11private" in line or done["item"] in line])

    def test_the_served_type_comes_from_the_first_bytes_not_from_the_record(self):
        public = launch.read_space()["public"]
        cases = (("h3", bench.png_bytes(fmt="WEBP"), "image/webp", ".webp"),          # fiche d'image, octets WebP
                 ("h3-video", bench.png_bytes(), "image/png", ".png"),               # fiche de vidéo, octets PNG
                 ("h3-video", b"RIFF\0\0\0\0WAVEfmt ", "image/png", ".png"))        # RIFF qui n'est pas un WebP
        for k, (model, raw, ctype, ext) in enumerate(cases):
            with self.subTest(model=model, ctype=ctype, k=k):
                meta = {"mode": "t2i", "prompt": f"type {k}", "width": 64, "height": 48, "steps": 4, "model": model,
                        "time": 1, "pile": True}
                with mock.patch.object(launch, "thumb_jpeg", return_value=b"\xff\xd8"):   # vignette de tout octet
                    item = launch.store_private(public, meta, raw, [])
                body, headers = self.served(item)
                self.assertEqual((bytes(body), headers["Content-Type"]), (raw, ctype))
                _, headers = self.served(item, query="&download=1")
                self.assertIn(f'filename="prive_{item[:8]}{ext}"', headers["Content-Disposition"])

    def test_a_failed_or_cancelled_private_video_leaves_nothing(self):
        failed = self.start("FAIL zv11private échouée")
        self.assertEqual(wait_job(failed, private=self.session)["status"], "failed")
        start = bench.png_bytes(72, 40)
        cancelled = self.start("HOLD=v11-annule zv11private annulée", init_image=bench.data_url(start))
        wait_job(cancelled, ("running",), private=self.session)
        self.assertEqual(call("POST", f"/api/job/{cancelled}/cancel", private=self.session)[0], 200)
        bench.release("v11-annule")
        self.assertEqual(wait_job(cancelled, private=self.session)["status"], "cancelled")
        bench.wait_idle()
        self.assertEqual((files("jobs", "*"), files("outputs", "*.webp"), self.list("pile")), ([], [], []))
        for fp in bench.all_files(hidden=True):           # dossiers cachés compris (.pile, .inputs, .thumbs)
            with open(fp, "rb") as f:
                raw = f.read()
            for s in (b"zv11private", start[len(start) // 2:len(start) // 2 + 64]):
                self.assertNotIn(s, raw, fp)
        self.assertFalse([line for line in bench.LOG if "zv11private" in line])

    def test_an_abrupt_stop_leaves_its_work_folder_to_the_startup_sweep(self):
        """Pendant le calcul, ni son prompt ni son image de départ ne sont en clair hors de son dossier de travail
        jobs/private_<id> (dossiers cachés compris) ; un arrêt brutal laisse ce dossier tel quel (copié ici pendant le
        calcul, sous un autre identifiant), et remove_leftovers, que main() appelle au démarrage, le supprime."""
        start = bench.png_bytes(72, 40)
        jid = self.start("HOLD=v11-arret zv11private", init_image=bench.data_url(start))
        left = launch.P("jobs", "private_" + "0" * 32)          # reste d'une génération privée d'un serveur tué
        try:
            wait_job(jid, ("running",), private=self.session)
            folder = launch.P("jobs", "private_" + jid)
            self.assertIn("init.png", os.listdir(folder))
            for fp in bench.all_files(hidden=True):
                if os.path.commonpath([fp, folder]) != folder:
                    with open(fp, "rb") as f:
                        raw = f.read()
                    for s in (b"zv11private", start[len(start) // 2:len(start) // 2 + 64]):
                        self.assertNotIn(s, raw, fp)
            bench.shutil.copytree(folder, left)
        finally:
            call("POST", f"/api/job/{jid}/cancel", private=self.session)
            bench.release("v11-arret")
            bench.wait_idle()
        self.assertEqual(files("jobs", "*"), [left])
        launch.remove_leftovers()
        self.assertEqual(files("jobs", "*"), [])

    def test_keep_discard_and_a_code_change_treat_a_private_video_like_an_image(self):
        kept, other = self.generate()["item"], self.generate("zv11private autre")["item"]
        self.assertEqual(call("POST", "/api/private/keep", {"id": kept}, private=self.session), (200, {"ok": True}))
        self.assertEqual(call("POST", "/api/private/discard", {"id": other}, private=self.session),
                         (200, {"ok": True}))
        self.assertEqual(files("private", "items", other), [])
        old_key = S.private_sessions[self.session]["key"]
        self.assertEqual(call("POST", "/api/private/code", {"old": CODE, "new": "Autre-code-3"})[0], 200)
        session = bench.unlock_private("Autre-code-3")
        [item] = self.list("history", session)
        self.assertEqual((item["id"], item["model"], item.get("frames")), (kept, "h3-video", 56))
        video, headers = self.served(kept, session)
        self.assertEqual((is_webp(video), headers["Content-Type"]), (True, "image/webp"))
        bench.assert_old_key_opens_nothing(self, old_key, S.private_sessions[session]["key"])

    def test_the_server_log_has_the_same_lines_as_for_an_image(self):
        lines = {}
        for what, body in (("image", gen_body("zv11private image", private=True)),
                           ("vidéo", gen_body("zv11private vidéo", private=True, **VIDEO))):
            bench.LOG.clear()
            code, job = call("POST", "/api/generate", body, private=self.session)
            self.assertEqual(code, 202, job)
            self.assertEqual(wait_job(job["id"], private=self.session)["status"], "done")
            [item] = [it["id"] for it in self.list("pile") if it["prompt"] == body["prompt"]]
            self.assertEqual(call("POST", "/api/private/keep", {"id": item}, private=self.session)[0], 200)
            bench.wait_idle()
            lines[what] = list(bench.LOG)
        self.assertIn(launch.DONE_LINE, lines["image"])            # comparaison de lignes réellement écrites
        self.assertEqual(lines["vidéo"], lines["image"])

    def test_a_queued_private_video_leaves_the_status_readable(self):
        """Une vidéo privée en attente derrière une génération publique : /api/status se lit sans erreur des deux
        espaces (vue du public, elle n'est qu'une durée dans l'ahead), et rien d'elle n'entre dans les journaux."""
        bench.LOG.clear()
        public = bench.generate("HOLD=v11-file a public car")["id"]
        try:
            wait_job(public, ("running",))
            jid = self.start("zv11private en file")
            code, status = call("GET", "/api/status")
            self.assertEqual(code, 200, status)
            self.assertNotIn(jid, str(status))
            code, status = call("GET", "/api/status", private=self.session)
            self.assertEqual(code, 200, status)
            [entry] = [e for e in status["queue"] if e["id"] == jid]
            self.assertEqual((entry["kind"], entry["model"]), ("private", "video"))
        finally:
            bench.release("v11-file")
        self.assertEqual(wait_job(jid, private=self.session)["status"], "done")
        bench.wait_idle()
        self.assertFalse([line for line in bench.LOG if "zv11private" in line or jid in line or "Traceback" in line])


if __name__ == "__main__":
    unittest.main()
