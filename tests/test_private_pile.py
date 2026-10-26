"""Pile de l'espace privé, sur le banc à faux moteur (voir bench.py) : une génération privée terminée y attend d'être
triée, marquée « à trier » dans sa fiche chiffrée (meta) ; Garder rescelle la fiche sans la marque (image et vignette
intactes), Jeter supprime le dossier de l'image ; étanche à l'espace public, et rien dans les journaux."""
import json, os, unittest
from unittest import mock

import bench
from bench import call, files, wait_job

CODE = "Mot2passe!"


class PrivatePileTest(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def generate(self, prompt="zq8 privée", **kw):
        code, job = call("POST", "/api/generate", bench.gen_body(prompt, private=True, **kw), private=self.session)
        self.assertEqual(code, 202, job)
        done = wait_job(job["id"], private=self.session)
        self.assertEqual(done["status"], "done")
        return done

    def list(self, what, session=None):
        code, items = call("GET", f"/api/private/{what}", private=session or self.session)
        self.assertEqual(code, 200, items)
        return items

    def sort(self, action, item, session=None):
        return call("POST", f"/api/private/{action}", {"id": item}, private=session or self.session)

    def raw(self, item, role):
        with open(bench.launch.P("private", "items", item, role), "rb") as f:
            return f.read()

    def rev(self, session=None):
        return call("GET", "/api/status", private=session)[1]["rev"]

    def test_finished_private_image_waits_in_the_private_pile(self):
        j = self.generate(mode="edit", ref_images=[bench.data_url(bench.png_bytes())])
        [item] = self.list("pile")
        self.assertEqual((item["id"], item["prompt"], item["inputs"], item["private"]),
                         (j["item"], "zq8 privée", ["ref_1.png"], True))
        self.assertNotIn("pile", item)
        self.assertEqual(self.list("history"), [])
        self.assertEqual(call("GET", "/api/pile")[1], [])          # étanche : rien dans la pile publique
        for path in ("/api/private/pile", "/api/private/history"):
            with self.subTest(path=path):
                self.assertEqual(call("GET", path)[0], 403)                          # sans session
                self.assertEqual(call("GET", path, private=self.session, wifi=True)[0], 403)   # en clair sur le Wi-Fi
        for fp in bench.all_files():
            with open(fp, "rb") as f:
                self.assertNotIn(b'"pile"', f.read(), fp)            # la marque reste chiffrée

    def test_keep_reseals_the_record_and_leaves_image_thumbnail_and_inputs(self):
        item = self.generate(mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["item"]
        before = [self.raw(item, role) for role in ("image", "thumb", "input_0")]
        meta = self.raw(item, "meta")
        self.assertEqual(self.sort("keep", item), (200, {"ok": True}))
        self.assertEqual([self.raw(item, role) for role in ("image", "thumb", "input_0")], before)
        self.assertNotEqual(self.raw(item, "meta"), meta)
        self.assertEqual(self.list("pile"), [])
        [kept] = self.list("history")
        self.assertEqual((kept["id"], kept["prompt"]), (item, "zq8 privée"))
        self.assertNotIn("pile", kept)
        for action in ("keep", "discard"):
            self.assertEqual(self.sort(action, item), (404, {"error": "déjà triée"}), action)
        self.assertEqual([it["id"] for it in self.list("history")], [item])

    def test_discard_removes_the_image_folder(self):
        item = self.generate()["item"]
        other = self.generate("zq8 autre")["item"]
        self.assertEqual(self.sort("discard", item), (200, {"ok": True}))
        self.assertEqual((files("private", "items", item), files("private", "items", "." + item)), ([], []))
        self.assertEqual([it["id"] for it in self.list("pile")], [other])
        self.assertEqual(self.sort("discard", item), (404, {"error": "déjà triée"}))

    def test_an_interrupted_discard_leaves_only_a_hidden_folder(self):
        item = self.generate()["item"]
        with mock.patch.object(bench.launch.shutil, "rmtree", side_effect=OSError("disque")):
            self.assertEqual(self.sort("discard", item)[0], 500)
        self.assertEqual(files("private", "items", item), [])      # le dossier caché est purgé au démarrage
        self.assertEqual((self.list("pile"), self.list("history")), ([], []))
        self.assertEqual(self.sort("discard", item), (404, {"error": "déjà triée"}))
        bench.shutil.rmtree(bench.launch.P("private", "items", "." + item))

    def test_a_generation_cancelled_while_put_away_leaves_no_image(self):
        """Annulée ou oubliée par sa page pendant son rangement (entre la fin du calcul et « done ») : aucune image ne
        reste dans la pile privée, ni sur le disque (décision du 23/10/2026)."""
        real = bench.launch.keep_private
        for stop in ("cancel_job", "forget_job"):
            with self.subTest(stop=stop):
                def stopped_meanwhile(job):
                    item = real(job)
                    getattr(bench.launch, stop)(job)    # l'annulation, ou l'oubli, arrive pendant le rangement
                    return item
                with mock.patch.object(bench.launch, "keep_private", stopped_meanwhile):
                    code, job = call("POST", "/api/generate", bench.gen_body("zq8 annulée", private=True),
                                     private=self.session)
                    self.assertEqual(code, 202, job)
                    if stop == "cancel_job":
                        self.assertEqual(wait_job(job["id"], private=self.session)["status"], "cancelled")
                    bench.wait_idle()
                self.assertEqual(self.list("pile"), [])
                self.assertEqual([p for p in bench.private_entries()[1] if p.startswith("items" + os.sep)], [])

    def test_unknown_ids_are_already_sorted(self):
        for item in ("0" * 32, "../space.json", "", None, 3):
            with self.subTest(item=item):
                for action in ("keep", "discard"):
                    self.assertEqual(self.sort(action, item), (404, {"error": "déjà triée"}), action)

    def test_sorting_needs_a_session(self):
        item = self.generate()["item"]
        for action in ("keep", "discard"):
            with self.subTest(action=action):
                self.assertEqual(call("POST", f"/api/private/{action}", {"id": item})[0], 403)
                self.assertEqual(self.sort(action, item, session="session-inconnue")[0], 403)
                self.assertEqual(call("POST", f"/api/private/{action}", {"id": item}, private=self.session,
                                      wifi=True)[0], 403)
        self.assertEqual([it["id"] for it in self.list("pile")], [item])

    def test_a_key_that_is_no_longer_the_space_one_sorts_nothing(self):
        item = self.generate()["item"]
        other_key = bench.launch.X25519PrivateKey.generate()
        for action in ("keep", "discard"):
            with self.subTest(action=action), self.assertRaises(bench.launch.StaleKey):
                bench.launch.sort_private(action, other_key, item)
        self.assertEqual([it["id"] for it in self.list("pile")], [item])

    def test_private_image_from_before_the_pile_is_a_print(self):
        public = bench.launch.read_space()["public"]
        item = bench.launch.store_private(public, {"prompt": "zq8 ancienne", "time": 1}, bench.png_bytes(), [])
        self.assertEqual([it["id"] for it in self.list("history")], [item])
        self.assertEqual(self.list("pile"), [])
        self.assertEqual(self.sort("discard", item), (404, {"error": "déjà triée"}))
        self.assertEqual([it["id"] for it in self.list("history")], [item])

    def test_kept_record_reads_with_a_new_code(self):
        item = self.generate()["item"]
        self.assertEqual(self.sort("keep", item)[0], 200)
        self.assertEqual(call("POST", "/api/private/code", {"old": CODE, "new": "Autre-code-3"})[0], 200)
        session = bench.unlock_private("Autre-code-3")
        self.assertEqual([it["id"] for it in self.list("history", session)], [item])
        self.assertEqual(self.list("pile", session), [])

    def test_a_leftover_temporary_record_does_not_survive_a_code_change(self):
        item = self.generate()["item"]
        real = bench.launch.os.replace

        def cut(src, dst):
            if dst.endswith(os.path.join(item, "meta")):
                raise KeyboardInterrupt()       # coupure après l'écriture du fichier temporaire
            real(src, dst)
        with mock.patch.object(bench.launch.os, "replace", cut), mock.patch.object(bench.launch.os, "remove"), \
                self.assertRaises(KeyboardInterrupt):
            bench.launch.sort_private("keep", bench.S.private_sessions[self.session]["key"], item)
        self.assertTrue(files("private", "*.tmp"))                  # le reste d'une panne
        old_key = bench.S.private_sessions[self.session]["key"]
        self.assertEqual(call("POST", "/api/private/code", {"old": CODE, "new": "Autre-code-3"})[0], 200)
        self.assertEqual(files("private", "*.tmp"), [])
        new_key = bench.S.private_sessions[bench.unlock_private("Autre-code-3")]["key"]
        bench.assert_old_key_opens_nothing(self, old_key, new_key)

    def test_record_survives_a_failed_rewrite(self):
        item = self.generate()["item"]
        meta = self.raw(item, "meta")
        real = bench.launch.os.replace

        def replace(src, dst):
            if dst.endswith(os.path.join(item, "meta")):
                raise failure
            real(src, dst)
        for failure in (OSError("disque plein"), KeyboardInterrupt()):
            points = {"write_synced": mock.patch.object(bench.launch, "write_synced", side_effect=failure),
                      "os.replace": mock.patch.object(bench.launch.os, "replace", replace)}
            for at, patch in points.items():
                with self.subTest(failure=type(failure).__name__, at=at):
                    with patch, self.assertRaises(type(failure)):
                        bench.launch.sort_private("keep", bench.S.private_sessions[self.session]["key"], item)
                    self.assertEqual(self.raw(item, "meta"), meta)
                    self.assertEqual(files("private", "*.tmp"), [])
        self.assertEqual([it["id"] for it in self.list("pile")], [item])

    def test_private_rev_moves_only_inside_the_space(self):
        public, inside = self.rev(), self.rev(self.session)
        item = self.generate()["item"]
        self.assertNotEqual(self.rev(self.session), inside)
        other = self.generate("zq8 autre")["item"]
        last = self.rev(self.session)
        for action, it in (("keep", item), ("delete", item), ("discard", other)):
            with self.subTest(action=action):
                self.assertEqual(self.sort(action, it)[0], 200)
                self.assertNotEqual(self.rev(self.session), last)
                last = self.rev(self.session)
        self.assertEqual(self.rev(), public)                        # vu hors de l'espace : jamais bougé
        self.assertEqual(self.rev(self.session), last)
        self.assertEqual(self.sort("discard", other)[0], 404)
        self.assertEqual(self.rev(self.session), last)

    def test_nothing_reaches_the_server_log(self):
        item = self.generate()["item"]
        bench.LOG.clear()
        self.list("pile")
        self.assertEqual(self.sort("keep", item)[0], 200)
        self.assertEqual(self.sort("discard", item)[0], 404)
        self.assertEqual(call("GET", "/api/private/pile")[0], 403)
        self.assertEqual(call("POST", "/api/private/discard", {"id": item})[0], 403)
        self.assertEqual(bench.LOG, [])


if __name__ == "__main__":
    unittest.main()
