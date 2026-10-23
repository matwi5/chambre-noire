"""Journal du serveur (logs/ sur le Mac, bench.LOG au banc) : la même ligne neutre pour tout échec, génération privée ou
non, sans détail (le détail, qui peut citer le prompt ou un fichier, reste en mémoire pour l'interface) ; rien n'y
distingue une génération privée d'une normale."""
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
        bench.wait_idle()
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
            bench.wait_idle()
        self.assertIn("[job] fin de génération incomplète", bench.LOG)
        self.assertFalse([line for line in bench.LOG if "zq7" in line])

    def test_a_worker_error_gives_no_detail(self):
        bench.LOG.clear()
        with mock.patch.object(bench.launch, "notify_job", side_effect=RuntimeError("panne zq7")):
            self.assertEqual(wait_job(generate("visible")["id"])["status"], "done")
            bench.wait_idle()
        self.assertIn("[job] erreur du thread de calcul", bench.LOG)
        self.assertFalse([line for line in bench.LOG if "zq7" in line])

    def test_a_lot_notification_error_gives_no_detail(self):
        bench.LOG.clear()
        with mock.patch.object(bench.launch, "notify_lot", side_effect=RuntimeError("panne zq7")):
            code, reply = call("POST", "/api/generate", gen_body("visible", count=2))
            self.assertEqual(code, 202, reply)
            for j in reply["jobs"]:
                wait_job(j["id"])
            bench.wait_idle()
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
        bench.wait_idle()
        self.assertFalse([line for line in bench.LOG if "zq7" in line], "le prompt dans le journal")
        return logged()

    def test_a_success_writes_the_same_neutral_line(self):
        normal = self.success_lines("zq7 normale")
        self.assertEqual(normal, ["[job] génération terminée"])
        self.assertEqual(self.success_lines("zq7 privee", private=True), normal)

    def test_only_failed_requests_reach_the_log(self):
        name = wait_job(generate("visible")["id"])["name"]
        bench.wait_idle()
        bench.LOG.clear()
        for path in ("/api/history", "/api/result?name=" + name, "/api/thumb?name=" + name, "/"):
            self.assertEqual(call("GET", path)[0], 200, path)
        self.assertEqual(logged(), [], "requêtes réussies écrites au journal")
        self.assertEqual(call("GET", "/api/result?name=absente.png")[0], 404)
        self.assertEqual(len(logged()), 1, bench.LOG)
        self.assertIn(" 404 ", logged()[0])


if __name__ == "__main__":
    unittest.main()
