"""Lots et variantes : plusieurs générations d'une seule demande (count), graines tirées par le serveur, annulation du
lot, une seule notification par lot."""
import time, unittest

import bench
from bench import call, files, journal, wait_job


def generate_lot(prompt="a red car", count=3, **kw):
    code, reply = call("POST", "/api/generate", bench.gen_body(prompt, count=count, **kw))
    assert code == 202, (code, reply)
    return reply


class VariantsTest(bench.BenchCase):
    def test_count_creates_one_generation_per_image_in_one_lot(self):
        reply = generate_lot(count=3)
        lot, jobs = reply["lot"], reply["jobs"]
        self.assertEqual(lot["size"], 3)
        self.assertEqual(len(jobs), 3)
        self.assertEqual(len({j["id"] for j in jobs}), 3)
        self.assertEqual([j["lot"] for j in jobs], [{"id": lot["id"], "rank": k, "size": 3} for k in (1, 2, 3)])
        done = [wait_job(j["id"]) for j in jobs]
        self.assertEqual([j["status"] for j in done], ["done"] * 3)
        self.assertTrue(all(a["finished"] <= b["started"] for a, b in zip(done, done[1:])))   # à la suite, dans l'ordre
        self.assertEqual(len(files("outputs", "*.png")), 3)

    def test_server_draws_distinct_seeds_written_to_the_journal(self):
        jobs = generate_lot(count=4)["jobs"]
        for j in jobs:
            wait_job(j["id"])
        lines = journal()
        seeds = [m["seed"] for m in lines]
        self.assertEqual(len(set(seeds)), 4)
        self.assertTrue(all(isinstance(s, int) and 0 <= s < 2 ** 31 for s in seeds))
        self.assertEqual(sorted(m["lot"]["rank"] for m in lines), [1, 2, 3, 4])
        self.assertEqual({m["lot"]["id"] for m in lines}, {jobs[0]["lot"]["id"]})
        self.assertEqual([bench.job(j["id"])["seed"] for j in jobs], [m["seed"] for m in sorted(lines, key=lambda m: m["lot"]["rank"])])

    def test_explicit_seed_gives_consecutive_seeds(self):
        jobs = generate_lot(count=3, seed=10)["jobs"]
        self.assertEqual([j["seed"] for j in jobs], [10, 11, 12])
        for j in jobs:
            wait_job(j["id"])

    def test_single_generation_has_no_lot_and_a_real_seed(self):
        for body in ({}, {"count": 1}):
            j = bench.generate("alone", **body)
            self.assertIsNone(j["lot"])
            wait_job(j["id"])
        self.assertTrue(all(m["seed"] >= 0 and "lot" not in m for m in journal()))
        self.assertEqual(len(journal()), 2)

    def test_queue_shows_the_rank_in_the_lot(self):
        jobs = generate_lot("SLOW=0.05 lot", count=2, steps=8)["jobs"]
        q = call("GET", "/api/status")[1]["queue"]
        self.assertEqual([e["lot"] for e in q], [j["lot"] for j in jobs])
        for j in jobs:
            wait_job(j["id"])

    def test_incognito_lot_hides_its_id_from_the_queue(self):
        jobs = generate_lot("SLOW=0.05 secret", count=2, steps=8, incognito=True)["jobs"]
        lot = jobs[0]["lot"]["id"]
        s = call("GET", "/api/status", remote=True)[1]
        self.assertEqual([e["lot"] for e in s["queue"]], [{"rank": 1, "size": 2}, {"rank": 2, "size": 2}])
        self.assertNotIn(lot, str(s))
        for j in jobs:
            wait_job(j["id"])

    def test_count_is_refused_outside_create_mode_or_out_of_range(self):
        ref = [bench.data_url(bench.png_bytes())]
        for body in ({"count": 2, "mode": "edit", "ref_images": ref}, {"count": 2, "mode": "annot", "ref_images": ref},
                     {"count": 5}, {"count": 0}, {"count": "2"}, {"count": True}, {"count": 2.0}):
            code, reply = call("POST", "/api/generate", bench.gen_body(**body))
            self.assertEqual(code, 400, body)
            self.assertIn("count", reply["error"])
        self.assertEqual(bench.S.jobs, {})


class LotCancelTest(bench.BenchCase):
    def test_cancelling_the_lot_stops_everything_and_leaves_nothing(self):
        with bench.capture_push() as sent:
            jobs = generate_lot("SLOW=0.1 lot", count=3, steps=30)["jobs"]
            wait_job(jobs[0]["id"], ("running",))
            code, reply = call("POST", f"/api/lot/{jobs[0]['lot']['id']}/cancel", remote=True)
            self.assertEqual((code, reply["cancelled"]), (200, 3))
            self.assertEqual([wait_job(j["id"])["status"] for j in jobs], ["cancelled"] * 3)
            bench.wait_idle()
            self.assertEqual(files("outputs", "*.png"), [])
            self.assertEqual(files("jobs", "*"), [])
            time.sleep(0.3)
            self.assertEqual(list(sent), [])               # tout le lot annulé : aucune notification

    def test_cancelling_the_rest_of_a_lot_keeps_the_finished_images(self):
        jobs = generate_lot("SLOW=0.05 lot", count=3, steps=8)["jobs"]
        wait_job(jobs[0]["id"])
        call("POST", f"/api/lot/{jobs[0]['lot']['id']}/cancel")
        self.assertEqual([wait_job(j["id"])["status"] for j in jobs], ["done", "cancelled", "cancelled"])
        self.assertEqual(len(files("outputs", "*.png")), 1)

    def test_unknown_or_finished_lot(self):
        self.assertEqual(call("POST", "/api/lot/inconnu/cancel")[0], 404)
        jobs = generate_lot(count=2)["jobs"]
        for j in jobs:
            wait_job(j["id"])
        bench.wait_idle()
        self.assertEqual(call("POST", f"/api/lot/{jobs[0]['lot']['id']}/cancel")[0], 404)   # lot fini : oublié
        self.assertEqual(bench.S.lots, {})


class LotNotificationTest(bench.BenchCase):
    def wait_lot(self, jobs):
        for j in jobs:
            wait_job(j["id"])
        bench.wait_idle()

    def only(self, sent):
        """La seule notification envoyée (une seconde envoyée par erreur aurait le temps d'arriver)."""
        sent.wait(1)
        time.sleep(0.3)
        self.assertEqual(len(sent), 1, list(sent))
        return sent[0]

    def test_one_notification_for_the_whole_lot(self):
        with bench.capture_push() as sent:
            self.wait_lot(generate_lot("zq7marker lot", count=3)["jobs"])
            msg = self.only(sent)
            self.assertEqual(msg["title"], "3 images prêtes")
            self.assertTrue(msg["body"].startswith("Lot de 3 images terminé en "))
            self.assertNotIn("zq7marker", str(msg))

    def test_notification_counts_the_failures(self):
        with bench.capture_push() as sent:
            self.wait_lot(generate_lot("FAILSEED=11 lot", count=3, seed=10)["jobs"])
            self.assertEqual(self.only(sent)["title"], "2 images prêtes, 1 en échec")

    def test_whole_lot_failed(self):
        with bench.capture_push() as sent:
            self.wait_lot(generate_lot("FAIL lot", count=2)["jobs"])
            self.assertEqual(self.only(sent)["title"], "Échec du lot")

    def test_incognito_lot(self):
        with bench.capture_push() as sent:
            self.wait_lot(generate_lot("secret", count=2, incognito=True)["jobs"])
            self.assertEqual(self.only(sent)["title"], "2 images incognito prêtes")

    def test_lot_ending_with_cancelled_generations_notifies_once(self):
        with bench.capture_push() as sent:
            jobs = generate_lot("SLOW=0.05 lot", count=3, steps=8)["jobs"]
            wait_job(jobs[0]["id"], ("running",))
            call("POST", f"/api/job/{jobs[2]['id']}/cancel")    # la dernière, encore en file
            self.wait_lot(jobs)
            self.assertEqual(self.only(sent)["title"], "2 images prêtes")


class HistoryLotTest(bench.BenchCase):
    def test_history_gives_the_lot_of_each_image_and_nothing_for_a_single_one(self):
        jobs = generate_lot(count=2)["jobs"]
        single = bench.generate("alone")
        for j in jobs + [single]:
            wait_job(j["id"])
        items = {it["name"]: it for it in call("GET", "/api/history")[1]}
        self.assertEqual(len(items), 3)
        self.assertEqual([items[j["name"]]["lot"] for j in jobs], [j["lot"] for j in jobs])
        self.assertIsNone(items[single["name"]]["lot"])
        self.assertTrue(all(isinstance(it["seed"], int) for it in items.values()))

    def test_incognito_lot_stays_out_of_the_history(self):
        jobs = generate_lot("secret", count=2, incognito=True)["jobs"]
        for j in jobs:
            wait_job(j["id"])
        self.assertEqual(call("GET", "/api/history")[1], [])


if __name__ == "__main__":
    unittest.main()
