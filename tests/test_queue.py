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


if __name__ == "__main__":
    unittest.main()
