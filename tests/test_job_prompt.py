"""Prompt complet d'une génération suivie (/api/job/<id>), sur le banc (voir bench.py) : une page qui reprend une
génération qu'elle n'a pas lancée (après un rechargement, depuis un autre appareil) n'a dans la file qu'un extrait de 80
caractères ; le suivi lui donne le texte entier, aux seuls appareils qui ont le droit de la suivre."""
import unittest

import bench
from bench import call, wait_job

# plus de 80 caractères ; HOLD : la génération reste en cours jusqu'à bench.release()
LONG = "HOLD zq6 " + "a long and detailed description of a lighthouse at dusk, " * 4
CODE = "Code-prive-1"


class JobPromptTest(bench.BenchCase):
    def test_following_a_normal_generation_gives_its_full_prompt(self):
        job = bench.generate(LONG, steps=10)
        entry = next((e for e in call("GET", "/api/status")[1]["queue"] if e["id"] == job["id"]), None)
        self.assertIsNotNone(entry, "génération déjà sortie de la file")
        self.assertLess(len(entry["prompt"]), len(LONG))           # la file n'en montre que le début
        self.assertEqual(bench.job(job["id"])["prompt"], LONG)
        self.assertEqual(call("GET", f"/api/job/{job['id']}", remote=True)[1]["prompt"], LONG)   # autre appareil
        bench.release()
        self.assertEqual(wait_job(job["id"])["prompt"], LONG)      # aussi une fois terminée

    def test_following_a_private_generation_gives_its_full_prompt_in_the_private_space_only(self):
        session = bench.create_private(CODE)
        code, job = call("POST", "/api/generate", bench.gen_body(LONG, steps=10, private=True), private=session)
        self.assertEqual(code, 202, job)
        self.assertEqual(bench.job(job["id"], private=session)["prompt"], LONG)
        phone = bench.unlock_private(CODE, remote=True)
        self.assertEqual(call("GET", f"/api/job/{job['id']}", remote=True, private=phone)[1]["prompt"], LONG)
        for origin in ({}, {"remote": True}, {"wifi": True, "private": session}):   # hors de l'espace privé
            with self.subTest(origin=origin):
                self.assertEqual(call("GET", f"/api/job/{job['id']}", **origin), (404, {"error": "job inconnu"}))
        bench.release()
        done = wait_job(job["id"], private=session)
        bench.wait_idle()
        self.assertEqual(done["status"], "done")
        self.assertIsNone(bench.job(job["id"], private=session)["prompt"])   # rangée : la demande a quitté la mémoire

    def test_an_incognito_generation_never_gives_its_prompt(self):
        job = bench.generate(LONG, steps=10, incognito=True)
        self.assertIsNone(job["prompt"])
        self.assertIsNone(bench.job(job["id"])["prompt"])
        bench.release()
        self.assertIsNone(wait_job(job["id"])["prompt"])


if __name__ == "__main__":
    unittest.main()
