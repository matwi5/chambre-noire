"""Espace privé et transport : il ne s'ouvre qu'en HTTPS (requête relayée par « tailscale serve ») ou sur le Mac
lui-même, jamais par http:// direct sur le Wi-Fi, où le code et les images passeraient en clair ; des en-têtes de relais
envoyés par un appareil du Wi-Fi n'y changent rien."""
import unittest

import bench
from bench import call, files, private_status, wait_job

CODE = "Mot2passe!"
SPOOFED = {"Host": bench.HTTPS_HOST, "X-Forwarded-For": "192.0.2.10", "X-Forwarded-Host": bench.HTTPS_HOST,
           "Tailscale-User-Login": "someone@example.com"}   # ce qu'un appareil du Wi-Fi peut envoyer en http://


class PrivateOverHttpsOnlyTest(bench.BenchCase):
    def assert_refused(self, method, path, body=None, **origin):
        code, reply = call(method, path, body, **origin)
        self.assertEqual(code, 403, (path, origin, reply))
        self.assertIn("HTTPS", reply["error"])

    def test_status_says_where_the_space_can_open(self):
        self.assertTrue(private_status()["secure"])
        self.assertTrue(private_status(remote=True)["secure"])
        self.assertFalse(private_status(wifi=True)["secure"])
        self.assertFalse(call("GET", "/api/status", wifi=True, headers=SPOOFED)[1]["private"]["secure"])

    def test_creation_over_wifi_is_refused(self):
        self.assert_refused("POST", "/api/private/create", {"code": CODE}, wifi=True)
        self.assert_refused("POST", "/api/private/create", {"code": CODE}, wifi=True, headers=SPOOFED)
        self.assertFalse(private_status()["exists"])
        self.assertEqual(files("private", "*"), [])

    def test_unlock_over_wifi_is_refused_and_accepted_over_https_and_on_the_mac(self):
        bench.create_private(CODE)
        self.assert_refused("POST", "/api/private/unlock", {"code": CODE}, wifi=True)
        self.assert_refused("POST", "/api/private/unlock", {"code": CODE}, wifi=True, headers=SPOOFED)
        self.assertTrue(private_status(bench.unlock_private(CODE, remote=True), remote=True)["unlocked"])
        self.assertTrue(private_status(bench.unlock_private(CODE))["unlocked"])

    def test_nothing_decrypted_goes_over_wifi_even_with_a_session(self):
        session = bench.create_private(CODE)
        code, job = call("POST", "/api/generate", bench.gen_body("zq9 over wifi", private=True), private=session, wifi=True)
        self.assertEqual(code, 403, job)
        code, job = call("POST", "/api/generate", bench.gen_body("zq9 on the mac", private=True), private=session)
        wait_job(job["id"], private=session)
        [item] = call("GET", "/api/private/pile", private=session)[1]
        for path in ("/api/private/history", "/api/private/pile", f"/api/private/image?id={item['id']}",
                     f"/api/private/thumb?id={item['id']}", f"/api/private/input?id={item['id']}&file=init.png"):
            self.assert_refused("GET", path, private=session, wifi=True)
        self.assert_refused("POST", "/api/private/delete", {"id": item["id"]}, private=session, wifi=True)
        self.assertEqual(len(call("GET", "/api/private/pile", private=session)[1]), 1)
        self.assertEqual(call("POST", "/api/private/lock", {}, private=session, wifi=True)[0], 200)   # verrouiller : toujours
        self.assertFalse(private_status(session)["unlocked"])

    def test_preview_of_a_private_generation_is_not_served_over_wifi(self):
        session = bench.create_private(CODE)
        code, job = call("POST", "/api/generate", bench.gen_body("SLOW=0.05 zq9 preview", private=True, preview=True, steps=10),
                         private=session)
        wait_job(job["id"], ("running",), check=lambda j: j.get("preview_version"), private=session)
        path = f"/api/job/{job['id']}/preview"
        self.assertEqual(call("GET", path, wifi=True, private=session), (404, {"error": "job inconnu"}))
        self.assertEqual(call("GET", path, remote=True, private=bench.unlock_private(CODE, remote=True))[0], 200)
        self.assertEqual(call("GET", path, private=session)[0], 200)
        wait_job(job["id"], private=session)

    def test_change_code_over_wifi_is_refused(self):
        bench.create_private(CODE)
        self.assert_refused("POST", "/api/private/code", {"old": CODE, "new": "Nouveau-code"}, wifi=True)
        self.assertEqual(call("POST", "/api/private/unlock", {"code": CODE})[0], 200)   # code inchangé



if __name__ == "__main__":
    unittest.main()
