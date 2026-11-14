"""Modèle d'une demande (champ model) : table fermée du serveur, refus avant la file, commande de MiniMax H3, modèle
gardé par la génération (commande, journal, fiche privée), mesure de durée de MiniMax H3 sous sa propre clé (ticket
06, détails dans test_estimates.py), modèles installés dans /api/status. Sur le banc à faux moteur (voir bench.py), avec
de faux fichiers de modèle."""
import contextlib, os, unittest
from unittest import mock

import bench
from bench import S, call, gen_body, generate, wait_job

launch = bench.launch
CODE = "Mot2passe!"
H3 = {"model": "h3", "steps": 6}                 # demande MiniMax H3 minimale valide


def post(body, **kw):
    return call("POST", "/api/generate", body, **kw)


def samples():
    """Toutes les mesures de durée gardées (tools/calibration.json du banc), par clé : les mesures elles-mêmes, pas leur
    nombre (40 au plus par clé : une mesure de plus en chasse une)."""
    return S.store.read()


@contextlib.contextmanager
def without(path):
    """Le fichier path absent le temps du bloc (remis ensuite, même en cas d'échec)."""
    os.rename(path, path + ".absent")
    try:
        yield
    finally:
        os.rename(path + ".absent", path)


class QwenCommandTest(bench.BenchCase):
    def test_a_qwen_command_is_unchanged(self):
        j = wait_job(generate("a red car", seed=7)["id"])
        m = launch.MODELS
        expected = ([launch.P("sdcpp", S.backend, launch.EXE), "--diffusion-model", m["diffusion"], "--vae", m["vae"],
                     "--llm", m["llm"]] + (["--llm_vision", m["llm_vision"]] if "llm_vision" in m else [])
                    + launch.BACKENDS[S.backend] + ["-p", "a red car", "-W", "512", "-H", "512", "--steps", "4",
                                                    "--cfg-scale", "1", "--sampling-method", "euler", "-s", "7", "-o"])
        self.assertTrue(S.jobs[j["id"]]["cmd"].startswith(" ".join(expected) + " "), S.jobs[j["id"]]["cmd"])
        self.assertNotIn("--sigmas", S.jobs[j["id"]]["cmd"])
        self.assertEqual(bench.journal()[-1]["model"], S.model)


class ModelFieldTest(bench.BenchCase):
    def refused(self, body, needle):
        before = (len(S.jobs), sorted(os.listdir(launch.P("jobs"))))
        code, reply = post(body)
        self.assertEqual(code, 400, reply)
        self.assertIn(needle, reply["error"])
        self.assertEqual((len(S.jobs), sorted(os.listdir(launch.P("jobs")))), before)   # ni génération ni dossier
        return reply["error"]

    def test_without_model_or_with_qwen_it_is_qwen(self):
        for extra in ({}, {"model": "qwen"}):
            j = wait_job(generate(**extra)["id"])
            self.assertEqual(j["status"], "done")
            self.assertEqual(bench.journal()[-1]["model"], S.model)

    def test_a_model_that_is_not_a_text_is_refused(self):
        for value in (None, True, 1, 1.5, [], ["h3"], {}, {"h3": 1}):
            self.refused(gen_body(**{**H3, "model": value}), "model : texte attendu")

    def test_an_unknown_model_is_refused_without_echoing_it(self):
        for value in ("H3", "h3 ", " h3", "../x", "zq9inconnu", "", "q4", "h3-q4"):
            error = self.refused(gen_body(**{**H3, "model": value}), "modèle inconnu")
            if value.strip():
                self.assertNotIn(value.strip(), error)

    def test_h3_without_a_file_is_refused_with_its_setup_option(self):
        for path in (launch.H3_DIFFUSION["h3-q4"], launch.H3_FILES["vae"], launch.H3_FILES["llm"]):
            others = [p for p in launch.H3_DIFFUSION.values() if p != path] if path in launch.H3_DIFFUSION.values() \
                else []
            with without(path), contextlib.ExitStack() as stack:
                for p in others:                    # sans aucune version du modèle
                    stack.enter_context(without(p))
                self.refused(gen_body(**H3), "setup.py --h3")

    def test_h3_on_an_older_engine_is_refused_with_its_setup_option(self):
        for engine in ("master-959-d637cfb", "illisible"):
            with mock.patch.object(S, "engine", engine):
                error = self.refused(gen_body(**H3), "setup.py --h3")
            self.assertIn("relancez le serveur", error)     # le moteur est lu au lancement

    def test_h3_installed_is_accepted(self):
        j = wait_job(generate(**H3)["id"])
        self.assertEqual(j["status"], "done", j)

    def test_h3_refuses_what_it_cannot_do(self):
        img = bench.data_url(bench.png_bytes())
        for extra, needle in (({"steps": 4}, "étapes"), ({"steps": 40}, "étapes"),
                              ({"init_image": img}, "image de départ"), ({"mask_image": img}, "masque"),
                              ({"mode": "annot", "ref_images": [img]}, "annotation"),
                              ({"mode": "mask"}, "mode masque"), ({"mode": "mask_"}, "mode masque"),
                              ({"mode": "an-not", "ref_images": [img]}, "mode annotation"),
                              ({"negative_prompt": "blur"}, "prompt négatif")):
            self.refused(gen_body(**{**H3, **extra}), needle)

    def test_h3_accepts_qwen_sizes_and_ten_references(self):
        img = bench.data_url(bench.png_bytes())
        code, reply = post(gen_body("HOLD=choix-tailles", **{**H3, "width": 4096, "height": 2048, "mode": "edit",
                                                              "ref_images": [img] * 10, "negative_prompt": ""}))
        self.assertEqual(code, 202, reply)
        call("POST", f"/api/job/{reply['id']}/cancel")
        wait_job(reply["id"])


class H3GenerationTest(bench.BenchCase):
    def test_the_h3_command_is_the_trial_one(self):
        img = bench.data_url(bench.png_bytes())
        j = wait_job(generate("a boat", **{**H3, "mode": "edit", "ref_images": [img], "preview": True, "cfg": 3.5,
                                          "preview_interval": 5, "seed": 9})["id"])
        self.assertEqual(j["status"], "done", j)
        cmd = S.jobs[j["id"]]["cmd"]
        d = launch.H3_FILES
        head = [launch.P("sdcpp", S.backend, launch.EXE), "--diffusion-model", launch.H3_DIFFUSION["h3-q4"],
                "--vae", d["vae"], "--llm", d["llm"]] + launch.BACKENDS[S.backend]
        self.assertTrue(cmd.startswith(" ".join(head) + " "), cmd)
        for part in ("--steps 6 ", "--cfg-scale 1.0 ", "--sampling-method euler ", "--sigmas minimax-h3-image ",
                     "--rng cpu ", "-s 9 ", " -r ", "--preview-interval 2"):
            self.assertIn(part, cmd)
        self.assertNotIn("--llm_vision", cmd)
        self.assertNotIn(" h3 ", cmd + " ")
        self.assertEqual(bench.journal()[-1]["model"], "h3-q4")

    def test_without_q4_the_q8_version_is_used(self):
        with without(launch.H3_DIFFUSION["h3-q4"]):
            j = wait_job(generate(**H3)["id"])
        self.assertEqual(j["status"], "done", j)
        self.assertIn(launch.H3_DIFFUSION["h3-q8"], S.jobs[j["id"]]["cmd"])
        self.assertEqual(bench.journal()[-1]["model"], "h3-q8")

    def test_h3_records_its_sample_under_its_own_key_only(self):
        before = samples()
        self.assertEqual(wait_job(generate(**H3)["id"])["status"], "done")
        key = f"{S.backend}/h3-q4"
        self.assertEqual(len(samples()[key]), min(len(before.get(key, [])) + 1, 40))
        others = lambda d: {k: v for k, v in d.items() if k != key}
        self.assertEqual(others(samples()), others(before))
        # Qwen mesure toujours, sous sa clé (taille propre à ce test)
        self.assertEqual(wait_job(generate("a red car", width=352, height=224)["id"])["status"], "done")
        last = samples()[f"{S.backend}/{S.model}"][-1]
        self.assertEqual((last["w"], last["h"]), (352, 224))

    def test_a_mixed_queue_runs_in_order_each_image_with_its_model(self):
        ids = [generate("HOLD=choix-file a")["id"], generate("b", **H3)["id"], generate("c")["id"],
               generate("d", **H3)["id"]]
        bench.release("choix-file")
        for jid in ids:
            self.assertEqual(wait_job(jid)["status"], "done")
        lines = bench.journal()[-4:]
        self.assertEqual([x["prompt"].split()[-1] for x in lines], ["a", "b", "c", "d"])
        self.assertEqual([x["model"] for x in lines], [S.model, "h3-q4", S.model, "h3-q4"])

    def test_the_model_is_chosen_when_the_generation_is_created(self):
        first = generate("HOLD=choix-creation")["id"]
        jid = generate("b", **H3)["id"]                  # en file derrière la première
        q4 = launch.H3_DIFFUSION["h3-q4"]
        with without(q4):              # retiré pendant l'attente : la commande garde la version choisie, sans repli
            bench.release("choix-creation")
            wait_job(first)
            j = wait_job(jid)
        self.assertEqual(j["status"], "failed", j)    # le moteur ne trouve plus le fichier : pas de bascule sur h3-q8
        self.assertIn(q4, S.jobs[jid]["cmd"])
        self.assertNotIn(launch.H3_DIFFUSION["h3-q8"], S.jobs[jid]["cmd"])


class StatusModelsTest(bench.BenchCase):
    def test_status_lists_the_installed_models_with_their_limits(self):
        s = call("GET", "/api/status")[1]
        self.assertEqual((s["model_version"], s["sd_ready"]), (S.model, True))   # champs d'avant inchangés
        models = {m["key"]: m for m in s["models"]}
        self.assertEqual(list(models), ["qwen", "h3"])
        self.assertEqual(models["h3"], {"key": "h3", "name": "MiniMax H3", "version": "h3-q4", "steps": [6],
                                        "modes": ["t2i", "edit"], "init_image": False, "mask": False,
                                        "negative_prompt": False, "max_refs": launch.MAX_CAMPAIGN,
                                        "max_side": 4096, "preview_every": 2})
        self.assertEqual((models["qwen"]["version"], models["qwen"]["steps"]), (S.model, None))

    def test_h3_on_an_older_engine_or_without_files_is_not_listed(self):
        with mock.patch.object(S, "engine", "master-959-d637cfb"):
            self.assertEqual([m["key"] for m in call("GET", "/api/status")[1]["models"]], ["qwen"])
        with without(launch.H3_FILES["llm"]):
            self.assertEqual([m["key"] for m in call("GET", "/api/status")[1]["models"]], ["qwen"])


class ConfigVersionTest(bench.BenchCase):
    """Version de MiniMax H3 propre à la machine : "h3": "q8" dans tools/config.local.json (lu au lancement, S.cfg)."""

    def version(self, value=None):
        """Version de MiniMax H3 dans /api/status quand la configuration porte "h3": value (None : sans clé h3)."""
        cfg = {k: v for k, v in S.cfg.items() if k != "h3"}
        if value is not None:
            cfg["h3"] = value
        with mock.patch.object(S, "cfg", cfg):
            models = {m["key"]: m for m in call("GET", "/api/status")[1]["models"]}
        return models["h3"]["version"]

    def test_q8_in_the_config_chooses_the_q8_version(self):
        self.assertEqual(self.version("q8"), "h3-q8")
        with mock.patch.object(S, "cfg", {**S.cfg, "h3": "q8"}):
            j = wait_job(generate(**H3)["id"])
        self.assertEqual(j["status"], "done", j)
        self.assertIn(launch.H3_DIFFUSION["h3-q8"], S.jobs[j["id"]]["cmd"])
        self.assertNotIn(launch.H3_DIFFUSION["h3-q4"], S.jobs[j["id"]]["cmd"])
        self.assertEqual(bench.journal()[-1]["model"], "h3-q8")

    def test_without_a_value_it_is_q4(self):
        self.assertEqual(self.version(None), "h3-q4")
        self.assertEqual(self.version("q4"), "h3-q4")

    def test_an_unknown_value_falls_back_to_a_present_version(self):
        for value in ("q9", "h3-q8", "Q8", "", "../x", 8, ["q8"], {"q8": True}, True):
            self.assertEqual(self.version(value), "h3-q4", value)

    def test_an_unknown_value_never_reaches_the_command(self):
        with mock.patch.object(S, "cfg", {**S.cfg, "h3": "../zq9-chemin"}):
            j = wait_job(generate(**H3)["id"])
        self.assertEqual(j["status"], "done", j)
        self.assertIn(launch.H3_DIFFUSION["h3-q4"], S.jobs[j["id"]]["cmd"])
        self.assertNotIn("zq9-chemin", S.jobs[j["id"]]["cmd"])

    def test_an_absent_version_falls_back_to_the_present_one(self):
        with without(launch.H3_DIFFUSION["h3-q8"]):
            self.assertEqual(self.version("q8"), "h3-q4")
        with without(launch.H3_DIFFUSION["h3-q4"]):
            self.assertEqual(self.version("q4"), "h3-q8")
            self.assertEqual(self.version("q9"), "h3-q8")


class PrivateH3Test(bench.PrivateFilesCheck, bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def generate(self, prompt, **kw):
        code, job = post(gen_body(prompt, private=True, **kw), private=self.session)
        self.assertEqual(code, 202, job)
        return wait_job(job["id"], private=self.session)

    def test_a_private_h3_generation_keeps_its_model_inside_and_adds_no_sample(self):
        before, log = samples(), len(bench.LOG)
        self.assertEqual(self.generate("zq9h3 secret", **H3)["status"], "done")
        h3_lines = bench.LOG[log:]
        log = len(bench.LOG)
        self.assertEqual(self.generate("zq9qwen secret")["status"], "done")
        self.assertEqual(bench.LOG[log:], h3_lines)                    # mêmes lignes de journal du serveur
        self.assertEqual(samples(), before)                             # aucune mesure d'une génération privée
        code, items = call("GET", "/api/private/pile", private=self.session)
        self.assertEqual(code, 200, items)
        self.assertEqual(sorted(x["model"] for x in items), sorted([S.model, "h3-q4"]))
        self.assertEqual(bench.journal(), [])
        for fp in bench.all_files():                                    # le modèle n'est en clair nulle part
            if "calibration" not in fp:
                self.assertNotIn(b"h3-q4", open(fp, "rb").read(), fp)


if __name__ == "__main__":
    unittest.main()
