"""Espace privé : création, déverrouillage propre à chaque appareil, verrouillage (à la main et après inactivité),
changement de code, suppression ; aucun secret en clair sur le disque."""
import glob, http.client, io, json, os, time, unittest
from unittest import mock

import bench
from bench import call, private_status

CODE = "Mot2passe!"


class PrivateSpaceTest(bench.PrivateFilesCheck, bench.BenchCase):
    def test_status_says_available_without_space(self):
        self.assertEqual(private_status(), {"available": True, "exists": False, "unlocked": False, "secure": True, "local": True})

    def test_code_shorter_than_8_characters_is_refused(self):
        for code in ("1234567", "", 12345678, None):
            self.assertEqual(call("POST", "/api/private/create", {"code": code})[0], 400)
        self.assertFalse(private_status()["exists"])

    def test_creation_unlocks_this_device_only(self):
        session = bench.create_private(CODE)
        self.assertEqual(private_status(session), {"available": True, "exists": True, "unlocked": True, "secure": True, "local": True})
        self.assertEqual(private_status(), {"available": True, "exists": True, "unlocked": False, "secure": True, "local": True})
        self.assertEqual(call("POST", "/api/private/create", {"code": "Autre-code-1"})[0], 409)

    def test_unlocking_again_replaces_the_session_of_this_device(self):
        first = bench.create_private(CODE)
        status, reply, headers = bench.call_full("POST", "/api/private/unlock", {"code": CODE}, private=first)
        self.assertEqual(status, 200, reply)
        self.assertEqual(list(bench.S.private_sessions), [bench.cookie_of(headers)])   # l'ancienne clé est oubliée

    def test_no_secret_in_clear_on_disk(self):
        session = bench.create_private(CODE)
        key = bench.S.private_sessions[session]["key"].private_bytes_raw()
        for fp in glob.glob(os.path.join(bench.launch.ROOT, "**", "*"), recursive=True):
            if os.path.isfile(fp) and not os.path.islink(os.path.dirname(fp)):
                raw = open(fp, "rb").read()
                self.assertNotIn(CODE.encode(), raw, fp)
                self.assertNotIn(key, raw, fp)
                self.assertNotIn(key.hex().encode(), raw, fp)
        self.assertFalse([line for line in bench.LOG if CODE in line or "/api/private" in line or "privé" in line])

    def test_wrong_code_waits_then_right_code_unlocks(self):
        bench.create_private(CODE)
        t = time.time()
        code, _, headers = bench.call_full("POST", "/api/private/unlock", {"code": "Mauvais-code"})
        self.assertEqual(code, 403)
        self.assertGreaterEqual(time.time() - t, 1)
        self.assertIsNone(bench.cookie_of(headers))
        session = bench.unlock_private(CODE)
        self.assertTrue(private_status(session)["unlocked"])

    def test_code_is_taken_as_typed(self):
        bench.create_private("Abcdefgh1")
        self.assertEqual(call("POST", "/api/private/unlock", {"code": "abcdefgh1"})[0], 403)
        self.assertEqual(call("POST", "/api/private/unlock", {"code": " Abcdefgh1"})[0], 403)

    def test_each_device_unlocks_on_its_own(self):
        bench.create_private(CODE)
        phone = bench.unlock_private(CODE, remote=True)
        self.assertTrue(private_status(phone, remote=True)["unlocked"])
        self.assertFalse(private_status()["unlocked"])
        self.assertEqual(call("POST", "/api/private/unlock", {"code": CODE}, remote=True, cookie=False)[0], 401)

    def test_lock_closes_the_session(self):
        session = bench.create_private(CODE)
        code, _, headers = bench.call_full("POST", "/api/private/lock", {}, private=session)
        self.assertEqual(code, 200)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))
        self.assertFalse(private_status(session)["unlocked"])

    def test_lock_closes_the_session_even_without_the_access_cookie(self):
        # code d'accès redemandé (cookie effacé, code changé) : le verrouillage de la page ferme quand même la session,
        # depuis le Mac, le relais et le Wi-Fi (verrouiller ne demande pas une adresse sûre)
        bench.create_private(CODE)
        for origin in ({}, {"remote": True}, {"wifi": True}):
            with self.subTest(**origin):
                session = bench.unlock_private(CODE, remote=origin.get("remote", False))
                self.assertTrue(private_status(session)["unlocked"], "session pas ouverte (prémisse)")
                code, reply, headers = bench.call_full("POST", "/api/private/lock", {}, cookie=False, private=session,
                                                       **origin)
                self.assertEqual((code, reply), (200, {"ok": True}))
                self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))
                self.assertNotIn(session, bench.S.private_sessions)

    def test_lock_ignores_its_body(self):
        # corps qu'aucune page n'envoie : très imbriqué (RecursionError de json.loads), illisible, pas un objet
        session = bench.create_private(CODE)
        bench.LOG.clear()
        bodies = (b"[" * 200000, b"pas du json", b"[]", b"")
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            for body in bodies:
                with self.subTest(body=body[:10]):
                    conn = http.client.HTTPConnection("127.0.0.1", bench.S.ui_port, timeout=30)
                    try:
                        conn.request("POST", "/api/private/lock", body=body, headers={
                            "Host": f"127.0.0.1:{bench.S.ui_port}", "Content-Type": "application/json",
                            "Cookie": f"{bench.launch.PRIVATE_COOKIE}={session}"})
                        r = conn.getresponse()
                        self.assertEqual((r.status, json.loads(r.read())), (200, {"ok": True}))
                    finally:
                        conn.close()
        self.assertNotIn(session, bench.S.private_sessions)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse([line for line in bench.LOG if "Traceback" in line or "Error" in line], bench.LOG)

    def test_lock_answers_the_same_without_cryptography(self):
        # un appareil sans le code n'apprend pas si le module de chiffrement est installé : même réponse, sans effet
        with_crypto = bench.call_full("POST", "/api/private/lock", {}, cookie=False)
        with mock.patch("launch.HAVE_CRYPTO", False):
            for cookie in (False, True):
                with self.subTest(cookie=cookie):
                    without = bench.call_full("POST", "/api/private/lock", {}, cookie=cookie)
                    self.assertEqual((without[0], without[1], without[2]["Set-Cookie"]),
                                     (with_crypto[0], with_crypto[1], with_crypto[2]["Set-Cookie"]))

    def test_lock_without_any_cookie_says_nothing_about_sessions(self):
        session = bench.create_private(CODE)
        replies = [bench.call_full("POST", "/api/private/lock", {}, cookie=False, private=other)
                   for other in (None, "jeton-inconnu")]
        replies.append(bench.call_full("POST", "/api/private/lock", {}, private="jeton-inconnu"))
        self.assertEqual({(c, json.dumps(r), h.get("Set-Cookie")) for c, r, h in replies},
                         {(200, '{"ok": true}', "qwen_private=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")})
        self.assertTrue(private_status(session)["unlocked"], "session d'un autre appareil fermée")

    def test_other_private_routes_still_need_the_access_cookie(self):
        session = bench.create_private(CODE)
        for path, body in (("/api/private/unlock", {"code": CODE}), ("/api/private/create", {"code": CODE}),
                           ("/api/private/reset", {"confirm": "SUPPRIMER"}), ("/api/private/delete", {"id": "x"}),
                           ("/api/private/keep", {"id": "x"}), ("/api/private/code", {"old": CODE, "new": "Autre-1x"}),
                           ("/api/private/prompts", {"title": "t", "text": "x", "usage": "t2i"}),
                           ("/api/private/lock/x", {}), ("/api/private/lockx", {})):
            with self.subTest(path=path):
                self.assertEqual(call("POST", path, body, cookie=False, private=session)[0], 401)
        self.assertTrue(private_status(session)["unlocked"])

    def test_lock_from_another_site_is_still_refused(self):
        session = bench.create_private(CODE)
        for headers in ({"Sec-Fetch-Site": "cross-site"}, {"Origin": "http://ailleurs.example"},
                        {"Content-Type": "text/plain"}):
            with self.subTest(**headers):
                code = call("POST", "/api/private/lock", {}, cookie=False, private=session, headers=headers)[0]
                self.assertIn(code, (403, 415))
        self.assertTrue(private_status(session)["unlocked"])

    def test_session_expires_after_inactivity_and_status_does_not_keep_it_alive(self):
        with mock.patch("launch.PRIVATE_IDLE", 0.5):
            session = bench.create_private(CODE)
            # l'interface interroge /api/status sans cesse : la session se ferme quand même, PRIVATE_IDLE après la
            # dernière requête privée (si /api/status la prolongeait, l'attente échouerait)
            bench.wait_until(lambda: call("GET", "/api/status", private=session)[0] == 200
                             and session not in bench.S.private_sessions, timeout=5, what="session fermée")
            self.assertFalse(private_status(session)["unlocked"])
            self.assertNotIn(session, bench.S.private_sessions)

    def test_change_code_draws_new_keys(self):
        bench.create_private(CODE)
        space = lambda: json.load(open(bench.launch.P("private", "space.json")))
        public = space()["public"]
        self.assertEqual(call("POST", "/api/private/code", {"old": "Mauvais-code", "new": "Nouveau-code"})[0], 403)
        self.assertEqual(call("POST", "/api/private/code", {"old": CODE, "new": "court"})[0], 400)
        self.assertEqual(space()["public"], public)
        self.assertEqual(call("POST", "/api/private/code", {"old": CODE, "new": "Nouveau-code"})[0], 200)
        self.assertNotEqual(space()["public"], public)
        self.assertEqual(call("POST", "/api/private/unlock", {"code": CODE})[0], 403)
        self.assertTrue(private_status(bench.unlock_private("Nouveau-code"))["unlocked"])

    def test_reset_needs_the_word_and_erases_everything(self):
        session = bench.create_private(CODE)
        phone = bench.unlock_private(CODE, remote=True)
        for word in (None, "supprimer", "OUI"):
            self.assertEqual(call("POST", "/api/private/reset", {"confirm": word})[0], 400)
        self.assertEqual(call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})[0], 200)
        self.assertEqual(private_status(session), {"available": True, "exists": False, "unlocked": False, "secure": True, "local": True})
        self.assertFalse(private_status(phone, remote=True)["unlocked"])
        self.assertEqual(glob.glob(bench.launch.P("private", "**", "*"), recursive=True), [])
        bench.create_private("Un-autre-code")       # puis un nouvel espace

    def test_reset_without_the_code_only_from_the_mac_itself(self):
        bench.create_private(CODE)
        phone = bench.unlock_private(CODE, remote=True)
        self.assertFalse(private_status(phone, remote=True)["local"])
        self.assertFalse(private_status(wifi=True)["local"])
        for origin in ({"remote": True}, {"wifi": True}, {"remote": True, "private": phone}):
            code, reply = call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"}, **origin)
            self.assertEqual(code, 403, origin)
            self.assertIn("Mac", reply["error"])
        self.assertTrue(private_status(phone, remote=True)["unlocked"])   # rien n'a été effacé
        self.assertTrue(private_status()["exists"])
        self.assertEqual(call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})[0], 200)

    def test_unavailable_without_cryptography(self):
        with mock.patch("launch.HAVE_CRYPTO", False):
            self.assertEqual(private_status(), {"available": False, "exists": False, "unlocked": False, "secure": True, "local": True})
            self.assertEqual(call("POST", "/api/private/create", {"code": CODE})[0], 503)
            self.assertEqual(call("POST", "/api/private/unlock", {"code": CODE})[0], 503)

    def test_an_image_stays_in_its_space(self):
        """« Rendre privée » retiré (porteur, 16/10/2026) : la route n'existe plus, l'image publique reste publique."""
        bench.create_private(CODE)
        name = bench.wait_job(bench.generate("an image that stays public")["id"])["name"]
        self.assertEqual(call("POST", "/api/private/adopt", {"name": name, "code": CODE})[0], 404)
        self.assertIn(name, [it["name"] for it in call("GET", "/api/pile")[1]])


if __name__ == "__main__":
    unittest.main()
