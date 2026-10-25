"""Comportement de base de l'API locale, sur le banc à faux moteur (voir bench.py)."""
import hashlib, io, os, subprocess, threading, unittest
from unittest import mock

import bench
from bench import call, files, gen_body, generate, journal, wait_job

ORIGINS = ({}, {"wifi": True}, {"remote": True})    # le Mac lui-même, le Wi-Fi, le relais de Tailscale


def login_page(**origin):
    """Page servie pour / sans le cookie d'accès, depuis cette origine (le Mac par défaut), en texte."""
    return bytes(call("GET", "/", cookie=False, **origin)[1]).decode()


class AccessTest(bench.BenchCase):
    def test_other_device_needs_the_access_cookie(self):
        self.assertEqual(call("GET", "/api/status", remote=True, cookie=False)[0], 401)
        self.assertEqual(call("POST", "/api/generate", gen_body(), remote=True, cookie=False)[0], 401)
        self.assertEqual(call("GET", "/api/status", remote=True)[0], 200)

    def assert_mac_needs_the_cookie(self):
        """Le Mac lui-même sans cookie : 401 pour une route, page du code pour / ; avec le cookie, il passe."""
        self.assertEqual(call("GET", "/api/status", cookie=False)[0], 401)
        self.assertEqual(call("POST", "/api/generate", gen_body(), cookie=False)[0], 401)
        self.assertEqual(call("GET", "/", cookie=False)[0], 200)
        self.assertIn('aria-label="Code d\'accès"', login_page())
        self.assertEqual(call("GET", "/api/status")[0], 200)

    def test_mac_needs_the_access_cookie_with_lan(self):
        self.assert_mac_needs_the_cookie()

    def test_mac_needs_the_access_cookie_without_lan(self):
        # sans --lan, main() ne pose ni nom du Wi-Fi ni nom HTTPS de Tailscale : seuls les noms locaux sont admis
        with mock.patch.object(bench.S, "lan_hosts", set()), mock.patch.object(bench.S, "https_hosts", set()):
            self.assert_mac_needs_the_cookie()
            # le code existe toujours, mais rien à ouvrir depuis le téléphone sans --lan
            self.assertIsNone(call("GET", "/api/status")[1]["phone"])
        self.assertEqual(call("GET", "/api/status")[1]["phone"]["code"], bench.ACCESS_CODE)

    def test_nothing_passes_without_a_loaded_code(self):
        # main() pose toujours le code ; s'il manquait, rien ne passerait, ni le Mac, ni le Wi-Fi, ni le relais
        with mock.patch.object(bench.S, "access_code", None), mock.patch.object(bench.S, "access_token", None):
            for origin in ORIGINS:
                with self.subTest(**origin):
                    self.assertEqual(call("GET", "/api/status", cookie=False, **origin)[0], 401)

    def test_cookie_of_an_already_connected_phone_stays_valid(self):
        # cookie posé avant le ticket pour le code du banc (empreinte recopiée telle quelle, nom compris)
        cookie = {"Cookie": "qwen_access=c913daf7a0df62bac32b898b2e2a7a1916edd397b7242e63f3a05fba00c86da9"}
        for origin in ORIGINS:
            with self.subTest(**origin):
                self.assertEqual(call("GET", "/api/status", cookie=False, headers=cookie, **origin)[0], 200)

    def test_end_to_end_script_presents_the_access_cookie(self):
        # tests/run_tests.py (vraies générations, jamais lancé par le banc) : sa requête lit /api/status sur le banc
        import run_tests
        path = bench.launch.ACCESS_FILE                  # repointé dans le dossier temporaire du banc
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.addCleanup(run_tests.access_cookie.cache_clear)
        with open(path, "w", encoding="utf-8") as f:
            f.write(bench.ACCESS_CODE + "\n")
        self.assertIs(run_tests.call(f"http://127.0.0.1:{bench.S.ui_port}", "/api/status")["sd_ready"], True)

    def test_end_to_end_script_stops_on_an_unreadable_code_without_showing_it(self):
        import run_tests
        path = bench.launch.ACCESS_FILE
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.addCleanup(run_tests.access_cookie.cache_clear)
        run_tests.access_cookie.cache_clear()
        with open(path, "wb") as f:
            f.write("zq-secret-1".encode("utf-16"))       # UTF-16 : illisible en UTF-8
        with self.assertRaises(SystemExit) as stop:
            run_tests.access_cookie()
        self.assertIn("tools/access_code.txt", str(stop.exception.code))
        self.assertNotIn("zq", str(stop.exception.code))

    def test_login_with_the_code_sets_the_access_cookie(self):
        code, reply, headers = bench.call_full("POST", "/api/login", {"code": bench.ACCESS_CODE}, cookie=False)
        self.assertEqual((code, reply), (200, {"ok": True}))
        cookie = headers["Set-Cookie"]
        self.assertTrue(cookie.startswith(f"qwen_access={bench.S.access_token};"), cookie)
        for flag in ("HttpOnly", "SameSite=Lax", "Max-Age=31536000", "Path=/"):
            self.assertIn(flag, cookie)
        mine = {"Cookie": cookie.split(";")[0]}
        self.assertEqual(call("GET", "/api/status", cookie=False, headers=mine)[0], 200)

    def test_login_with_a_wrong_code_is_refused(self):
        code, reply, headers = bench.call_full("POST", "/api/login", {"code": "faux-code"}, cookie=False)
        self.assertEqual(code, 403)
        self.assertIsNone(headers["Set-Cookie"])

    def test_private_space_reset_on_the_mac_needs_the_access_cookie(self):
        # réservée au Mac lui-même (sans le code privé) : sans cookie d'accès, un autre compte du Mac ne l'atteint pas
        bench.create_private("Mot2passe!")
        reply = call("POST", "/api/private/reset", {"confirm": "SUPPRIMER"}, cookie=False)
        self.assertEqual(reply[0], 401)
        self.assertTrue(bench.private_status()["exists"])

    def test_public_files_are_served_to_the_mac_without_the_access_cookie(self):
        for path in ("/manifest.webmanifest", "/sw.js", "/logo.svg", "/PixelifySans.woff2", "/icon-192.png"):
            with self.subTest(path=path):
                self.assertEqual(call("GET", path, cookie=False)[0], 200)

    def test_pixel_font_is_served_without_the_access_cookie(self):
        # demandée aussi par la page du code d'accès, avant toute saisie du code
        code, raw, hdrs = bench.call_full("GET", "/PixelifySans.woff2", remote=True, cookie=False)
        self.assertEqual((code, hdrs["Content-Type"], raw[:4]), (200, "font/woff2", b"wOF2"))
        self.assertEqual(hdrs["Cache-Control"], "no-store")

    def test_login_page_says_where_to_find_the_code(self):
        # plus de bouton « Téléphone » dans l'en-tête : le code est dans la feuille de la lampe d'état, sur le Mac
        page = login_page(remote=True)
        self.assertIn("touchez la lampe d'état, en haut à droite de l'interface", page)
        self.assertIn("« Ouvrir depuis le téléphone »", page)
        self.assertNotIn("« Téléphone »", page)
        self.assertNotIn("Sur cet ordinateur", page)      # le téléphone n'a pas de raccourci ni de fichier à lire

    def test_login_page_says_on_the_mac_how_to_enter(self):
        mac = ("Sur cet ordinateur : ouvrez Chambre noire par son raccourci, ou saisissez le code de "
               "<code>tools/access_code.txt</code>.")
        self.assertIn(mac, login_page())
        # l'adresse du Wi-Fi ouverte depuis le Mac n'est pas « le Mac lui-même » (_local) : page du téléphone
        self.assertNotIn("Sur cet ordinateur", login_page(wifi=True))

    def test_post_without_json_content_type_is_refused(self):
        self.assertEqual(call("POST", "/api/generate", gen_body(), headers={"Content-Type": "text/plain"})[0], 415)


# en-têtes Cookie où d'autres applications de 127.0.0.1 ont posé des paires mal formées ({c} : les cookies du banc)
MESSY = ("foo=bar baz; {c}", "foo; {c}", "x(y)=1; {c}", "a,b=1; {c}", 'x={{"a":1}}; {c}', "{c}; a=b c")


class CookieHeaderTest(bench.BenchCase):
    """Le Mac partage ses cookies avec tout serveur de 127.0.0.1 : une paire mal formée d'une autre application ne
    doit ni masquer le cookie d'accès ou celui de l'espace privé, ni couper la connexion."""

    def test_access_cookie_is_found_among_malformed_cookies(self):
        mine = f"qwen_access={bench.S.access_token}"
        for messy in MESSY:
            for origin in ORIGINS:
                with self.subTest(cookie=messy, **origin):
                    headers = {"Cookie": messy.format(c=mine)}
                    self.assertEqual(call("GET", "/api/status", cookie=False, headers=headers, **origin)[0], 200)

    def test_private_cookie_is_found_among_malformed_cookies(self):
        for remote in (False, True):
            session = bench.create_private("Mot2passe!") if not remote else bench.unlock_private("Mot2passe!", True)
            mine = f"qwen_access={bench.S.access_token}; qwen_private={session}"
            for messy in MESSY:
                with self.subTest(cookie=messy, remote=remote):
                    headers = {"Cookie": messy.format(c=mine)}
                    reply = call("GET", "/api/status", cookie=False, headers=headers, remote=remote)
                    self.assertTrue(reply[1]["private"]["unlocked"])

    def test_malformed_access_cookie_is_refused_without_a_stack_trace(self):
        bench.LOG.clear()
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            for value in ('"\\303\\251"', "é", "€".encode().decode("latin-1")):
                for origin in ORIGINS:
                    with self.subTest(value=value, **origin):
                        headers = {"Cookie": f"qwen_access={value}"}
                        self.assertEqual(call("GET", "/api/status", cookie=False, headers=headers, **origin)[0], 401)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse([line for line in bench.LOG if "Traceback" in line or "Error" in line], bench.LOG)


class AccessCodeFileTest(bench.BenchCase):
    """tools/access_code.txt (ACCESS_FILE, repointé dans le dossier temporaire du banc) : créé, relu, protégé."""

    def setUp(self):
        super().setUp()
        self.path = bench.launch.ACCESS_FILE
        self.addCleanup(self.remove)
        self.remove()
        for name in ("access_code", "access_token"):     # l'état du banc est rendu après chaque test
            patch = mock.patch.object(bench.S, name, None)
            patch.start()
            self.addCleanup(patch.stop)

    def remove(self):
        if os.path.isdir(self.path):
            os.rmdir(self.path)
        elif os.path.lexists(self.path):
            os.chmod(self.path, 0o600)
            os.remove(self.path)

    def content(self):
        with open(self.path, "rb") as f:
            return f.read()

    def test_setup_access_creates_the_code_and_keeps_it(self):
        # ce que prouve ce test : setup_access() crée le code, puis le reprend (main() l'appelle à chaque lancement)
        bench.launch.setup_access()
        if os.name == "posix":
            self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        code = self.content().decode().strip()
        self.assertRegex(code, r"^[a-z2-9]{4}-[a-z2-9]{4}$")
        self.assertEqual((bench.S.access_code, bench.S.access_token), (code, bench.launch.access_token(code)))
        bench.launch.setup_access()                      # relance : même code, un téléphone connecté le reste
        self.assertEqual(bench.S.access_code, code)

    def test_too_short_code_file_is_replaced(self):
        self.assertIsNone(bench.launch.read_access_code())          # absent : rien n'est créé
        self.assertFalse(os.path.exists(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("ab-12\n")                             # moins de 6 signes : refusé
        self.assertIsNone(bench.launch.read_access_code())
        code = bench.launch.load_access_code()
        self.assertRegex(code, r"^[a-z2-9]{4}-[a-z2-9]{4}$")
        self.assertEqual(bench.launch.read_access_code(), code)

    def test_unreadable_code_file_stops_the_launch_without_being_overwritten(self):
        unreadable = "zq-secret-1".encode("utf-16")         # lisible par l'homme, pas en UTF-8
        with open(self.path, "wb") as f:
            f.write(unreadable)
        with self.assertRaises(SystemExit) as stop:
            bench.launch.setup_access()
        message = str(stop.exception.code)
        self.assertIn("tools/access_code.txt", message)
        self.assertIn("supprimez", message)
        self.assertNotIn("zq", message)
        self.assertEqual(self.content(), unreadable, "fichier illisible écrasé")

    def test_code_file_replaced_by_a_folder_stops_the_launch(self):
        os.mkdir(self.path)
        with self.assertRaises(SystemExit) as stop:
            bench.launch.setup_access()
        self.assertIn("tools/access_code.txt", str(stop.exception.code))
        self.assertTrue(os.path.isdir(self.path))

    @unittest.skipUnless(os.name == "posix", "droits POSIX")
    def test_existing_code_file_is_closed_to_other_accounts(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("abcd-efgh\n")
        os.chmod(self.path, 0o644)
        self.assertEqual(bench.launch.load_access_code(), "abcd-efgh")
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_code_file_created_meanwhile_by_another_launch_is_kept(self):
        real_open, raced = os.open, []

        def other_launch_first(path, flags, mode=0o777, **kw):   # un autre lancement écrit son code juste avant
            if path == self.path and flags & os.O_EXCL:
                raced.append(path)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("abcd-efgh\n")
            return real_open(path, flags, mode, **kw)
        with mock.patch.object(bench.launch.os, "open", other_launch_first):
            code = bench.launch.load_access_code()
        self.assertEqual(raced, [self.path], "création du fichier sans os.open exclusif")
        self.assertEqual(code, "abcd-efgh")
        self.assertEqual(self.content(), b"abcd-efgh\n")

    def test_code_file_still_empty_under_another_launch_is_kept(self):
        open(self.path, "w").close()                       # créé (O_EXCL) par un autre lancement, pas encore écrit
        def write_later():
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("abcd-efgh\n")
        writer = threading.Timer(0.2, write_later)
        writer.start()
        try:
            code = bench.launch.load_access_code()
        finally:
            writer.join()
        self.assertEqual(code, "abcd-efgh", "code de l'autre lancement effacé pendant son écriture")
        self.assertEqual(self.content(), b"abcd-efgh\n")

    def test_code_file_left_empty_by_another_launch_stops_without_asking_to_delete_it(self):
        real_open = os.open

        def other_launch_first(path, flags, mode=0o777, **kw):   # un autre lancement le crée, et n'écrit pas
            if path == self.path and flags & os.O_EXCL:
                open(path, "w").close()
            return real_open(path, flags, mode, **kw)
        with mock.patch.object(bench.launch.os, "open", other_launch_first), self.assertRaises(SystemExit) as stop:
            bench.launch.setup_access()                    # (2 s d'attente de son écriture)
        self.assertNotIn("supprimez", str(stop.exception.code))
        self.assertTrue(os.path.exists(self.path), "fichier de l'autre lancement effacé")


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
