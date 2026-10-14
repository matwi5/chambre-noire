"""« Rendre privée » : une image de la galerie normale entre dans l'espace privé avec le code, et quitte outputs/, ses
miniatures, ses images d'entrée et sa ligne du journal ; une génération qui se termine pendant la réécriture du journal
garde sa ligne."""
import os, threading, time, unittest
from unittest import mock

import bench
from bench import call, files, journal, wait_job

CODE = "Mot2passe!"


class AdoptTest(bench.BenchCase):
    def setUp(self):
        super().setUp()
        bench.create_private(CODE)

    def make_image(self, prompt="zq9adopt a red car"):
        ref = bench.png_bytes(70, 50)
        job = wait_job(bench.generate(prompt, mode="edit", ref_images=[bench.data_url(ref)], seed=42)["id"])
        self.assertEqual(call("GET", f"/api/thumb?name={job['name']}")[0], 200)                      # miniature faite
        self.assertEqual(call("GET", f"/api/input?name={job['name']}&file=ref_1.png&thumb=1")[0], 200)
        return job["name"], ref

    def test_adopt_moves_the_image_into_the_private_space(self):
        name, ref = self.make_image()
        other, _ = self.make_image("zq9 another one")
        png = open(bench.launch.P("outputs", name), "rb").read()
        code, reply = call("POST", "/api/private/adopt", {"name": name, "code": CODE})
        self.assertEqual(code, 200, reply)
        stem = name[:-4]
        self.assertEqual([os.path.basename(f) for f in files("outputs", "*.png")], [other])
        self.assertEqual(files("outputs", ".thumbs", stem + "*"), [])
        self.assertEqual(files("outputs", ".inputs", stem), [])
        self.assertEqual([os.path.basename(m["file"]) for m in journal()], [other])
        self.assertNotIn(name, [h["name"] for h in call("GET", "/api/history")[1]])
        jid = stem.rsplit("_", 1)[0]                     # sa génération : dossier de travail et suivi oubliés
        self.assertEqual(files("jobs", jid), [])
        self.assertEqual(call("GET", f"/api/job/{jid}")[0], 404)
        session = bench.unlock_private(CODE)
        [item] = call("GET", "/api/private/history", private=session)[1]
        self.assertEqual(item["id"], reply["id"])
        self.assertEqual((item["prompt"], item["mode"], item["seed"], item["inputs"]), ("zq9adopt a red car", "edit", 42, ["ref_1.png"]))
        self.assertEqual(call("GET", f"/api/private/image?id={item['id']}", private=session)[1], png)
        self.assertEqual(call("GET", f"/api/private/input?id={item['id']}&file=ref_1.png", private=session)[1], ref)

    def test_wrong_code_changes_nothing(self):
        name, _ = self.make_image()
        t = time.time()
        self.assertEqual(call("POST", "/api/private/adopt", {"name": name, "code": "Mauvais-code"})[0], 403)
        self.assertGreaterEqual(time.time() - t, 1)
        self.assertEqual(len(files("outputs", "*.png")), 1)
        self.assertEqual(len(journal()), 1)
        self.assertEqual(files("private", "items", "*"), [])

    def test_unknown_image_or_missing_space(self):
        self.assertEqual(call("POST", "/api/private/adopt", {"name": "nope.png", "code": CODE})[0], 404)
        self.assertEqual(call("POST", "/api/private/adopt", {"name": "../tools/config.json", "code": CODE})[0], 404)
        name, _ = self.make_image()
        call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})
        self.assertEqual(call("POST", "/api/private/adopt", {"name": name, "code": CODE})[0], 404)
        self.assertEqual(len(files("outputs", "*.png")), 1)

    def test_failure_halfway_leaves_the_original_and_no_private_copy(self):
        name, _ = self.make_image()
        with mock.patch("launch.delete_output", side_effect=OSError("disque plein")):
            self.assertEqual(call("POST", "/api/private/adopt", {"name": name, "code": CODE})[0], 500)
        self.assertEqual(len(files("outputs", "*.png")), 1)
        self.assertEqual(files("private", "items", "*"), [])

    def test_generation_ending_during_the_journal_rewrite_keeps_its_line(self):
        name, _ = self.make_image()
        real, finished = bench.launch.write_journal, {}

        def slow_write(lines):                       # une génération se termine entre la lecture et l'écriture
            j = bench.generate("zq9 finishing meanwhile")
            finished.update(wait_job(j["id"]))
            time.sleep(0.4)                          # sans verrou commun, sa ligne serait ajoutée puis écrasée
            real(lines)
        with mock.patch("launch.write_journal", slow_write):
            self.assertEqual(call("POST", "/api/private/adopt", {"name": name, "code": CODE})[0], 200)
        bench.wait_idle()
        self.assertEqual([os.path.basename(m["file"]) for m in journal()], [finished["name"]])


if __name__ == "__main__":
    unittest.main()
