"""Journal du serveur (logs/ sur le Mac, bench.LOG au banc) : la même ligne neutre pour tout échec, génération privée ou
non, sans détail (le détail, qui peut citer le prompt ou un fichier, reste en mémoire pour l'interface) ; rien n'y
distingue une génération privée d'une normale."""
import unittest
from unittest import mock

import bench
from bench import call, gen_body, generate, wait_job

CODE = "Mot2passe!"


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


if __name__ == "__main__":
    unittest.main()
