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


class MoveFirstTest(bench.BenchCase):
    """« Passer en tête » : une génération en attente, ou ce qui attend d'un lot, passe juste après celle en cours."""

    def held_queue(self, *prompts):
        """Une génération retenue en cours (HOLD), puis les prompts en attente ; renvoie leurs identifiants."""
        a = generate("HOLD running")["id"]
        wait_job(a, ("running",))
        return [a] + [generate(p)["id"] for p in prompts]

    def order(self):
        return [e["id"] for e in queue()]

    def test_moving_a_waiting_generation_puts_it_right_after_the_running_one(self):
        a, b, c, d = self.held_queue("b", "c", "d")
        self.assertEqual([bench.job(i)["queue_position"] for i in (b, c, d)], [1, 2, 3])
        self.assertEqual(call("POST", f"/api/job/{d}/first", {}), (200, {"ok": True}))
        self.assertEqual(self.order(), [a, d, b, c])
        self.assertEqual([bench.job(i)["queue_position"] for i in (d, b, c)], [1, 2, 3])
        bench.release()
        done = [wait_job(i) for i in (a, b, c, d)]
        self.assertEqual([j["id"] for j in sorted(done, key=lambda j: j["started"])], [a, d, b, c])

    def test_first_in_line_running_finished_or_unknown(self):
        a, b, c = self.held_queue("b", "c")
        self.assertEqual(call("POST", f"/api/job/{b}/first", {}), (200, {"ok": True}))
        self.assertEqual(self.order(), [a, b, c], "déjà en tête : rien ne bouge")
        self.assertEqual(call("POST", f"/api/job/{a}/first", {})[0], 409)
        self.assertEqual(call("POST", "/api/job/inconnu/first", {})[0], 404)
        self.assertEqual(call("POST", "/api/lot/inconnu/first", {})[0], 404)
        bench.release()
        wait_job(c)
        self.assertEqual(call("POST", f"/api/job/{c}/first", {})[0], 409)

    def test_moving_a_lot_moves_what_still_waits_in_its_order(self):
        a, b = self.held_queue("b")
        lot = generate("lot", count=3)
        ids = [j["id"] for j in lot["jobs"]]
        call("POST", f"/api/job/{ids[0]}/cancel")
        self.assertEqual(call("POST", f"/api/lot/{lot['lot']['id']}/first", {}), (200, {"ok": True}))
        self.assertEqual(self.order(), [a, ids[1], ids[2], b])
        self.assertEqual([bench.job(i)["queue_position"] for i in (ids[1], ids[2], b)], [1, 2, 3])
        bench.release()
        done = [wait_job(i) for i in (a, b, ids[1], ids[2])]
        self.assertEqual([j["id"] for j in sorted(done, key=lambda j: j["started"])], [a, ids[1], ids[2], b])

    def test_a_lot_where_nothing_waits_any_more_cannot_move(self):
        a, b = self.held_queue("b")
        lot = generate("lot", count=2)
        call("POST", f"/api/lot/{lot['lot']['id']}/cancel")
        self.assertEqual(call("POST", f"/api/lot/{lot['lot']['id']}/first", {})[0], 409)
        bench.release()
        wait_job(b)

    def test_cancelling_after_a_move_lets_the_others_run_and_notifies_the_lot_once(self):
        with bench.capture_push() as sent:
            a, b = self.held_queue("b")
            lot = generate("lot", count=3)
            ids = [j["id"] for j in lot["jobs"]]
            call("POST", f"/api/job/{ids[2]}/first", {})
            call("POST", f"/api/job/{ids[2]}/cancel")
            bench.release()
            self.assertEqual([wait_job(i)["status"] for i in (a, b, *ids)],
                             ["done", "done", "done", "done", "cancelled"])
            bench.wait_idle()
            lots = [m for m in sent.decided if m["body"].startswith("Lot de 3 images")]
            self.assertEqual([m["title"] for m in lots], ["2 images prêtes"], sent.decided)

    def test_a_move_writes_nothing_to_the_server_logs(self):
        a, b, c = self.held_queue("b", "c")
        lot = generate("lot", count=2)["lot"]["id"]
        before = len(bench.LOG)
        call("POST", f"/api/job/{c}/first", {})
        call("POST", f"/api/lot/{lot}/first", {})
        self.assertEqual(bench.LOG[before:], [])
        bench.release()
        wait_job(b)


class QueueListTest(bench.BenchCase):
    def test_status_lists_the_queue_running_first(self):
        a = generate("SLOW=0.2 the running one with a rather long prompt that goes on and on and on, far beyond eighty characters")["id"]
        wait_job(a, ("running",))
        b = generate("the waiting one", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"]
        q = queue()
        self.assertEqual([(e["id"], e["status"], e["position"]) for e in q], [(a, "running", 0), (b, "queued", 1)])
        self.assertEqual(q[1]["mode"], "edit")
        self.assertEqual(q[1]["prompt"], "the waiting one")
        self.assertEqual([(e["width"], e["height"], e["steps"]) for e in q], [(512, 512, 4)] * 2)
        self.assertLessEqual(len(q[0]["prompt"]), 81)
        self.assertTrue(all(e["estimate"] > 0 for e in q))
        self.assertIsNone(q[0]["lot"])
        self.assertEqual(call("GET", "/api/status")[1]["queued"], 1)
        call("POST", f"/api/job/{a}/cancel")
        call("POST", f"/api/job/{b}/cancel")

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

    def mixed_queue(self, first="zq9secret first"):
        """Une génération normale qui tourne, puis, en attente : privée, normale, privée, normale."""
        a = generate("SLOW=1 zq9public running", steps=20)["id"]
        wait_job(a, ("running",))
        p1 = self.private(first, mode="edit", ref_images=[bench.data_url(bench.png_bytes())])
        i = generate("zq9public second")["id"]
        p2 = self.private("zq9secret second")
        n = generate("zq9public waiting")["id"]
        return a, p1, i, p2, n

    def test_public_space_sees_only_public_generations(self):
        a, p1, i, p2, n = self.mixed_queue()
        s = self.status()
        q = s["queue"]
        self.assertEqual([(e.get("id"), e["kind"], e["status"], e["position"]) for e in q],
                         [(a, "normal", "running", 0), (i, "normal", "queued", 1), (n, "normal", "queued", 2)])
        self.assertNotIn(p1["id"], str(s))
        self.assertNotIn(p2["id"], str(s))
        self.assertNotIn("zq9secret", str(s))
        self.assertEqual((s["queued"], s["current_job"]), (2, a))
        # travail caché devant : rien devant la génération en cours ; la première privée devant la deuxième publique,
        # les deux devant la dernière, comptées pour leur estimation vue depuis l'espace privé
        hidden = [e["estimate"] for e in self.status(private=True)["queue"]]
        self.assertEqual(q[0]["ahead"], 0)
        self.assertAlmostEqual(q[1]["ahead"], hidden[0], delta=0.2)
        self.assertAlmostEqual(q[2]["ahead"], hidden[0] + hidden[1], delta=0.2)
        self.assertEqual([bench.job(j)["queue_position"] for j in (i, n)], [1, 2])
        call("POST", f"/api/job/{a}/cancel")

    def test_private_space_sees_only_private_generations_with_their_prompt(self):
        # la première privée attend sa libération une fois lancée : sinon, rapide, elle peut finir avant d'être vue
        # « running » (vu en CI)
        a, p1, i, p2, n = self.mixed_queue(first="HOLD=p1 zq9secret first")
        pub = self.status()["queue"]
        s = self.status(private=True)
        q = s["queue"]
        self.assertEqual([(e["id"], e["kind"], e["status"], e["position"]) for e in q],
                         [(p1["id"], "private", "queued", 1), (p2["id"], "private", "queued", 2)])
        self.assertEqual([(e["mode"], e["prompt"]) for e in q],
                         [("edit", "HOLD=p1 zq9secret first"), ("t2i", "zq9secret second")])
        self.assertNotIn(a, str(q))
        self.assertNotIn(n, str(q))
        self.assertNotIn("zq9public", str(q))
        self.assertEqual((s["queued"], s["current_job"], s["last_job"]), (2, None, None))
        # devant la première : ce qui reste de la génération publique en cours ; devant la seconde, en plus, la
        # deuxième publique
        left = pub[0]["estimate"] - pub[0]["elapsed"]
        self.assertGreater(q[0]["ahead"], 0)
        self.assertAlmostEqual(q[0]["ahead"], left, delta=1.5)
        self.assertAlmostEqual(q[1]["ahead"] - q[0]["ahead"], pub[1]["estimate"], delta=0.2)
        self.assertEqual([bench.job(j["id"], self.session)["queue_position"] for j in (p1, p2)], [1, 2])
        self.assertEqual(p1["queue_position"], 1, "rang annoncé au lancement : celui de l'espace")
        # la publique annulée, la première privée tourne : génération courante de l'espace privé, rien devant elle
        call("POST", f"/api/job/{a}/cancel")
        wait_job(p1["id"], ("running",), private=self.session)
        s = self.status(private=True)
        self.assertEqual(s["current_job"], p1["id"])
        self.assertEqual([(e["position"], e["ahead"]) for e in s["queue"]][0], (0, 0))
        pub = self.status()
        self.assertIsNone(pub["current_job"])
        self.assertEqual([(e["kind"], e["position"]) for e in pub["queue"]], [("normal", 1), ("normal", 2)])
        for j in (p1["id"], p2["id"]):
            call("POST", f"/api/job/{j}/cancel", private=self.session)
        bench.release("p1")

    def test_moving_a_private_generation_needs_the_private_space_and_public_ones_pass_hidden_work(self):
        a = generate("HOLD zq9public running")["id"]
        wait_job(a, ("running",))
        p1 = self.private("zq9secret first")["id"]
        i = generate("zq9public second")["id"]
        p2 = self.private("zq9secret second")["id"]
        n = generate("zq9public waiting")["id"]
        for kw in ({}, {"remote": True}):            # hors de l'espace privé : inconnue
            self.assertEqual(call("POST", f"/api/job/{p1}/first", {}, **kw)[0], 404)
        self.assertEqual(call("POST", f"/api/job/{n}/first", {})[0], 200)
        hidden = [e["estimate"] for e in self.status(private=True)["queue"]]
        pub = self.status()["queue"]
        self.assertEqual([(e["id"], e["position"]) for e in pub], [(a, 0), (n, 1), (i, 2)])
        self.assertEqual(pub[1]["ahead"], 0, "plus rien de caché devant la normale passée en tête")
        self.assertAlmostEqual(pub[2]["ahead"], hidden[0], delta=0.2)
        priv = self.status(private=True)["queue"]
        self.assertEqual([(e["id"], e["position"]) for e in priv], [(p1, 1), (p2, 2)])
        self.assertAlmostEqual(priv[0]["ahead"], pub[1]["estimate"] + pub[0]["estimate"] - pub[0]["elapsed"], delta=1.5)
        self.assertEqual(call("POST", f"/api/job/{p2}/first", {}, private=self.session)[0], 200)
        self.assertEqual([e["id"] for e in self.status(private=True)["queue"]], [p2, p1])
        self.assertEqual([e["id"] for e in self.status()["queue"]], [a, n, i])
        bench.release()
        for j in (p1, p2):
            wait_job(j, private=self.session)
        self.assertEqual(wait_job(i)["status"], "done")

    def test_outside_the_private_space_a_running_private_generation_is_unknown_not_busy(self):
        p = self.private("HOLD zq9secret running")["id"]
        wait_job(p, ("running",), private=self.session)
        lot = self.private("zq9secret lot", count=2)["lot"]["id"]
        self.assertEqual(call("POST", f"/api/job/{p}/first", {})[0], 404)
        self.assertEqual(call("POST", f"/api/lot/{lot}/first", {})[0], 404)
        self.assertEqual(call("POST", f"/api/job/{p}/first", {}, private=self.session)[0], 409)
        self.assertEqual(call("POST", f"/api/lot/{lot}/first", {}, private=self.session)[0], 200)
        call("POST", f"/api/lot/{lot}/cancel", private=self.session)
        bench.release()
        wait_job(p, private=self.session)

    def test_private_lot_shows_its_id_in_the_private_space_only(self):
        a = generate("SLOW=1 zq9public running", steps=20)["id"]
        wait_job(a, ("running",))
        lot = self.private("zq9lot", count=2)["lot"]
        q = self.status(private=True)["queue"]
        self.assertEqual([e["lot"] for e in q],
                         [{"id": lot["id"], "rank": k, "size": 2, "campaign": False} for k in (1, 2)])
        self.assertNotIn(lot["id"], str(self.status()))
        self.assertEqual(call("POST", f"/api/lot/{lot['id']}/cancel", private=self.session)[1]["cancelled"], 2)
        call("POST", f"/api/job/{a}/cancel")

    def test_last_image_is_public_only(self):
        wait_job(generate("zq9public done")["id"])
        self.assertIsNotNone(self.status()["last_job"])
        self.assertIsNone(self.status(private=True)["last_job"])


if __name__ == "__main__":
    unittest.main()
