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

    def test_post_without_json_content_type_is_refused(self):
        self.assertEqual(call("POST", "/api/generate", gen_body(), headers={"Content-Type": "text/plain"})[0], 415)


class GenerationTest(bench.BenchCase):
    def test_generation_runs_to_the_end(self):
        j = wait_job(generate("a red car")["id"])
        self.assertEqual(j["status"], "done")
        self.assertEqual(j["dims"], [512, 512])
        self.assertTrue(os.path.isfile(j["path"]))
        self.assertEqual(journal()[-1]["prompt"], "a red car")
        names = [it["name"] for it in call("GET", "/api/history")[1]]
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
        self.assertEqual(files("outputs", "*.png"), [])

    def test_edit_keeps_its_input_images(self):
        j = wait_job(generate("make it blue", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"])
        self.assertEqual(j["status"], "done")
        item = next(it for it in call("GET", "/api/history")[1] if it["name"] == j["name"])
        self.assertEqual(item["inputs"], ["ref_1.png"])


class CancelTest(bench.BenchCase):
    def test_cancel_a_queued_generation(self):
        first = generate("SLOW a slow one")["id"]
        second = generate("waiting one")["id"]
        self.assertEqual(call("POST", f"/api/job/{second}/cancel")[1]["status"], "cancelled")
        self.assertEqual(wait_job(first)["status"], "done")
        bench.wait_idle()
        self.assertEqual(bench.job(second)["status"], "cancelled")
        self.assertEqual(len(files("outputs", "*.png")), 1)
        self.assertEqual(files("jobs", second), [])

    def test_cancel_the_running_generation(self):
        jid = generate("SLOW a slow one", steps=20)["id"]
        wait_job(jid, ("running",), check=lambda j: (j.get("step") or 0) >= 1)
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[1]["status"], "cancelled")
        bench.wait_idle()                           # « cancelled » est posé avant l'arrêt du moteur
        self.assertEqual(files("outputs", "*.png"), [])
        self.assertEqual(files("jobs", jid), [])
        self.assertEqual(journal(), [])


class IncognitoTest(bench.BenchCase):
    def test_incognito_image_is_delivered_once_then_forgotten(self):
        jid = generate("a secret garden", incognito=True)["id"]
        j = wait_job(jid)
        self.assertEqual((j["status"], j["incognito"], j["path"]), ("done", True, None))
        bench.wait_idle()
        code, raw = call("GET", f"/api/job/{jid}/result")
        self.assertEqual((code, raw[:4]), (200, b"\x89PNG"))
        self.assertEqual(files("outputs", "*.png"), [])
        self.assertEqual(files("jobs", "incognito_*"), [])
        self.assertEqual(journal(), [])
        self.assertEqual(call("POST", f"/api/job/{jid}/forget")[0], 200)
        self.assertEqual(call("GET", f"/api/job/{jid}/result")[0], 404)
        self.assertEqual(call("GET", f"/api/job/{jid}")[0], 404)

    def test_status_never_resumes_an_incognito_generation(self):
        wait_job(generate("visible")["id"])
        wait_job(generate("hidden", incognito=True)["id"])
        self.assertEqual(call("GET", "/api/status")[1]["last_job"]["incognito"], False)


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

    def test_incognito_and_failure_messages(self):
        with bench.capture_push() as sent:
            wait_job(generate("zq7marker hidden", incognito=True)["id"])
            sent.wait(1)
            wait_job(generate("FAIL zq7marker broken")["id"])
            sent.wait(2)
        self.assertEqual([m["title"] for m in sent], ["Image incognito prête", "Échec de la génération"])
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
