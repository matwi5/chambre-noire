"""Avancement d'une génération, sur le banc à faux moteur (voir bench.py) : seules les barres d'avancement des étapes
comptent (entre la fin de l'encodage du prompt et la fin de l'échantillonnage, et du total des étapes demandées) ; les
barres que les nouveaux modèles impriment à la lecture d'une image d'entrée et au décodage ne faussent ni l'étape
affichée, ni le temps par étape, ni la mesure de durée gardée pour la calibration. Le faux moteur échoue comme le vrai
quand un fichier de modèle de sa ligne de commande manque, et le banc fixe la release de son moteur."""
import os, unittest

import bench
from bench import S, generate, wait_job, wait_until

W, H = 320, 192                                     # taille propre à ces tests : leur mesure se reconnaît


def last_sample():
    """Dernière mesure de durée gardée pour le moteur et le modèle du banc (tools/calibration.json du banc), ou None."""
    samples = S.store.read().get(f"{S.backend}/{S.model}") or []
    return samples[-1] if samples else None


class ParasiteBarsTest(bench.BenchCase):
    def test_bars_outside_the_sampling_do_not_count_as_steps(self):
        # NOISE : barres « k/25 » et « k/4 » à 99 s/it à la lecture d'une image d'entrée et au décodage
        j = wait_job(generate("NOISE a boat", steps=4, width=W, height=H)["id"])
        self.assertEqual(j["status"], "done", j)
        self.assertEqual((j["step"], j["total"]), (4, 4))
        self.assertEqual((j["sec_per_it"], j["sec_per_it_recent"]), (0.01, 0.01))
        sample = last_sample()
        self.assertIsNotNone(sample)
        self.assertEqual((sample["w"], sample["h"], sample["steps"]), (W, H, 4))
        self.assertLess(sample["step"], 1.0, sample)

    def test_bars_before_the_prompt_is_encoded_are_not_shown_as_steps(self):
        # barres parasites et fin de lecture de l'image d'entrée, puis génération retenue avant l'encodage du prompt
        jid = generate("NOISE HOLD=progres-avant", steps=4)["id"]
        try:
            wait_until(lambda: S.jobs[jid].get("venc_seconds"), what="lecture de l'image d'entrée annoncée")
            j = bench.job(jid)
            self.assertEqual((j["step"], j["total"], j["sec_per_it"]), (None, None, None), j)
            self.assertEqual(j["phase"], "chargement du modèle")
        finally:
            bench.release("progres-avant")
        self.assertEqual(wait_job(jid)["status"], "done")

    def test_qwen_steps_are_shown_as_before(self):
        j = wait_job(generate("a red car", steps=6)["id"])
        self.assertEqual((j["status"], j["step"], j["total"], j["sec_per_it"]), ("done", 6, 6, 0.01))

    def test_a_partial_edit_still_shows_its_steps(self):
        # image d'origine retouchée à moins de 1 : le moteur n'en calcule qu'une part (« 1/1 » pour --strength 0.05
        # sur 25 étapes) ; FEWER=<n> fait imprimer au faux moteur n étapes au lieu de --steps
        j = wait_job(generate("FEWER=2 a red car", steps=6, mode="edit", strength=0.3,
                              init_image=bench.data_url(bench.png_bytes()))["id"])
        self.assertEqual((j["status"], j["step"], j["total"]), ("done", 2, 2), j)


class MissingModelFileTest(bench.BenchCase):
    def test_the_fake_engine_fails_when_a_model_file_is_missing(self):
        path = bench.launch.MODELS["vae"]
        os.rename(path, path + ".absent")
        try:
            j = wait_job(generate("a red car")["id"])
        finally:
            os.rename(path + ".absent", path)
        self.assertEqual(j["status"], "failed", j)
        self.assertIn(os.path.basename(path), j["error"])
        self.assertEqual(wait_job(generate("a red car")["id"])["status"], "done")


class EngineReleaseTest(bench.BenchCase):
    def test_the_bench_engine_release_is_its_install_marker(self):
        self.assertEqual(bench.launch.engine_tag(S.backend), bench.ENGINE)
        self.assertEqual(S.engine, bench.ENGINE)


if __name__ == "__main__":
    unittest.main()
