"""Campagne : le même prompt appliqué séparément à chaque photo, une génération du mode Éditer par photo, à ses
dimensions, dans un même lot."""
import unittest

import bench
from bench import call, data_url, png_bytes, wait_job


def photo(w, h, color=(200, 30, 30)):
    """Photo PNG de w×h d'une couleur donnée (pour reconnaître chaque photo parmi les images d'entrée)."""
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def entry(raw, w, h):
    return {"image": data_url(raw), "width": w, "height": h}


def campaign_body(entries, prompt="make the car blue", **kw):
    return bench.gen_body(prompt, mode="edit", campaign=entries, **kw)


class CampaignTest(bench.BenchCase):
    def test_one_generation_per_photo_with_its_own_photo_and_size(self):
        photos = [photo(64, 48, (255, 0, 0)), photo(48, 64, (0, 255, 0)), photo(50, 50, (0, 0, 255))]
        sizes = [(1184, 896), (896, 1184), (1024, 1024)]
        code, reply = call("POST", "/api/generate", campaign_body([entry(p, *s) for p, s in zip(photos, sizes)]))
        self.assertEqual(code, 202, reply)
        jobs = reply["jobs"]
        self.assertEqual((reply["lot"]["size"], reply["lot"]["campaign"]), (3, True))
        self.assertEqual([(j["lot"]["rank"], j["lot"]["campaign"]) for j in jobs], [(1, True), (2, True), (3, True)])
        done = [wait_job(j["id"]) for j in jobs]
        self.assertEqual([j["status"] for j in done], ["done"] * 3)
        self.assertEqual([tuple(j["dims"]) for j in done], sizes)
        history = {it["name"]: it for it in call("GET", "/api/history")[1]}
        for j, raw in zip(jobs, photos):
            item = history[j["name"]]
            self.assertEqual(item["inputs"], ["ref_1.png"])            # sa seule photo, gardée comme image d'entrée
            self.assertEqual(item["mode"], "edit")
            self.assertEqual(item["prompt"], "make the car blue")
            self.assertTrue(item["lot"]["campaign"])
            self.assertTrue(bench.job(j["id"])["lot"]["campaign"])
            code, kept = call("GET", f"/api/input?name={j['name']}&file=ref_1.png")
            self.assertEqual((code, kept), (200, raw))

    def test_queue_shows_the_campaign_as_a_lot(self):
        entries = [entry(png_bytes(), 512, 512) for _ in range(2)]
        jobs = call("POST", "/api/generate", campaign_body(entries, prompt="SLOW=0.05 blue", steps=8))[1]["jobs"]
        q = call("GET", "/api/status")[1]["queue"]
        self.assertEqual([(e["mode"], e["lot"]["rank"], e["lot"]["campaign"]) for e in q],
                         [("edit", 1, True), ("edit", 2, True)])
        for j in jobs:
            wait_job(j["id"])

    def test_campaign_notification_speaks_of_photos(self):
        with bench.capture_push() as sent:
            jobs = call("POST", "/api/generate", campaign_body([entry(png_bytes(), 512, 512)] * 2))[1]["jobs"]
            for j in jobs:
                wait_job(j["id"])
            msg = sent.wait(1)[0]
            self.assertEqual(msg["title"], "2 images prêtes")
            self.assertTrue(msg["body"].startswith("Campagne de 2 photos terminée en "), msg["body"])

    def test_single_photo_campaign_is_a_single_generation(self):
        code, j = call("POST", "/api/generate", campaign_body([entry(png_bytes(), 512, 384)]))
        self.assertEqual(code, 202)
        self.assertIsNone(j["lot"])
        self.assertEqual(wait_job(j["id"])["dims"], [512, 384])

    def test_invalid_campaigns_are_refused(self):
        ok = entry(png_bytes(), 512, 512)
        for body in (bench.gen_body(mode="t2i", campaign=[ok, ok]),                     # hors du mode Éditer
                     bench.gen_body(mode="annot", campaign=[ok, ok]),
                     campaign_body([ok] * 11),                                          # au-delà de 10
                     campaign_body([]),
                     campaign_body("photos"),
                     campaign_body([ok, {"image": data_url(png_bytes())}]),           # dimensions manquantes
                     campaign_body([ok, {"image": 3, "width": 512, "height": 512}]),
                     campaign_body([ok, {"image": data_url(png_bytes()), "width": 5000, "height": 512}]),
                     campaign_body([ok, ok], ref_images=[data_url(png_bytes())])):   # photos à part de ref_images
            with self.subTest(mode=body["mode"], campaign=str(body["campaign"])[:80]):
                code, reply = call("POST", "/api/generate", body)
                self.assertEqual(code, 400)
                self.assertIn("campaign", reply["error"])
        self.assertEqual(bench.S.jobs, {})

    def test_ten_photos_are_accepted(self):
        code, reply = call("POST", "/api/generate", campaign_body([entry(png_bytes(), 256, 256)] * 10, steps=1))
        self.assertEqual((code, reply["lot"]["size"]), (202, 10))
        for j in reply["jobs"]:
            wait_job(j["id"])


if __name__ == "__main__":
    unittest.main()
