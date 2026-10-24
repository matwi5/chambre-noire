"""Comportement de base de l'API locale, sur le banc à faux moteur (voir bench.py)."""
import hashlib, os, subprocess, unittest
from unittest import mock

import bench
from bench import call, files, gen_body, generate, journal, wait_job


class AccessTest(bench.BenchCase):
    def test_other_device_needs_the_access_cookie(self):
        self.assertEqual(call("GET", "/api/status", remote=True, cookie=False)[0], 401)
        self.assertEqual(call("POST", "/api/generate", gen_body(), remote=True, cookie=False)[0], 401)
        self.assertEqual(call("GET", "/api/status", remote=True)[0], 200)

    def test_pixel_font_is_served_without_the_access_cookie(self):
        # demandée aussi par la page du code d'accès, avant toute saisie du code
        code, raw, hdrs = bench.call_full("GET", "/PixelifySans.woff2", remote=True, cookie=False)
        self.assertEqual((code, hdrs["Content-Type"], raw[:4]), (200, "font/woff2", b"wOF2"))
        self.assertEqual(hdrs["Cache-Control"], "no-store")

    def test_login_page_says_where_to_find_the_code(self):
        # plus de bouton « Téléphone » dans l'en-tête : le code est dans la feuille de la lampe d'état, sur le Mac
        page = bytes(call("GET", "/", remote=True, cookie=False)[1]).decode()
        self.assertIn("touchez la lampe d'état, en haut à droite de l'interface", page)
        self.assertIn("« Ouvrir depuis le téléphone »", page)
        self.assertNotIn("« Téléphone »", page)

    def test_post_without_json_content_type_is_refused(self):
        self.assertEqual(call("POST", "/api/generate", gen_body(), headers={"Content-Type": "text/plain"})[0], 415)


class GenerationTest(bench.BenchCase):
    def test_generation_runs_to_the_end(self):
        j = wait_job(generate("a red car")["id"])
        self.assertEqual(j["status"], "done")
        self.assertEqual(j["dims"], [512, 512])
        self.assertTrue(os.path.isfile(j["path"]))
        self.assertEqual(journal()[-1]["prompt"], "a red car")
        names = [it["name"] for it in call("GET", "/api/pile")[1]]
        self.assertIn(j["name"], names)
        code, raw = call("GET", "/api/result?name=" + j["name"])
        self.assertEqual((code, raw[:8]), (200, b"\x89PNG\r\n\x1a\n"))

    def test_progress_and_preview_are_reported(self):
        jid = generate("SLOW=0.1 a cat", steps=10, preview=True)["id"]
        j = wait_job(jid, ("running", "done"), check=lambda j: (j.get("preview_version") or 0) >= 1)
        self.assertGreaterEqual(j["step"], 5)
        code, raw = call("GET", f"/api/job/{jid}/preview")
        self.assertEqual((code, raw[:4]), (200, b"\x89PNG"))
        self.assertEqual(wait_job(jid)["status"], "done")

    def test_engine_failure_fails_the_generation(self):
        j = wait_job(generate("FAIL")["id"])
        self.assertEqual(j["status"], "failed")
        self.assertIn("panne simulée", j["error"])
        self.assertEqual(files("outputs", ".pile", "*.png"), [])

    def test_edit_keeps_its_input_images(self):
        j = wait_job(generate("make it blue", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"])
        self.assertEqual(j["status"], "done")
        item = next(it for it in call("GET", "/api/pile")[1] if it["name"] == j["name"])
        self.assertEqual(item["inputs"], ["ref_1.png"])

    def test_inputs_the_engine_cannot_read_are_converted_to_png(self):
        # WebP, AVIF, TIFF : lus par le navigateur et par Pillow, pas par sd-cli (stb_image)
        for fmt in ("WEBP", "AVIF", "TIFF"):
            with self.subTest(fmt=fmt):
                img = bench.data_url(bench.png_bytes(fmt=fmt))
                j = wait_job(generate("edit it", mode="edit", ref_images=[img])["id"])
                self.assertEqual(j["status"], "done", j.get("error"))
                j = wait_job(generate("fix it", mode="mask", init_image=img, mask_image=img)["id"])
                self.assertEqual(j["status"], "done", j.get("error"))
        kept = files("outputs", ".inputs", "*", "*.png")
        self.assertEqual(len(kept), 6)
        for fp in kept:
            with open(fp, "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n", fp)

class CancelTest(bench.BenchCase):
    def test_cancel_a_queued_generation(self):
        first = generate("SLOW a slow one")["id"]
        second = generate("waiting one")["id"]
        self.assertEqual(call("POST", f"/api/job/{second}/cancel")[1]["status"], "cancelled")
        self.assertEqual(wait_job(first)["status"], "done")
        bench.wait_idle()
        self.assertEqual(bench.job(second)["status"], "cancelled")
        self.assertEqual(len(files("outputs", ".pile", "*.png")), 1)
        self.assertEqual(files("jobs", second), [])

    def test_cancel_the_running_generation(self):
        jid = generate("SLOW a slow one", steps=20)["id"]
        wait_job(jid, ("running",), check=lambda j: (j.get("step") or 0) >= 1)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "cancelled")
        bench.wait_idle()                           # « cancelled » est posé avant l'arrêt du moteur
        self.assertEqual(files("outputs", ".pile", "*.png"), [])
        self.assertEqual(files("jobs", jid), [])
        self.assertEqual(journal(), [])


class NotificationTest(bench.BenchCase):
    def assertNoPrompt(self, msg, marker):
        self.assertEqual(set(msg), {"title", "body", "tag", "url"})
        self.assertNotIn(marker, str(msg))

    def test_end_of_generation_notification_has_no_prompt(self):
        with bench.capture_push() as sent:
            j = wait_job(generate("zq7marker a car")["id"])
            sent.wait(1)
        self.assertEqual(sent[0]["title"], "Image prête")
        self.assertNoPrompt(sent[0], "zq7marker")
        self.assertNotIn(j["name"], str(sent[0]))

    def test_failure_message(self):
        with bench.capture_push() as sent:
            wait_job(generate("FAIL zq7marker broken")["id"])
            sent.wait(1)
        self.assertEqual([m["title"] for m in sent], ["Échec de la génération"])
        for msg in sent:
            self.assertNoPrompt(msg, "zq7marker")


class VersionTest(bench.BenchCase):
    """Version du code servie par /api/status (panneau Moteur) : le dernier commit du dossier, relu périodiquement."""

    def test_status_reports_the_served_code(self):
        status = call("GET", "/api/status")[1]
        self.assertIn("version", status)                 # le banc sert un dossier temporaire hors git : None
        self.assertIsNone(status["server_version"])      # main() n'est pas lancé par le banc

    def test_version_is_the_last_commit_of_the_folder(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        head = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h %cs"], capture_output=True, text=True,
                              check=True).stdout.split()
        digest = hashlib.sha1()
        for name in ("launch.py", "estimate.py"):         # le code que le serveur charge à son lancement
            with open(os.path.join(repo, "tools", name), "rb") as f:
                digest.update(f.read())
        with mock.patch.object(bench.launch, "ROOT", repo), mock.patch.dict(bench.launch._version, root=None):
            version = bench.launch.code_version()
        self.assertEqual([version["commit"], version["date"], version["server"]], head + [digest.hexdigest()[:12]])

    def test_git_is_not_called_outside_a_repository(self):
        """Sur un Mac sans outils de développement, /usr/bin/git ouvre une fenêtre : jamais hors d'un dépôt git."""
        with mock.patch.object(bench.launch.subprocess, "run", wraps=subprocess.run) as run, \
                mock.patch.dict(bench.launch._version, root=None):
            version = bench.launch.code_version()           # le banc sert un dossier temporaire, sans .git
        self.assertFalse([c for c in run.call_args_list if "git" in c.args[0]])   # les autres appels passent
        self.assertIsNone(version["commit"])


if __name__ == "__main__":
    unittest.main()
