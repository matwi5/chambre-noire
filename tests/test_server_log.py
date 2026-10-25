"""Journal du serveur (logs/ sur le Mac, bench.LOG au banc) : la même ligne neutre pour tout échec, génération privée ou
non, sans détail (le détail, qui peut citer le prompt ou un fichier, reste en mémoire pour l'interface) ; rien n'y
distingue une génération privée d'une normale."""
import errno
import io
import unittest
from unittest import mock

import bench
from bench import call, gen_body, generate, wait_job

CODE = "Mot2passe!"


def logged():
    """Lignes du journal du serveur, sans celles des notifications : un envoi d'un test précédent (thread à part) peut
    arriver après LOG.clear(), et elles sont les mêmes pour toute génération."""
    return [line for line in bench.LOG if not line.startswith("[push]")]


class NeutralFailureLineTest(bench.BenchCase):
    """Journal du serveur (logs/ sur le Mac, bench.LOG au banc) : la même ligne pour un échec normal et un échec privé,
    sans détail (le détail, qui peut citer le prompt ou un fichier, reste en mémoire pour l'interface)."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def failure_lines(self, prompt, **kw):
        """Lignes « [job] … » écrites par une génération qui échoue (privée : kw private=True)."""
        bench.LOG.clear()
        session = self.session if kw.get("private") else None
        code, job = call("POST", "/api/generate", gen_body(prompt, **kw), private=session)
        self.assertEqual(code, 202, job)
        self.assertEqual(wait_job(job["id"], private=session)["status"], "failed")
        self.assertFalse([line for line in bench.LOG if "zq7" in line], "le prompt dans le journal")
        return [line for line in bench.LOG if line.startswith("[job]")]

    def test_an_engine_failure_writes_the_same_neutral_line(self):
        normal = self.failure_lines("FAIL zq7 normale")
        self.assertEqual(len(normal), 1, normal)
        self.assertRegex(normal[0], r"^\[job\] échec : génération, sd-cli code \d+$")
        self.assertEqual(self.failure_lines("FAIL zq7 privee", private=True), normal)

    def test_a_preparation_failure_writes_the_same_neutral_line(self):
        bad = ["data:image/png;base64,bm90IGFuIGltYWdl"]   # « not an image »
        normal = self.failure_lines("zq7 normale", mode="edit", ref_images=bad)
        self.assertEqual(normal, ["[job] échec : génération, erreur de préparation"])
        self.assertEqual(self.failure_lines("zq7 privee", mode="edit", ref_images=bad, private=True), normal)

    def test_an_incomplete_end_gives_no_detail(self):
        bench.LOG.clear()
        with mock.patch.object(bench.launch, "append_journal", side_effect=OSError("disque plein zq7")):
            jid = generate("zq7 normale")["id"]
            self.assertEqual(wait_job(jid)["status"], "done")
        self.assertIn("[job] fin de génération incomplète", bench.LOG)
        self.assertFalse([line for line in bench.LOG if "zq7" in line])

    def test_a_worker_error_gives_no_detail(self):
        bench.LOG.clear()
        with mock.patch.object(bench.launch, "notify_job", side_effect=RuntimeError("panne zq7")):
            self.assertEqual(wait_job(generate("visible")["id"])["status"], "done")
        self.assertIn("[job] erreur du thread de calcul", bench.LOG)
        self.assertFalse([line for line in bench.LOG if "zq7" in line])

    def test_a_lot_notification_error_gives_no_detail(self):
        bench.LOG.clear()
        with mock.patch.object(bench.launch, "notify_lot", side_effect=RuntimeError("panne zq7")):
            code, reply = call("POST", "/api/generate", gen_body("visible", count=2))
            self.assertEqual(code, 202, reply)
            for j in reply["jobs"]:
                wait_job(j["id"])
        self.assertIn("[push] notification du lot impossible", bench.LOG)
        self.assertFalse([line for line in bench.LOG if "zq7" in line])


class QuietSuccessTest(bench.BenchCase):
    """Une réussite écrit la même ligne pour une génération normale et une privée, sans chemin ni durée ni mesure de
    calibration, et seules les requêtes en erreur vont au journal : la suite des requêtes réussies (lectures de l'image
    et de sa miniature après une génération normale seulement) trahirait sinon les générations privées (décision du
    23/10/2026)."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def success_lines(self, prompt, **kw):
        """Lignes écrites par une génération réussie (privée : kw private=True)."""
        bench.LOG.clear()
        session = self.session if kw.get("private") else None
        code, job = call("POST", "/api/generate", gen_body(prompt, **kw), private=session)
        self.assertEqual(code, 202, job)
        self.assertEqual(wait_job(job["id"], private=session)["status"], "done")
        self.assertFalse([line for line in bench.LOG if "zq7" in line], "le prompt dans le journal")
        return logged()

    def test_a_success_writes_the_same_neutral_line(self):
        normal = self.success_lines("zq7 normale")
        self.assertEqual(normal, ["[job] génération terminée"])
        self.assertEqual(self.success_lines("zq7 privee", private=True), normal)

    def test_only_failed_requests_reach_the_log(self):
        name = wait_job(generate("visible")["id"])["name"]
        bench.LOG.clear()
        for path in ("/api/history", "/api/pile", "/api/result?name=" + name, "/api/thumb?name=" + name, "/"):
            self.assertEqual(call("GET", path)[0], 200, path)
        self.assertEqual(logged(), [], "requêtes réussies écrites au journal")
        self.assertEqual(call("GET", "/api/result?name=absente.png")[0], 404)
        self.assertEqual(len(logged()), 1, bench.LOG)
        self.assertIn(" 404 ", logged()[0])


class NoPrivateTraceTest(bench.BenchCase):
    """Rien d'autre dans le journal qui laisse deviner l'espace privé (décision du 23/10/2026) : une connexion coupée
    par l'appareil donne une ligne neutre au lieu de la pile d'appels de Python (qui nommerait une route privée,
    l'adresse de l'appareil et des chemins du Mac) ; /api/generate n'y va jamais, même refusée (ses refus 403 et 503 ne
    viennent que de l'espace privé) ; une suppression n'y écrit rien."""

    def test_a_cut_connection_writes_one_neutral_line(self):
        def cut(handler):
            raise BrokenPipeError(32, "Broken pipe")
        err = io.StringIO()
        bench.LOG.clear()
        with mock.patch.object(bench.launch.H, "do_GET", cut), mock.patch("sys.stderr", err):
            with self.assertRaises(OSError):              # connexion fermée sans réponse
                call("GET", "/api/private/history")
            bench.wait_until(lambda: "[ui] connexion interrompue" in bench.LOG, what="ligne neutre")
        self.assertEqual(logged(), ["[ui] connexion interrompue"])
        self.assertEqual(err.getvalue(), "", "pile d'appels écrite sur la sortie d'erreur")

    def test_a_thumbnail_cut_while_sent_writes_only_the_neutral_line(self):
        name = wait_job(generate("visible")["id"])["name"]
        real = bench.launch.H._send

        def cut_on_success(handler, code, *a, **kw):       # l'appareil a fermé la page pendant l'envoi
            if code == 200 and handler.path.startswith("/api/thumb"):
                raise BrokenPipeError(32, "Broken pipe")
            return real(handler, code, *a, **kw)
        bench.LOG.clear()
        with mock.patch.object(bench.launch.H, "_send", cut_on_success), mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(OSError):
                call("GET", "/api/thumb?name=" + name)
            bench.wait_until(lambda: "[ui] connexion interrompue" in bench.LOG, what="ligne neutre")
        self.assertEqual(logged(), ["[ui] connexion interrompue"], "fausse erreur 500 écrite en plus")

    def test_a_cut_reported_as_a_plain_os_error_is_neutral_too(self):
        def cut(handler):                                   # macOS : EPROTOTYPE au lieu de EPIPE
            raise OSError(errno.EPROTOTYPE, "Protocol wrong type for socket")
        err = io.StringIO()
        bench.LOG.clear()
        with mock.patch.object(bench.launch.H, "do_GET", cut), mock.patch("sys.stderr", err):
            with self.assertRaises(OSError):
                call("GET", "/api/private/history")
            bench.wait_until(lambda: "[ui] connexion interrompue" in bench.LOG, what="ligne neutre")
        self.assertEqual(err.getvalue(), "", "pile d'appels écrite sur la sortie d'erreur")

    def test_a_query_string_hides_no_request(self):
        quiet = bench.launch.quiet_request
        self.assertTrue(quiet('"POST /api/generate HTTP/1.1" 400 -'))
        self.assertTrue(quiet('"GET /api/job/abc/preview?v=2 HTTP/1.1" 404 -'))
        self.assertFalse(quiet('"POST /api/login?/api/generate HTTP/1.1" 403 -'), "chemin pris dans la requête")
        self.assertFalse(quiet('"GET /api/result?name=/api/private/x HTTP/1.1" 404 -'))

    def test_generate_requests_stay_out_of_the_log(self):
        bench.LOG.clear()
        self.assertEqual(call("POST", "/api/generate", gen_body("zq7", width=10))[0], 400)
        self.assertEqual(call("POST", "/api/generate", gen_body("zq7", private=True), private="session-inconnue")[0],
                         403)
        self.assertEqual(logged(), [])

    def test_sorting_and_deletion_write_nothing(self):
        kept, thrown = (wait_job(generate(p)["id"])["name"] for p in ("visible", "jetée"))
        bench.LOG.clear()
        self.assertEqual(call("POST", "/api/keep", {"name": kept})[0], 200)
        self.assertEqual(call("POST", "/api/discard", {"name": thrown})[0], 200)
        self.assertEqual(call("POST", "/api/delete", {"name": kept})[0], 200)
        self.assertEqual(logged(), [])


if __name__ == "__main__":
    unittest.main()
