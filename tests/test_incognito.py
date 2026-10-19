"""Incognito dans la file : rien qui le trahisse aux autres appareils, image gardée jusqu'à sa page, oubli groupé,
identifiant impossible à deviner, image jamais récupérée oubliée après un délai."""
import time, unittest
from unittest import mock

import bench
from bench import call, files, generate, wait_job


class IncognitoQueueTest(bench.BenchCase):
    def test_status_shows_neither_id_nor_prompt(self):
        jid = generate("SLOW=0.1 zq7marker secret", incognito=True, steps=20)["id"]
        wait_job(jid, ("running",))
        s = call("GET", "/api/status", remote=True)[1]
        self.assertIsNone(s["current_job"])
        self.assertTrue(s["busy"])
        self.assertEqual(s["queue"][0]["kind"], "incognito")
        self.assertNotIn(jid, str(s))
        self.assertNotIn("zq7marker", str(s))
        call("POST", f"/api/job/{jid}/cancel")

    def test_normal_current_job_is_still_shown(self):
        jid = generate("SLOW visible")["id"]
        wait_job(jid, ("running",))
        self.assertEqual(call("GET", "/api/status")[1]["current_job"], jid)
        wait_job(jid)

    def test_another_request_keeps_an_image_not_yet_retrieved(self):
        jid = generate("secret", incognito=True)["id"]
        wait_job(jid)
        code, other = call("POST", "/api/generate", bench.gen_body("someone else's image"), remote=True)
        self.assertEqual(code, 202)
        wait_job(other["id"])
        code, raw = call("GET", f"/api/job/{jid}/result")
        self.assertEqual((code, raw[:4]), (200, b"\x89PNG"))

    def test_page_close_forgets_all_its_incognito_generations_at_once(self):
        done = generate("finished, not retrieved", incognito=True)["id"]
        wait_job(done)
        running = generate("SLOW=0.2 running", incognito=True, steps=30)["id"]
        waiting = generate("waiting", incognito=True)["id"]
        normal = generate("a normal one")["id"]
        wait_job(running, ("running",))
        code, reply = call("POST", "/api/forget", {"ids": [done, running, waiting, normal, "inconnu"]})
        self.assertEqual((code, reply["forgotten"]), (200, 3))
        for jid in (done, running, waiting):
            self.assertEqual(call("GET", f"/api/job/{jid}")[0], 404)
            self.assertEqual(call("GET", f"/api/job/{jid}/result")[0], 404)
        self.assertEqual(wait_job(normal)["status"], "done")
        bench.wait_idle()
        self.assertEqual(files("jobs", "incognito_*"), [])
        self.assertEqual(len(files("outputs", "*.png")), 1)

    def test_forget_needs_a_list_of_ids(self):
        self.assertEqual(call("POST", "/api/forget", {"ids": "abc"})[0], 400)
        self.assertEqual(call("POST", "/api/forget", {})[0], 400)


class IncognitoHardeningTest(bench.BenchCase):
    def test_incognito_id_has_128_random_bits_and_normal_ids_keep_their_format(self):
        incog = generate("secret", incognito=True)["id"]
        normal = generate("visible")["id"]
        self.assertRegex(incog, r"^[0-9a-f]{32}$")
        self.assertRegex(normal, r"^\d{8}_\d{6}_[0-9a-f]{6}$")
        wait_job(incog)
        wait_job(normal)

    def test_incognito_lot_id_is_long_too(self):
        code, reply = call("POST", "/api/generate", bench.gen_body("secret lot", count=2, incognito=True))
        self.assertEqual(code, 202)
        self.assertRegex(reply["lot"]["id"], r"^[0-9a-f]{32}$")
        for j in reply["jobs"]:
            wait_job(j["id"])

    def test_image_never_retrieved_is_forgotten_after_the_delay(self):
        with mock.patch("launch.INCOGNITO_TTL", 0.4):
            done = generate("never retrieved", incognito=True)["id"]
            failed = generate("FAIL never seen", incognito=True)["id"]
            wait_job(done)
            wait_job(failed)
            self.assertEqual(call("GET", f"/api/job/{done}/result")[0], 200)   # avant le délai : toujours là
            # chaque requête fait le ménage (sweep) : on interroge jusqu'à l'oubli, passé le délai
            bench.wait_until(lambda: all(call("GET", f"/api/job/{jid}")[0] == 404 for jid in (done, failed)),
                             what="générations incognito oubliées")
            self.assertEqual(call("GET", f"/api/job/{done}/result")[0], 404)
            self.assertNotIn(done, bench.S.jobs)

    def test_running_or_waiting_incognito_is_not_expired(self):
        with mock.patch("launch.INCOGNITO_TTL", 0.1):
            jid = generate("SLOW=0.1 long", incognito=True, steps=8)["id"]
            started = lambda: bench.S.jobs[jid]   # en cours depuis plus que le délai, sans être oubliée
            bench.wait_until(lambda: started().get("status") == "running" and time.time() - started()["created"] > 0.2,
                             what="génération en cours depuis plus que le délai")
            self.assertEqual(call("GET", f"/api/job/{jid}")[0], 200)
        # délai rendu avant d'attendre la fin : avec 0,1 s, la génération finie serait oubliée entre deux
        # interrogations sur une machine lente (CI), et wait_job ne la trouverait plus
        self.assertEqual(wait_job(jid)["status"], "done")

    def test_queue_carries_the_page_token_and_nothing_that_identifies_the_generation(self):
        a = generate("SLOW=0.2 visible", steps=6, page="pageA1")["id"]
        b = generate("zq7marker secret", incognito=True, page="pageB2")["id"]
        q = call("GET", "/api/status", remote=True)[1]["queue"]
        self.assertEqual(q[1]["page"], "pageB2")
        self.assertNotIn(b, str(q))
        self.assertEqual(set(q[1]),
                         {"status", "position", "ahead", "lot", "kind", "page", "tag", "estimate", "elapsed"})
        call("POST", f"/api/job/{a}/cancel")
        call("POST", f"/api/job/{b}/cancel")

    def test_each_incognito_generation_carries_its_own_tag_that_follows_a_move(self):
        a = generate("HOLD visible", page="pageA1")["id"]
        wait_job(a, ("running",))
        b, c = (generate(f"zq7marker secret {k}", incognito=True, page="pageB2") for k in range(2))
        self.assertNotIn("tag", generate("normal", page="pageA1"))
        self.assertTrue(b["tag"] and c["tag"] and b["tag"] != c["tag"])
        self.assertNotIn(b["tag"], (b["id"], c["id"]))
        self.assertEqual(call("POST", f"/api/job/{c['id']}/first", {}), (200, {"ok": True}))
        q = call("GET", "/api/status", remote=True)[1]["queue"]
        self.assertEqual([e.get("tag") for e in q[1:3]], [c["tag"], b["tag"]])
        self.assertNotIn(b["id"], str(q))
        self.assertNotIn(c["id"], str(q))
        bench.release()
        wait_job(b["id"])

    def test_page_token_must_be_a_short_text(self):
        for page in (12, "x" * 65, ["a"]):
            self.assertEqual(call("POST", "/api/generate", bench.gen_body("x", incognito=True, page=page))[0], 400)


if __name__ == "__main__":
    unittest.main()
