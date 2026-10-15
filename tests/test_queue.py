"""File d'attente visible : ordre de calcul, positions recalculées, liste de la file dans /api/status."""
import unittest

import bench
from bench import call, generate, wait_job


def queue():
    return call("GET", "/api/status")[1]["queue"]


class QueueOrderTest(bench.BenchCase):
    def test_three_requests_run_in_order_and_positions_advance(self):
        ids = [generate(f"SLOW=0.05 image {k}", steps=8)["id"] for k in range(3)]
        self.assertEqual([bench.job(i)["queue_position"] for i in ids], [0, 1, 2])
        wait_job(ids[0])
        self.assertEqual([bench.job(i)["queue_position"] for i in ids[1:]], [0, 1])
        done = [wait_job(i) for i in ids]
        self.assertEqual([j["status"] for j in done], ["done"] * 3)
        self.assertEqual(sorted(done, key=lambda j: j["started"]), done)
        self.assertTrue(all(a["finished"] <= b["started"] for a, b in zip(done, done[1:])))
        self.assertIsNone(bench.job(ids[0])["queue_position"])

    def test_cancelling_a_waiting_generation_leaves_the_others(self):
        a, b, c = (generate(f"SLOW=0.05 image {k}", steps=8)["id"] for k in range(3))
        call("POST", f"/api/job/{b}/cancel")
        self.assertEqual(bench.job(c)["queue_position"], 1)
        self.assertEqual([wait_job(i)["status"] for i in (a, b, c)], ["done", "cancelled", "done"])

    def test_other_device_can_cancel_a_normal_generation(self):
        a = generate("SLOW image")["id"]
        b = generate("waiting")["id"]
        self.assertEqual(call("POST", f"/api/job/{b}/cancel", remote=True)[1]["status"], "cancelled")
        wait_job(a)


class QueueListTest(bench.BenchCase):
    def test_status_lists_the_queue_running_first(self):
        a = generate("SLOW=0.2 the running one with a rather long prompt that goes on and on and on, far beyond eighty characters")["id"]
        wait_job(a, ("running",))
        b = generate("the waiting one", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"]
        q = queue()
        self.assertEqual([(e["id"], e["status"], e["position"]) for e in q], [(a, "running", 0), (b, "queued", 1)])
        self.assertEqual(q[1]["mode"], "edit")
        self.assertEqual(q[1]["prompt"], "the waiting one")
        self.assertLessEqual(len(q[0]["prompt"]), 81)
        self.assertTrue(all(e["estimate"] > 0 for e in q))
        self.assertIsNone(q[0]["lot"])
        self.assertEqual(call("GET", "/api/status")[1]["queued"], 1)
        call("POST", f"/api/job/{a}/cancel")
        call("POST", f"/api/job/{b}/cancel")

    def test_incognito_entry_has_neither_id_nor_prompt(self):
        a = generate("SLOW=0.2 visible", steps=6)["id"]
        b = generate("zq7marker secret", incognito=True)["id"]
        q = queue()
        self.assertEqual(q[1]["kind"], "incognito")
        self.assertNotIn("id", q[1])
        self.assertNotIn("prompt", q[1])
        self.assertNotIn("mode", q[1])
        self.assertNotIn(b, str(q))
        self.assertNotIn("zq7marker", str(q))
        wait_job(a)
        wait_job(b)

    def test_finished_generations_leave_the_queue(self):
        wait_job(generate("quick")["id"])
        self.assertEqual(queue(), [])


class SpacesQueueTest(bench.BenchCase):
    """File vue depuis chaque espace : l'espace public (sans session privée) et l'espace privé (session ouverte) ne
    voient que leurs générations, avec des rangs propres et le travail caché de l'autre espace compté dans ahead."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private("Mot2passe!")

    def status(self, private=False):
        return call("GET", "/api/status", private=self.session if private else None)[1]

    def private(self, prompt, **kw):
        code, job = call("POST", "/api/generate", bench.gen_body(prompt, private=True, **kw), private=self.session)
        self.assertEqual(code, 202, job)
        return job

    def mixed_queue(self):
        """Une génération normale qui tourne, puis, en attente : privée, incognito, privée, normale."""
        a = generate("SLOW=1 zq9public running", steps=20)["id"]
        wait_job(a, ("running",))
        p1 = self.private("zq9secret first", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])
        i = generate("zq9incognito", incognito=True, page="pageInc1")["id"]
        p2 = self.private("zq9secret second")
        n = generate("zq9public waiting")["id"]
        return a, p1, i, p2, n

    def test_public_space_sees_only_public_generations(self):
        a, p1, i, p2, n = self.mixed_queue()
        s = self.status()
        q = s["queue"]
        self.assertEqual([(e.get("id"), e["kind"], e["status"], e["position"]) for e in q],
                         [(a, "normal", "running", 0), (None, "incognito", "queued", 1), (n, "normal", "queued", 2)])
        self.assertNotIn(p1["id"], str(s))
        self.assertNotIn(p2["id"], str(s))
        self.assertNotIn("zq9secret", str(s))
        self.assertEqual((s["queued"], s["current_job"]), (2, a))
        # travail caché devant : rien devant la génération en cours ; la première privée devant l'incognito, les deux
        # devant la normale, comptées pour leur estimation vue depuis l'espace privé
        hidden = [e["estimate"] for e in self.status(private=True)["queue"]]
        self.assertEqual(q[0]["ahead"], 0)
        self.assertAlmostEqual(q[1]["ahead"], hidden[0], delta=0.2)
        self.assertAlmostEqual(q[2]["ahead"], hidden[0] + hidden[1], delta=0.2)
        self.assertEqual([bench.job(j)["queue_position"] for j in (i, n)], [1, 2])
        call("POST", f"/api/job/{a}/cancel")

    def test_private_space_sees_only_private_generations_with_their_prompt(self):
        a, p1, i, p2, n = self.mixed_queue()
        pub = self.status()["queue"]
        s = self.status(private=True)
        q = s["queue"]
        self.assertEqual([(e["id"], e["kind"], e["status"], e["position"]) for e in q],
                         [(p1["id"], "private", "queued", 1), (p2["id"], "private", "queued", 2)])
        self.assertEqual([(e["mode"], e["prompt"]) for e in q], [("edit", "zq9secret first"), ("t2i", "zq9secret second")])
        self.assertNotIn(a, str(q))
        self.assertNotIn(n, str(q))
        self.assertNotIn("zq9public", str(q))
        self.assertNotIn("incognito", str(q))
        self.assertEqual((s["queued"], s["current_job"], s["last_job"]), (2, None, None))
        # devant la première : ce qui reste de la génération publique en cours ; devant la seconde, en plus, l'incognito
        left = pub[0]["estimate"] - pub[0]["elapsed"]
        self.assertGreater(q[0]["ahead"], 0)
        self.assertAlmostEqual(q[0]["ahead"], left, delta=1.5)
        self.assertAlmostEqual(q[1]["ahead"] - q[0]["ahead"], pub[1]["estimate"], delta=0.2)
        self.assertEqual([bench.job(j["id"])["queue_position"] for j in (p1, p2)], [1, 2])
        self.assertEqual(p1["queue_position"], 1, "rang annoncé au lancement : celui de l'espace")
        # la publique annulée, la première privée tourne : génération courante de l'espace privé, rien devant elle
        call("POST", f"/api/job/{a}/cancel")
        wait_job(p1["id"], ("running",))
        s = self.status(private=True)
        self.assertEqual(s["current_job"], p1["id"])
        self.assertEqual([(e["position"], e["ahead"]) for e in s["queue"]][0], (0, 0))
        pub = self.status()
        self.assertIsNone(pub["current_job"])
        self.assertEqual([(e["kind"], e["position"]) for e in pub["queue"]], [("incognito", 1), ("normal", 2)])
        for j in (p1["id"], p2["id"]):
            call("POST", f"/api/job/{j}/cancel", private=self.session)

    def test_private_lot_shows_its_id_in_the_private_space_only(self):
        a = generate("SLOW=1 zq9public running", steps=20)["id"]
        wait_job(a, ("running",))
        lot = self.private("zq9lot", count=2)["lot"]
        q = self.status(private=True)["queue"]
        self.assertEqual([e["lot"] for e in q], [{"id": lot["id"], "rank": 1, "size": 2}, {"id": lot["id"], "rank": 2, "size": 2}])
        self.assertNotIn(lot["id"], str(self.status()))
        self.assertEqual(call("POST", f"/api/lot/{lot['id']}/cancel", private=self.session)[1]["cancelled"], 2)
        call("POST", f"/api/job/{a}/cancel")

    def test_last_image_is_public_only(self):
        wait_job(generate("zq9public done")["id"])
        self.assertIsNotNone(self.status()["last_job"])
        self.assertIsNone(self.status(private=True)["last_job"])


if __name__ == "__main__":
    unittest.main()
