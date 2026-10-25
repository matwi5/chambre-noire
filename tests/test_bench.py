"""Le banc lui-même : bench.wait_job rend une génération finie une fois que le thread de calcul en a fini avec elle
(fichiers rangés, notification décidée, dossier de travail supprimé pour une annulée), pas au seul statut, posé
avant ; un test qui lit le disque juste après n'a plus à attendre wait_idle() à la main (CI de la PR #11)."""
import threading, unittest
from unittest import mock

import bench
from bench import S, generate, launch, wait_job


class WaitJobTest(bench.BenchCase):
    def test_a_final_status_waits_for_the_worker_to_be_done_with_the_job(self):
        gate, reached = threading.Event(), threading.Event()
        real = launch.notify_job

        def slow_notify(job):                       # le thread de calcul s'arrête après « done », avant de rendre
            reached.set()
            gate.wait(10)
            real(job)
        with mock.patch.object(launch, "notify_job", slow_notify):
            jid = generate("a red car")["id"]
            returned = threading.Event()
            threading.Thread(target=lambda: (wait_job(jid), returned.set()), daemon=True).start()
            self.assertTrue(reached.wait(10))
            self.assertEqual(bench.job(jid)["status"], "done")          # le statut est déjà là…
            self.assertFalse(returned.wait(0.5), "wait_job rendu avant la fin du thread de calcul")   # …pas la fin
            gate.set()
            self.assertTrue(returned.wait(10))
        self.assertNotEqual(S.current, jid)

    def test_a_cancelled_job_is_returned_once_its_work_folder_is_gone(self):
        jid = generate("HOLD=banc-annulee annulée")["id"]
        wait_job(jid, ("running",))
        bench.call("POST", f"/api/job/{jid}/cancel")
        j = wait_job(jid)
        self.assertEqual(j["status"], "cancelled")
        self.assertFalse(bench.os.path.exists(S.jobs[jid]["dir"]), "dossier de travail encore là")

    def test_settle_false_returns_at_the_status(self):
        jid = generate("HOLD=banc-statut en cours")["id"]
        self.assertEqual(wait_job(jid, ("running",))["status"], "running")   # état non final : pas d'attente de fin
        bench.release("banc-statut")
        self.assertEqual(wait_job(jid, settle=False)["status"], "done")


if __name__ == "__main__":
    unittest.main()
