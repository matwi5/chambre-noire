"""Entrée depuis l'ordinateur sans taper le code d'accès : jeton à usage unique de launch.py --enter (tools/entry_token,
60 s) et sa page de redirection (tools/entry.html) vers GET /entrer, qui pose le cookie d'accès (voir bench.py)."""
import contextlib, io, os, re, shutil, subprocess, sys, time, unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import bench
from bench import call

launch = bench.launch


def get(path, origin="mac", host=None):
    """GET sans cookie ni redirection suivie : (code, en-têtes, corps en texte). origin : « mac » (le Mac lui-même),
    « wifi » ou « remote » (les origines de bench.call) ; host : nom d'hôte envoyé à la place."""
    code, reply, headers = bench.call_full("GET", path, cookie=False, follow=False, wifi=origin == "wifi",
                                           remote=origin == "remote", headers={"Host": host} if host else None)
    return code, headers, bytes(reply).decode("utf-8", "replace") if isinstance(reply, bytes) else str(reply)


class EntryTest(bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(self.clean)
        self.clean()

    def clean(self):
        for path in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE):
            if os.path.lexists(path):
                os.remove(path)

    def new_entry(self):
        """Jeton et page de redirection, comme launch.py --enter : (jeton, chemin de /entrer avec le jeton)."""
        page = launch.make_entry(bench.S.ui_port)
        self.assertEqual(page, launch.ENTRY_PAGE)
        with open(page, encoding="utf-8") as f:
            html = f.read()
        target = urlsplit(re.search(r'http-equiv="refresh" content="0;url=([^"]+)"', html).group(1))
        self.assertEqual((target.scheme, target.netloc, target.path),
                         ("http", f"127.0.0.1:{bench.S.ui_port}", "/entrer"))
        token = parse_qs(target.query)["jeton"][0]
        with open(launch.ENTRY_TOKEN, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), token)
        self.assertGreaterEqual(len(token), 22)                  # 128 bits au moins (base64url)
        return token, f"/entrer?{target.query}"

    def assert_refused(self, reply):
        code, headers, body = reply
        self.assertEqual(code, 200)
        self.assertIsNone(headers["Set-Cookie"])
        self.assertIn('aria-label="Code d\'accès"', body)        # page du code

    def entry_files(self):
        return [os.path.exists(p) for p in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE)]

    def test_good_token_sets_the_access_cookie_and_goes_home(self):
        _, path = self.new_entry()
        code, headers, _ = get(path)
        self.assertEqual((code, headers["Location"]), (303, "/"))
        cookie = headers["Set-Cookie"]
        self.assertTrue(cookie.startswith(f"qwen_access={bench.S.access_token};"), cookie)
        for flag in ("HttpOnly", "SameSite=Lax", "Max-Age=31536000", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertEqual(self.entry_files(), [False, False], "jeton ou page de redirection restés")
        self.assertEqual(call("GET", "/api/status", cookie=False, headers={"Cookie": cookie.split(";")[0]})[0], 200)

    def test_token_works_only_once(self):
        _, path = self.new_entry()
        self.assertEqual(get(path)[0], 303)
        self.assert_refused(get(path))

    def test_token_older_than_a_minute_is_refused_and_removed(self):
        _, path = self.new_entry()
        old = time.time() - 61
        os.utime(launch.ENTRY_TOKEN, (old, old))
        self.assert_refused(get(path))
        self.assertEqual(self.entry_files(), [False, False])

    def test_wrong_token_is_refused_without_removing_the_right_one(self):
        token, path = self.new_entry()
        for wrong in ("/entrer?jeton=" + token[:-1] + ("A" if token[-1] != "A" else "B"), "/entrer", "/entrer?jeton=",
                      "/entrer?jeton=%C3%A9", "/entrer?jeton=%FF", "/entrer?jeton=" + token + "x"):
            with self.subTest(path=wrong):
                self.assert_refused(get(wrong))
                self.assertEqual(self.entry_files(), [True, True], "le bon jeton a été effacé")
        self.assertEqual(get(path)[0], 303)

    def test_entry_from_another_device_is_refused(self):
        _, path = self.new_entry()
        for origin in ("wifi", "remote"):
            with self.subTest(origin=origin):
                self.assert_refused(get(path, origin))
                self.assertEqual(self.entry_files(), [True, True])
        self.assertEqual(get(path)[0], 303)

    def test_token_never_reaches_the_server_log(self):
        token, path = self.new_entry()
        bench.LOG.clear()
        self.assertEqual(get(path, host="ailleurs.example")[0], 403)    # nom d'hôte refusé : requête en erreur
        get(path, "wifi")
        get(path)
        get(path)
        self.assertFalse([line for line in bench.LOG if token in line or "/entrer" in line], bench.LOG)

    @unittest.skipUnless(os.name == "posix", "droits POSIX")
    def test_entry_files_are_readable_by_their_owner_only(self):
        for path in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE):     # restes d'avant, lisibles par tous
            with open(path, "w", encoding="utf-8") as f:
                f.write("ancien\n")
            os.chmod(path, 0o644)
        self.new_entry()
        for path in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE):
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600, path)
        names = tuple(os.path.basename(p) + "." for p in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE))
        leftovers = [n for n in os.listdir(os.path.dirname(launch.ENTRY_TOKEN)) if n.startswith(names)
                     and n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_good_token_still_enters_when_its_files_cannot_be_removed(self):
        # Windows : un fichier tenu ouvert (antivirus, indexation) ne s'efface pas ; le jeton ne sert pas deux fois
        token, path = self.new_entry()
        real_remove = os.remove

        def held_open(p, *a, **kw):
            if p in (launch.ENTRY_TOKEN, launch.ENTRY_PAGE):
                raise PermissionError(13, "fichier ouvert ailleurs", p)
            return real_remove(p, *a, **kw)
        with mock.patch.object(launch.os, "remove", held_open):
            code, headers, _ = get(path)
            self.assertEqual(code, 303)
            self.assertTrue(headers["Set-Cookie"].startswith("qwen_access="))
            self.assert_refused(get(path))             # resté sur le disque, mais déjà servi

    def test_token_replaced_meanwhile_by_another_enter_is_kept(self):
        # un --enter d'un autre processus remplace un jeton périmé juste avant sa lecture : le neuf n'est pas effacé
        self.new_entry()
        old = time.time() - 61
        os.utime(launch.ENTRY_TOKEN, (old, old))
        fresh = "jeton-neuf-de-l-autre-enter"
        real_open, replaced = open, []

        def other_enter_first(file, *a, **kw):
            if file == launch.ENTRY_TOKEN and not replaced:
                replaced.append(file)
                launch.write_owner_only(launch.ENTRY_TOKEN, fresh + "\n")
            return real_open(file, *a, **kw)
        with mock.patch.object(launch, "open", other_enter_first, create=True):
            self.assertEqual(get(f"/entrer?jeton={fresh}")[0], 303)
        self.assertEqual(replaced, [launch.ENTRY_TOKEN])

    def test_refused_entry_of_a_browser_already_connected_goes_home(self):
        # adresse d'entrée rouverte (historique, second onglet d'un double --enter) par un navigateur déjà connecté
        token, path = self.new_entry()
        mine = {"Cookie": f"qwen_access={bench.S.access_token}"}
        for wrong in ("/entrer?jeton=autre", "/entrer"):
            with self.subTest(path=wrong):
                code, reply, headers = bench.call_full("GET", wrong, cookie=False, follow=False, headers=mine)
                self.assertEqual((code, headers["Location"], headers["Set-Cookie"]), (303, "/", None))
                self.assertEqual(self.entry_files(), [True, True], "jeton touché")
        self.assertEqual(get(path)[0], 303)

    def test_enter_option_opens_the_page_never_the_token(self):
        opened, spawned = [], []
        record = lambda *a, **kw: spawned.append(repr((a, kw)))                   # noqa: E731
        argv = ["launch.py", "--enter", "--port", str(bench.S.ui_port)]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(launch, "restrict_new_files"), \
                mock.patch.object(launch, "close_folders"), \
                mock.patch.object(launch.webbrowser, "open", lambda *a, **kw: opened.append(repr((a, kw)))), \
                mock.patch.object(launch.subprocess, "Popen", record), \
                mock.patch.object(launch.subprocess, "run", record), \
                mock.patch.object(launch, "Server", side_effect=AssertionError("--enter a ouvert un serveur")):
            launch.main()
        with open(launch.ENTRY_TOKEN, encoding="utf-8") as f:
            token = f.read().strip()
        self.assertEqual(opened, [repr(((Path(launch.ENTRY_PAGE).as_uri(),), {}))])
        self.assertFalse([x for x in opened + spawned + sys.argv if token in x], "jeton sur une ligne de commande")
        self.assertEqual(get(f"/entrer?jeton={token}")[0], 303)    # la page ouverte mène bien à l'entrée

    def launch_main(self, *options, extra=()):
        """main() d'un lancement normal sur le banc, sans ouvrir de port : rend les adresses données au navigateur.
        Ce que main() changerait au banc partagé est neutralisé, le temps de l'appel seulement : état, code d'accès,
        masque des droits, thread de calcul, reprise d'un changement de code privé, ménage de jobs/ et des images
        (glob ne trouve rien), Time Machine ; le délai d'ouverture du navigateur (threading.Timer) passe tout de
        suite."""
        opened = []

        class FakeServer:
            def __init__(self, address, handler):
                pass

            def serve_forever(self):
                pass

        class NowTimer:
            def __init__(self, delay, action):
                self.action = action

            def start(self):
                self.action()
        argv = ["launch.py", "--port", str(bench.S.ui_port), *options]
        with contextlib.ExitStack() as stack:
            for patch in extra:
                stack.enter_context(patch)
            self.run_main(argv, opened, FakeServer, NowTimer)
        return opened

    @staticmethod
    def run_main(argv, opened, server, timer):
        with mock.patch.object(sys, "argv", argv), mock.patch.object(launch, "Server", server), \
                mock.patch.object(launch.threading, "Timer", timer), \
                mock.patch.object(launch.webbrowser, "open", lambda *a, **kw: opened.append(repr((a, kw)))), \
                mock.patch.object(launch, "restrict_new_files"), mock.patch.object(launch, "close_folders"), \
                mock.patch.object(launch, "setup_state"), mock.patch.object(launch, "setup_access"), \
                mock.patch.object(launch, "exclude_from_backup"), mock.patch.object(launch, "worker", lambda: None), \
                mock.patch.object(launch, "finish_rekey"), mock.patch.object(launch, "restore_hidden_images"), \
                mock.patch.object(launch.glob, "glob", lambda *a, **kw: []), \
                mock.patch.object(bench.S, "started", bench.S.started):
            launch.main()

    def test_launch_opens_the_entry_page_never_the_token(self):
        opened = self.launch_main()
        with open(launch.ENTRY_TOKEN, encoding="utf-8") as f:
            token = f.read().strip()
        self.assertEqual(opened, [repr(((Path(launch.ENTRY_PAGE).as_uri(),), {}))])
        self.assertFalse([x for x in opened if token in x], "jeton passé au navigateur")
        self.assertEqual(get(f"/entrer?jeton={token}")[0], 303)

    def test_launch_falls_back_to_the_plain_address_when_the_entry_cannot_be_written(self):
        bench.LOG.clear()
        unwritable = mock.patch.object(launch, "make_entry", side_effect=PermissionError(13, "lecture seule"))
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            opened = self.launch_main(extra=(unwritable,))
        self.assertEqual(opened, [repr((("http://127.0.0.1:%d/" % bench.S.ui_port,), {}))])
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse([line for line in bench.LOG if "Traceback" in line], bench.LOG)

    def test_launch_without_browser_opens_nothing(self):
        self.assertEqual(self.launch_main("--no-browser"), [])
        self.assertEqual(self.entry_files(), [False, False])


class ShortcutTest(unittest.TestCase):
    def test_mac_shortcut_enters_a_running_interface_by_the_entry_token(self):
        import make_shortcut
        script = make_shortcut.mac_command()
        # interface déjà lancée (le serveur répond) : entrée par le jeton ; l'adresse simple en recours, et le
        # raccourci s'arrête là (sans exec, que « || » ne rattraperait jamais)
        self.assertRegex(script, r"\nif curl [^\n]*/api/status; then\n"
                                 r"\s+venv/bin/python tools/launch.py --enter \|\| open http://127\.0\.0\.1:7860/\n"
                                 r"\s+exit 0\nfi\n")
        if shutil.which("zsh"):
            check = subprocess.run(["zsh", "-n"], input=script, text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == "__main__":
    unittest.main()
