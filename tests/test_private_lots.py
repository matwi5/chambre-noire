"""Lots privés : variantes et campagne dans l'espace privé, chaque image chiffrée, une seule notification, rien en clair
sur le disque ni dans la file."""
import unittest

import bench
from bench import call, files, wait_job
from test_private_gen import all_files

CODE = "Mot2passe!"


class PrivateLotTest(bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def launch(self, **kw):
        code, reply = call("POST", "/api/generate", bench.gen_body(private=True, **kw), private=self.session)
        self.assertEqual(code, 202, reply)
        return reply

    def history(self):
        return call("GET", "/api/private/history", private=self.session)[1]

    def test_private_variants_are_each_sealed_with_one_notification(self):
        with bench.capture_push() as sent:
            reply = self.launch(prompt="zq9lot a cat", count=3)
            self.assertRegex(reply["lot"]["id"], r"^[0-9a-f]{32}$")
            self.assertTrue(all(j["private"] for j in reply["jobs"]))
            for j in reply["jobs"]:
                self.assertEqual(wait_job(j["id"], private=self.session)["status"], "done")
            sent.wait(1)
            bench.wait_idle()
        self.assertEqual([m["title"] for m in sent], ["3 images prêtes"])
        self.assertNotIn("zq9lot", str(sent))
        self.assertEqual(sent[0]["body"][:len("Lot de 3 images terminé en ")], "Lot de 3 images terminé en ")
        self.assertNotIn("priv", str(sent).lower())
        items = self.history()
        self.assertEqual(sorted(i["lot"]["rank"] for i in items), [1, 2, 3])
        self.assertEqual(len({i["seed"] for i in items}), 3)
        self.assertEqual((files("outputs", "*.png"), bench.journal(), files("jobs", "*")), ([], [], []))
        for fp in all_files():
            self.assertNotIn(b"zq9lot", open(fp, "rb").read(), fp)

    def test_private_lot_is_absent_from_the_public_queue(self):
        reply = self.launch(prompt="SLOW=0.05 zq9lot", count=2, steps=8, page="pageLot1")
        wait_job(reply["jobs"][0]["id"], ("running",), private=self.session)
        s = call("GET", "/api/status", remote=True)[1]
        self.assertEqual(s["queue"], [])                                     # rien n'y trahit l'espace privé
        self.assertNotIn(reply["lot"]["id"], str(s))
        self.assertEqual(call("POST", f"/api/lot/{reply['lot']['id']}/cancel", private=self.session)[1]["cancelled"], 2)

    def test_private_campaign_keeps_each_photo_as_its_input(self):
        photos = [bench.png_bytes(64, 48), bench.png_bytes(48, 64)]
        with bench.capture_push() as sent:
            reply = self.launch(prompt="zq9camp paint it blue", mode="edit", ref_images=[],
                                campaign=[{"image": bench.data_url(p), "width": 512, "height": 384} for p in photos])
            for j in reply["jobs"]:
                self.assertEqual(wait_job(j["id"], private=self.session)["status"], "done")
            sent.wait(1)
        self.assertEqual(sent[0]["title"], "2 images prêtes")
        items = sorted(self.history(), key=lambda i: i["lot"]["rank"])
        self.assertEqual([i["inputs"] for i in items], [["ref_1.png"], ["ref_1.png"]])
        for item, photo in zip(items, photos):
            self.assertEqual(call("GET", f"/api/private/input?id={item['id']}&file=ref_1.png", private=self.session)[1], photo)

    def test_failed_image_in_a_private_lot(self):
        with bench.capture_push() as sent:
            reply = self.launch(prompt="zq9 FAILSEED=7", count=2, seed=6)
            for j in reply["jobs"]:
                wait_job(j["id"], private=self.session)
            sent.wait(1)
        self.assertEqual(sent[0]["title"], "1 image prête, 1 en échec")


if __name__ == "__main__":
    unittest.main()
