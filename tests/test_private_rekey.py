"""Changer le code privé : une nouvelle paire de clés, toutes les images privées rechiffrées, toutes les sessions
fermées ; une ancienne copie des clés (space.json) ne lit plus rien avec l'ancien code, et une panne au milieu du
rechiffrement ne perd aucune image ni ne laisse l'espace illisible."""
import contextlib, json, os, shutil, sys, unittest
from unittest import mock

import bench
from bench import call, wait_job

OLD, NEW = "Ancien-code-1", "Nouveau-code-2"


@contextlib.contextmanager
def failing(module, name, k):
    """Le k-ième appel de module.name lève OSError (panne simulée) ; les autres passent. Donne le compteur d'appels."""
    original, calls = getattr(module, name), [0]

    def wrapper(*a, **kw):
        calls[0] += 1
        if calls[0] == k:
            raise OSError("panne simulée")
        return original(*a, **kw)
    with mock.patch.object(module, name, wrapper):
        yield calls


@contextlib.contextmanager
def no_cleanup():
    """Arrêt brutal du serveur au moment de la panne : rien de ce qu'il avait commencé n'est rangé ni supprimé."""
    with mock.patch.object(shutil, "rmtree", lambda *a, **kw: None):
        yield


class ChangeCodeTest(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        session = bench.create_private(OLD)
        self.ref = bench.png_bytes(70, 50)
        jobs = [call("POST", "/api/generate", bench.gen_body(p, private=True, **kw), private=session)[1]
                for p, kw in (("zq9 first", {}), ("zq9 second", {"mode": "edit", "ref_images": [bench.data_url(self.ref)]}))]
        for j in jobs:
            self.assertEqual(wait_job(j["id"], private=session)["status"], "done")
        bench.wait_idle()
        self.before = self.contents(session)
        self.assertEqual(len(self.before), 2)

    def contents(self, session):
        """Ce que l'espace privé montre avec cette session, par prompt : réglages, image, miniature, entrées."""
        out = {}
        code, items = call("GET", "/api/private/pile", private=session)
        self.assertEqual(code, 200, items)
        for it in items:
            read = lambda path: call("GET", path, private=session)
            image, thumb = read(f"/api/private/image?id={it['id']}"), read(f"/api/private/thumb?id={it['id']}")
            self.assertEqual((image[0], thumb[0]), (200, 200))
            inputs = [read(f"/api/private/input?id={it['id']}&file={n}")[1] for n in it["inputs"]]
            settings = {k: v for k, v in it.items() if k != "id"}
            out[it["prompt"]] = (settings, image[1], thumb[1], inputs)
        return out

    def change(self, old=OLD, new=NEW):
        return bench.call_full("POST", "/api/private/code", {"old": old, "new": new})

    def opens(self, code):
        status, _, headers = bench.call_full("POST", "/api/private/unlock", {"code": code})
        return bench.cookie_of(headers) if status == 200 else None

    def test_new_code_reads_every_image_and_all_sessions_close(self):
        mac, phone = bench.unlock_private(OLD), bench.unlock_private(OLD, remote=True)
        old_key = bench.S.private_sessions[mac]["key"]
        status, reply, headers = bench.call_full("POST", "/api/private/code", {"old": OLD, "new": NEW}, private=mac)
        self.assertEqual(status, 200, reply)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie", ""))
        self.assertFalse(bench.private_status(mac)["unlocked"])
        self.assertFalse(bench.private_status(phone, remote=True)["unlocked"])
        self.assertEqual(bench.S.private_sessions, {})
        self.assertIsNone(self.opens(OLD))
        new = self.opens(NEW)
        self.assertEqual(self.contents(new), self.before)
        self.assertEqual(sorted(os.listdir(bench.launch.P("private"))), ["items", "space.json"])
        self.assertEqual(bench.assert_old_key_opens_nothing(self, old_key, bench.S.private_sessions[new]["key"]), 7)

    def test_an_old_copy_of_the_keys_no_longer_reads_the_images(self):
        space = bench.launch.P("private", "space.json")
        backup = open(space, "rb").read()                  # sauvegarde (Time Machine, copie du disque) d'avant le changement
        self.assertEqual(self.change()[0], 200)
        ids = [it["id"] for it in call("GET", "/api/private/pile", private=self.opens(NEW))[1]]
        self.assertEqual(json.loads(backup)["public"] == json.load(open(space))["public"], False)
        with open(space, "wb") as f:
            f.write(backup)
        session = self.opens(OLD)                          # l'ancienne clé privée se déchiffre encore avec l'ancien code…
        self.assertIsNotNone(session)
        self.assertEqual(call("GET", "/api/private/pile", private=session)[1], [])   # … mais n'ouvre plus aucune image
        for item in ids:
            for kind in ("image", "thumb"):
                self.assertNotEqual(call("GET", f"/api/private/{kind}?id={item}", private=session)[0], 200)

    def test_a_private_generation_running_during_the_change_is_kept(self):
        session = bench.unlock_private(OLD)
        job = call("POST", "/api/generate", bench.gen_body("SLOW=0.05 zq9 during", steps=10, private=True), private=session)[1]
        wait_job(job["id"], ("running",), private=session)
        self.assertEqual(self.change()[0], 200)          # toutes les sessions fermées : suivie avec le nouveau code
        session = self.opens(NEW)
        self.assertEqual(wait_job(job["id"], private=session)["status"], "done")
        after = self.contents(session)
        self.assertEqual(sorted(after), ["SLOW=0.05 zq9 during", "zq9 first", "zq9 second"])

    def test_wrong_old_code_or_short_new_code_changes_nothing(self):
        self.assertEqual(self.change(old="Mauvais-code")[0], 403)
        self.assertEqual(self.change(new="court")[0], 400)
        self.assertEqual(self.contents(self.opens(OLD)), self.before)

    def test_a_failure_halfway_loses_no_image(self):
        """Panne simulée à chaque étape d'écriture (rechiffrement d'un fichier, écriture des nouvelles clés, bascule,
        rangement des images), avec ou sans arrêt brutal : exactement un des deux codes ouvre l'espace, qui montre
        toutes les images, intactes, et rien ne traîne une fois l'espace rouvert."""
        launch = bench.launch
        steps = [(launch, "seal", 1), (launch, "seal", 4), (launch, "seal", 7), (os, "replace", 1), (os, "replace", 2),
                 (os, "rename", 1), (os, "rename", 2)]
        for module, name, k in steps:
            for crash in (False, True):
                with self.subTest(f"{name} n°{k}" + (", arrêt brutal" if crash else "")):
                    self.setUp()
                    old_key = bench.S.private_sessions[self.opens(OLD)]["key"]
                    with failing(module, name, k) as calls, no_cleanup() if crash else contextlib.nullcontext():
                        status, reply, _ = self.change()
                    if not crash:                  # sans ménage, un rangement peut échouer de lui-même avant le k-ième appel
                        self.assertGreaterEqual(calls[0], k, "la panne n'a pas eu lieu")
                    self.assertEqual(status, 500, reply)
                    old, new = self.opens(OLD), self.opens(NEW)
                    self.assertEqual([old is not None, new is not None].count(True), 1, (old, new))
                    self.assertEqual(self.contents(old or new), self.before)
                    if new:                        # le nouveau code l'a emporté : l'ancienne clé n'ouvre plus rien
                        self.assertGreater(bench.assert_old_key_opens_nothing(self, old_key), 0)
                    self.assertEqual(sorted(os.listdir(launch.P("private"))), ["items", "space.json"])
                    self.assertTrue(all(launch.ITEM_RE.fullmatch(n) for n in os.listdir(launch.P("private", "items"))))


if __name__ == "__main__":
    unittest.main()
