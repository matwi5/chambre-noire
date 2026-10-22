"""Incognito retiré : une demande incognito (ancienne page restée ouverte) est refusée sans rien écrire, et ses routes
n'existent plus. Ce qu'il partageait avec l'espace privé (identifiants de 128 bits, ménage après 24 h) est couvert par
tests/test_private_gen.py, la ligne neutre des échecs dans logs/ par tests/test_server_log.py."""
import os, unittest

import bench
from bench import call, gen_body, generate, wait_job

CODE = "Mot2passe!"
REFUSED = "L'incognito n'existe plus : passez par l'espace privé."


def disk():
    """Chaque fichier du dossier du banc avec sa taille et sa date de modification : une écriture dans un fichier déjà
    là (journal, calibration, espace privé) change aussi l'état."""
    return {fp: (os.stat(fp).st_size, os.stat(fp).st_mtime_ns) for fp in bench.all_files()}


class IncognitoRefusedTest(bench.BenchCase):
    def test_an_incognito_request_is_refused_and_writes_nothing(self):
        session = bench.create_private(CODE)
        before = disk()
        bench.LOG.clear()
        for body, private in ((gen_body("zq7 secret", incognito=True), None),
                              (gen_body("zq7 secret lot", count=2, incognito=True), None),
                              (gen_body("zq7 secret", mode="edit", ref_images=[bench.data_url(bench.png_bytes())],
                                        incognito=True), None),
                              (gen_body("zq7 secret", incognito=True, private=True), session)):
            with self.subTest(body={k: body[k] for k in body if k in ("count", "mode", "private")}):
                self.assertEqual(call("POST", "/api/generate", body, private=private), (400, {"error": REFUSED}))
        bench.wait_idle()
        self.assertEqual(disk(), before)
        self.assertEqual(bench.S.jobs, {})
        self.assertFalse([line for line in bench.LOG if "zq7" in line])

    def test_incognito_false_and_the_old_page_token_are_ignored(self):
        job = generate("visible", incognito=False, page=12)
        self.assertRegex(job["id"], r"^\d{8}_\d{6}_[0-9a-f]{6}$")
        self.assertEqual([k for k in ("incognito", "tag") if k in job], [])
        self.assertEqual(wait_job(job["id"])["status"], "done")
        self.assertEqual(len(bench.files("outputs", "*.png")), 1)

    def test_the_incognito_routes_are_gone(self):
        jid = generate("visible")["id"]
        self.assertEqual(wait_job(jid)["status"], "done")
        self.assertEqual(call("GET", f"/api/job/{jid}/result"), (404, {"error": "not found"}))
        self.assertEqual(call("POST", "/api/forget", {"ids": [jid]}), (404, {"error": "not found"}))
        self.assertEqual(wait_job(jid)["status"], "done")

    def test_the_running_normal_generation_is_the_current_job(self):
        jid = generate("HOLD visible")["id"]
        wait_job(jid, ("running",))
        self.assertEqual(call("GET", "/api/status")[1]["current_job"], jid)
        bench.release()
        wait_job(jid)


if __name__ == "__main__":
    unittest.main()
