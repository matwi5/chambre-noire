"""Incognito dans la file : rien qui le trahisse aux autres appareils, image gardée jusqu'à sa page, oubli groupé."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
