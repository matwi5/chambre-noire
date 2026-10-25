"""Gestes du poste sur le service macOS, essayés contre le banc et des remplacements (jamais le vrai service) :
tools/service_busy.py dit seulement si une génération tourne (True ou False), avec le cookie calculé du code d'accès,
sans jamais afficher le code ni la réponse ; tools/make_service.py attend la fin du bootout avant le bootstrap, le
réessaie, et n'imprime aucune adresse dans ses erreurs."""
import contextlib, io, os, subprocess, sys, tempfile, unittest
from unittest import mock

import bench
from bench import S, generate, launch, wait_job

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import service_busy  # noqa: E402


class ServiceBusyTest(bench.BenchCase):
    def setUp(self):
        super().setUp()
        with open(launch.ACCESS_FILE, "w", encoding="utf-8") as f:     # le code du Mac (ici celui du banc)
            f.write(bench.ACCESS_CODE)
        self.addCleanup(os.remove, launch.ACCESS_FILE)

    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = service_busy.main(["--port", str(S.ui_port)])
        return code, out.getvalue(), err.getvalue()

    def test_it_prints_only_whether_a_generation_runs(self):
        self.assertEqual(self.run_main(), (0, "False\n", ""))
        jid = generate("HOLD=service-occupe en cours")["id"]
        wait_job(jid, ("running",))
        code, out, err = self.run_main()
        self.assertEqual((code, out, err), (0, "True\n", ""))
        for secret in (bench.ACCESS_CODE, S.access_token):
            self.assertNotIn(secret, out + err)
        bench.release("service-occupe")
        wait_job(jid)

    def test_without_the_code_file_it_says_so_and_creates_nothing(self):
        os.remove(launch.ACCESS_FILE)
        self.addCleanup(lambda: open(launch.ACCESS_FILE, "w").close())    # pour le nettoyage de setUp
        code, out, err = self.run_main()
        self.assertEqual((code, out), (2, ""))
        self.assertIn("code d'accès introuvable", err)
        self.assertFalse(os.path.exists(launch.ACCESS_FILE))

    def test_a_reply_without_busy_is_unreadable_not_a_missing_code(self):
        with mock.patch.object(service_busy.json, "load", return_value={"queue": []}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(service_busy.main(["--port", str(S.ui_port)]), 1)
        self.assertIn("réponse illisible (KeyError)", err.getvalue())

    def test_an_unreachable_service_is_named_without_detail(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = service_busy.main(["--port", "1"])                    # rien n'écoute
        self.assertEqual((code, out.getvalue()), (1, ""))
        self.assertIn("service injoignable", err.getvalue())
        self.assertNotIn(bench.ACCESS_CODE, err.getvalue())


class Done:
    def __init__(self, returncode, stderr=""):
        self.returncode, self.stderr, self.stdout = returncode, stderr, ""


@unittest.skipIf(sys.platform != "darwin", "LaunchAgent : macOS seulement (make_service lit os.getuid à l'import)")
class MakeServiceTest(unittest.TestCase):
    def setUp(self):
        global make_service
        import make_service
        tmp = tempfile.TemporaryDirectory(prefix="qwen-service-test-")
        self.addCleanup(tmp.cleanup)
        self.calls = []
        # tous les chemins du LaunchAgent dans le dossier temporaire : rien sous ~/Library/LaunchAgents
        for name, value in (("ROOT", tmp.name), ("PLIST", os.path.join(tmp.name, "agent.plist")),
                            ("plist_path", lambda label: os.path.join(tmp.name, label + ".plist")),
                            ("BOOT_WAIT", 0.01)):
            p = mock.patch.object(make_service, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(make_service.time, "sleep", lambda s: None)
        p.start()
        self.addCleanup(p.stop)

    def install(self, answers):
        """install() avec launchctl remplacé : answers(args, nombre d'appels pareils) rend son résultat."""
        seen = []

        def launchctl(*args):
            self.calls.append(args[0])
            seen.append(args[:2])
            return answers(args, seen.count(args[:2]))
        with mock.patch.object(make_service, "launchctl", launchctl), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            make_service.install()
        return out.getvalue()

    def test_bootstrap_waits_for_the_bootout_then_retries(self):
        def answers(args, n):
            if args[0] == "print":                      # le service est encore là au premier regard
                return Done(0 if n == 1 and args[1].endswith(make_service.LABEL) else 113)
            if args[0] == "bootstrap":                  # première tentative trop tôt : launchd refuse
                return Done(5 if n == 1 else 0, "Bootstrap failed: 5: Input/output error")
            return Done(0)
        out = self.install(answers)
        self.assertIn("service installé et démarré", out)
        boots = [k for k, c in enumerate(self.calls) if c == "bootout"]
        self.assertEqual(self.calls[boots[-1] + 1:], ["print", "print", "bootstrap", "bootstrap"])

    def test_a_failure_names_no_address(self):
        err = f"Bootstrap failed: 5: Input/output error (192.0.2.10, {bench.WIFI_HOST}, {bench.HTTPS_HOST})"
        with self.assertRaises(SystemExit) as stop:
            self.install(lambda args, n: Done(113) if args[0] == "print" else Done(5 if args[0] == "bootstrap" else 0,
                                                                                    err))
        message = str(stop.exception.code)
        self.assertIn("échec du démarrage du service", message)
        for address in ("192.0.2.10", bench.WIFI_HOST, bench.HTTPS_HOST):
            self.assertNotIn(address, message)
        self.assertGreater(self.calls.count("bootstrap"), 1, "pas de nouvel essai")


if __name__ == "__main__":
    unittest.main()
