"""Prompts enregistrés de l'espace privé : routes /api/private/prompts, fichier scellé private/prompts, sur le banc
(voir bench.py). Chaque espace ne voit que ses prompts enregistrés, et les prompts types."""
import contextlib, os, unittest
from unittest import mock

import bench
from bench import call, launch
from test_private_rekey import failing, no_cleanup

CODE, NEW = "Code-prive-1", "Code-prive-2"


def read(fp):
    with open(fp, "rb") as f:
        return f.read()


class PrivatePromptsCase(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        if os.path.exists(launch.PROMPTS_FILE):
            os.remove(launch.PROMPTS_FILE)
        self.session = bench.create_private(CODE)

    def saved(self, session=None):
        code, reply = call("GET", "/api/private/prompts", private=session or self.session)
        self.assertEqual(code, 200, reply)
        return reply["saved"]

    def create(self, title="Ciel violet", text="Replace the sky with a violet dusk", usage="edit", session=None):
        code, p = call("POST", "/api/private/prompts", {"title": title, "text": text, "usage": usage},
                       private=session or self.session)
        self.assertEqual(code, 200, p)
        return p


class PrivatePromptsTest(PrivatePromptsCase):
    def test_a_private_prompt_is_listed_in_the_private_space_only(self):
        self.assertEqual(self.saved(), [])
        p = self.create("Ciel violet", "Replace the sky with a violet dusk", "edit")
        self.assertEqual((p["title"], p["text"], p["usage"]),
                         ("Ciel violet", "Replace the sky with a violet dusk", "edit"))
        self.assertEqual(self.saved(), [p])
        self.assertEqual(call("GET", "/api/prompts")[1]["saved"], [])

    def test_public_prompts_stay_out_of_the_private_space(self):
        code, pub = call("POST", "/api/prompts", {"title": "Public", "text": "a public prompt", "usage": "t2i"})
        self.assertEqual(code, 200, pub)
        p = self.create()
        self.assertEqual(self.saved(), [p])
        self.assertEqual(call("GET", "/api/prompts")[1]["saved"], [pub])
        for path in ("/api/prompts/used", "/api/prompts/delete"):   # chaque liste ne touche que ses prompts
            self.assertEqual(call("POST", path, {"id": p["id"]})[0], 404)
            self.assertEqual(call("POST", "/api/private" + path[4:], {"id": pub["id"]}, private=self.session)[0], 404)
        self.assertEqual(call("POST", "/api/prompts", {"id": p["id"], "title": "x", "text": "x"})[0], 404)
        self.assertEqual(call("POST", "/api/private/prompts", {"id": pub["id"], "title": "x", "text": "x"},
                              private=self.session)[0], 404)
        self.assertEqual((self.saved(), call("GET", "/api/prompts")[1]["saved"]), ([p], [pub]))

    def test_the_prompt_types_are_listed_in_both_spaces_and_can_be_duplicated(self):
        types = call("GET", "/api/private/prompts", private=self.session)[1]["types"]
        self.assertEqual(types, call("GET", "/api/prompts")[1]["types"])
        self.assertEqual(len(types), 11)
        t = types[7]
        self.assertEqual(call("POST", "/api/private/prompts/used", {"id": t["id"]}, private=self.session)[0], 404)
        p = self.create(t["title"], t["text"], t["usage"])           # « Dupliquer » dans l'espace privé
        self.assertNotEqual(p["id"], t["id"])
        self.assertEqual(self.saved(), [p])
        self.assertEqual(call("GET", "/api/prompts")[1]["saved"], [])

    def test_modify_delete_and_use_like_public_prompts(self):
        a, b, c = self.create("A", "first", "t2i"), self.create("B", "second", "mask"), self.create("C", "third")
        self.assertEqual([p["title"] for p in self.saved()], ["C", "B", "A"])   # un prompt créé passe en tête
        code, used = call("POST", "/api/private/prompts/used", {"id": a["id"]}, private=self.session)
        self.assertEqual((code, used["id"]), (200, a["id"]))
        self.assertGreater(used["used"], c["used"])
        self.assertEqual([p["title"] for p in self.saved()], ["A", "C", "B"])
        code, q = call("POST", "/api/private/prompts",
                       {"id": b["id"], "title": " B du soir ", "text": "red", "usage": "t2i"}, private=self.session)
        self.assertEqual((code, q), (200, {**b, "title": "B du soir", "text": "red"}))   # même usage, même utilisation
        self.assertEqual(call("POST", "/api/private/prompts/delete", {"id": c["id"]}, private=self.session),
                         (200, {"ok": True}))
        self.assertEqual(self.saved(), [used, q])
        self.assertEqual(call("POST", "/api/private/prompts/delete", {"id": c["id"]}, private=self.session)[0], 404)
        self.assertEqual(call("POST", "/api/private/prompts/used", {"id": "inconnu"}, private=self.session)[0], 404)

    def test_same_limits_and_validation_as_public_prompts(self):
        p = self.create("Gardé", "kept")
        for body in ({"title": "", "text": "x", "usage": "t2i"}, {"title": "x" * 81, "text": "x", "usage": "t2i"},
                     {"title": "x", "text": "x" * 4001, "usage": "t2i"}, {"title": "x", "text": "x", "usage": "hist"},
                     {"id": 12, "title": "x", "text": "x"}, []):
            with self.subTest(body=body):
                self.assertEqual(call("POST", "/api/private/prompts", body, private=self.session)[0], 400)
        for path in ("/api/private/prompts/delete", "/api/private/prompts/used"):
            self.assertEqual(call("POST", path, {}, private=self.session)[0], 400)
        with mock.patch.object(launch, "MAX_SAVED_PROMPTS", 2):
            self.create("B", "b")
            self.assertEqual(call("POST", "/api/private/prompts", {"title": "C", "text": "c", "usage": "t2i"},
                                  private=self.session)[0], 400)
        self.assertEqual([x["title"] for x in self.saved()], ["B", "Gardé"])
        self.assertEqual(self.saved()[1], p)

    def test_another_device_in_the_private_space_sees_the_same_prompts(self):
        p = self.create()
        phone = bench.unlock_private(CODE, remote=True)
        code, reply = call("GET", "/api/private/prompts", remote=True, private=phone)
        self.assertEqual((code, reply["saved"]), (200, [p]))


class PrivatePromptsFileTest(PrivatePromptsCase):
    def test_the_file_is_sealed_and_readable_by_its_owner_only(self):
        self.create("Titre secret zq7", "Texte secret zq7")
        fp = launch.P("private", "prompts")
        self.assertEqual(read(fp)[:4], b"QPV1")
        if os.name == "posix":
            self.assertEqual(os.stat(fp).st_mode & 0o777, 0o600)
        for root, _, names in os.walk(launch.P("private")):         # rien en clair dans l'espace privé
            for n in names:
                self.assertNotIn(b"zq7", read(os.path.join(root, n)), n)
        self.assertEqual(sorted(os.listdir(launch.P("private"))), ["prompts", "space.json"])

    def test_no_prompt_file_until_one_is_saved(self):
        self.assertEqual(self.saved(), [])
        self.assertFalse(os.path.exists(launch.P("private", "prompts")))

    def test_an_unreadable_file_is_reported_and_never_overwritten(self):
        self.create()
        fp = launch.P("private", "prompts")
        for content in (b"QPV1" + b"\0" * 60, b"[]"):                # altéré, ou pas scellé
            with self.subTest(content=content):
                with open(fp, "wb") as f:
                    f.write(content)
                self.assertEqual(call("GET", "/api/private/prompts", private=self.session)[0], 500)
                self.assertEqual(call("POST", "/api/private/prompts", {"title": "A", "text": "a", "usage": "t2i"},
                                      private=self.session)[0], 500)
                self.assertEqual(read(fp), content)

    def test_the_file_is_never_half_written(self):
        """Panne à chaque point d'écriture (au milieu du fichier temporaire, droits, remplacement), en erreur et en
        interruption : le fichier reste l'ancien, entier, et rien ne traîne."""
        p = self.create()
        fp = launch.P("private", "prompts")
        before = read(fp)

        def half(path, data, full=True):                             # panne au milieu de l'écriture
            with open(path, "wb") as f:
                f.write(data[:len(data) // 2])
            raise error
        points = ((launch, "write_synced", half), (os, "chmod", None), (os, "replace", None))
        for module, name, fake in points:
            for error in (OSError("disque plein"), KeyboardInterrupt()):
                with self.subTest(point=name, error=type(error).__name__):
                    # interruption : elle remonte jusqu'au fil de la requête, sans trace à l'écran
                    with mock.patch.object(module, name, fake or mock.Mock(side_effect=error)), \
                            mock.patch.object(bench.threading, "excepthook", lambda args: None):
                        try:
                            code = call("POST", "/api/private/prompts",
                                        {"title": "Perdu", "text": "lost", "usage": "t2i"}, private=self.session)[0]
                        except Exception:                # interruption : le serveur ferme la connexion sans répondre
                            code = None
                    if isinstance(error, OSError):
                        self.assertEqual(code, 500)
                    self.assertEqual(read(fp), before)
                    self.assertEqual(self.saved(), [p])
                    self.assertEqual(sorted(os.listdir(launch.P("private"))), ["prompts", "space.json"])

    def test_nothing_goes_to_the_server_logs(self):
        del bench.LOG[:]
        p = self.create("Titre zq8", "Texte zq8")
        call("POST", "/api/private/prompts", {"id": p["id"], "title": "Autre zq8", "text": "zq8"}, private=self.session)
        call("POST", "/api/private/prompts/used", {"id": p["id"]}, private=self.session)
        self.saved()
        call("POST", "/api/private/prompts/delete", {"id": p["id"]}, private=self.session)
        call("GET", "/api/private/prompts", private="session-inconnue")
        logged = "\n".join(bench.LOG)
        self.assertNotIn("zq8", logged)
        self.assertNotIn("prompts", logged)


class PrivatePromptsLifeTest(PrivatePromptsCase):
    def opens(self, code):
        status, _, headers = bench.call_full("POST", "/api/private/unlock", {"code": code})
        return bench.cookie_of(headers) if status == 200 else None

    def change_code(self):
        return bench.call_full("POST", "/api/private/code", {"old": CODE, "new": NEW})[0]

    def test_after_a_code_change_the_new_code_reads_them_and_an_old_copy_of_the_keys_does_not(self):
        p, q = self.create("A", "first"), self.create("B", "second")
        space = launch.P("private", "space.json")
        backup = read(space)                          # sauvegarde des clés d'avant le changement
        old_key = bench.S.private_sessions[self.session]["key"]
        self.assertEqual(self.change_code(), 200)
        new = self.opens(NEW)
        self.assertEqual(self.saved(new), [q, p])
        self.assertEqual(bench.assert_old_key_opens_nothing(self, old_key, bench.S.private_sessions[new]["key"]), 1)
        self.assertEqual(sorted(os.listdir(launch.P("private"))), ["prompts", "space.json"])
        if os.name == "posix":
            self.assertEqual(os.stat(launch.P("private", "prompts")).st_mode & 0o777, 0o600)
        with open(space, "wb") as f:
            f.write(backup)
        self.assertEqual(call("GET", "/api/private/prompts", private=self.opens(CODE))[0], 500)

    def test_a_leftover_from_an_interrupted_save_does_not_survive_a_code_change(self):
        """Fichier temporaire laissé par une coupure de courant pendant un enregistrement : scellé avec l'ancienne clé,
        il ne doit pas rester lisible avec l'ancien code."""
        self.create()
        leftover = launch.P("private", "prompts.tmp")
        with open(leftover, "wb") as f:
            f.write(read(launch.P("private", "prompts")))
        old_key = bench.S.private_sessions[self.session]["key"]
        self.assertEqual(self.change_code(), 200)
        self.assertFalse(os.path.exists(leftover))
        self.assertEqual(bench.assert_old_key_opens_nothing(self, old_key), 1)

    def test_an_unreadable_file_is_kept_as_is_through_a_code_change(self):
        self.create()
        fp = launch.P("private", "prompts")
        damaged = b"QPV1" + b"\1" * 60
        with open(fp, "wb") as f:
            f.write(damaged)
        self.assertEqual(self.change_code(), 200)
        self.assertEqual(read(fp), damaged)

    def test_a_failure_halfway_loses_no_prompt(self):
        """Panne à chaque étape d'écriture du changement de code (rechiffrement des prompts, bascule, rangement des
        prompts), avec ou sans arrêt brutal : un seul des deux codes ouvre l'espace, et ses prompts sont tous là."""
        steps = [(launch, "seal", 1), (os, "replace", 2), (os, "replace", 3)]
        for module, name, k in steps:
            for crash in (False, True):
                with self.subTest(f"{name} n°{k}" + (", arrêt brutal" if crash else "")):
                    self.setUp()
                    before = [self.create("A", "first"), self.create("B", "second")][::-1]
                    with failing(module, name, k) as calls, no_cleanup() if crash else contextlib.nullcontext():
                        status = self.change_code()
                    if not crash:
                        self.assertGreaterEqual(calls[0], k, "la panne n'a pas eu lieu")
                    self.assertEqual(status, 500)
                    old, new = self.opens(CODE), self.opens(NEW)
                    self.assertEqual([old is not None, new is not None].count(True), 1, (old, new))
                    self.assertEqual(self.saved(old or new), before)
                    self.assertEqual(sorted(os.listdir(launch.P("private"))), ["prompts", "space.json"])

    def test_they_go_with_the_private_space(self):
        self.create()
        self.assertEqual(call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"})[0], 200)
        self.assertFalse(os.path.exists(launch.P("private")))
        self.assertEqual(self.saved(bench.create_private(CODE)), [])


class PrivatePromptsAccessTest(PrivatePromptsCase):
    ROUTES = (("GET", "/api/private/prompts", None),
              ("POST", "/api/private/prompts", {"title": "x", "text": "x", "usage": "t2i"}),
              ("POST", "/api/private/prompts/delete", {"id": "x"}), ("POST", "/api/private/prompts/used", {"id": "x"}))

    def test_refused_without_a_session(self):
        p = self.create()
        call("POST", "/api/private/lock", {}, private=self.session)
        for method, path, body in self.ROUTES:
            with self.subTest(path=path):
                self.assertEqual(call(method, path, body, private=self.session)[0], 403)
                self.assertEqual(call(method, path, body)[0], 403)
        self.assertEqual(self.saved(bench.unlock_private(CODE)), [p])

    def test_refused_over_plain_wifi_even_with_a_session(self):
        p = self.create()
        spoofed = {"Host": bench.HTTPS_HOST, "X-Forwarded-For": "192.0.2.10", "X-Forwarded-Host": bench.HTTPS_HOST}
        for method, path, body in self.ROUTES:
            for headers in (None, spoofed):
                with self.subTest(path=path, headers=headers):
                    code, reply = call(method, path, body, private=self.session, wifi=True, headers=headers)
                    self.assertEqual(code, 403, reply)
                    self.assertIn("HTTPS", reply["error"])
        self.assertEqual(self.saved(), [p])

    def test_post_routes_follow_the_access_rules(self):
        p = self.create()
        for method, path, body in self.ROUTES:
            with self.subTest(path=path):
                self.assertEqual(call(method, path, body, remote=True, cookie=False, private=self.session)[0], 401)
                if method == "POST":
                    self.assertEqual(call(method, path, body, private=self.session,
                                          headers={"Content-Type": "text/plain"})[0], 415)
                    self.assertEqual(call(method, path, body, private=self.session,
                                          headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.saved(), [p])

    def test_a_session_key_replaced_by_a_code_change_neither_reads_nor_writes(self):
        """Requête dont la session a été lue juste avant un changement de code : sa clé n'est plus celle de l'espace."""
        p = self.create()
        stale = launch.S.private_sessions[self.session]
        status = bench.call_full("POST", "/api/private/code", {"old": CODE, "new": NEW})[0]
        self.assertEqual(status, 200)
        launch.S.private_sessions[self.session] = stale
        self.assertEqual(call("GET", "/api/private/prompts", private=self.session)[0], 403)
        self.assertEqual(call("POST", "/api/private/prompts", {"title": "A", "text": "a", "usage": "t2i"},
                              private=self.session)[0], 403)
        self.assertEqual(self.saved(bench.unlock_private(NEW)), [p])


if __name__ == "__main__":
    unittest.main()
