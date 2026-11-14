"""Vidéo par l'API (ticket 09) : modèle « video » de la table du serveur, refus propres à la vidéo, commande de l'essai,
vidéo en WebP animé dans la pile avec sa durée (frames) gardée, avancement, annulation, aucune mesure de durée. Sur le
banc à faux moteur (voir bench.py), la vidéo installée par bench.video() le temps d'un test."""
import json, os, unittest
from unittest import mock

import bench
from bench import S, call, gen_body, wait_job

launch = bench.launch
CODE = "Mot2passe!"
VIDEO = {"model": "video", "steps": 4, "width": 480, "height": 288, "frames": 56}   # vidéo Petite de 2 s


def post(body, **kw):
    return call("POST", "/api/generate", body, **kw)


def video_body(prompt="a boat at sunrise", **kw):
    return gen_body(prompt, **{**VIDEO, **kw})


def make_video(prompt="a boat at sunrise", **kw):
    code, reply = post(video_body(prompt, **kw))
    assert code == 202, bench.short((code, reply))
    return reply


class VideoCase(bench.BenchCase):
    def setUp(self):
        super().setUp()
        self.enterContext(bench.video())


class VideoStatusTest(bench.BenchCase):
    def test_video_is_listed_only_once_installed(self):
        keys = lambda: [m["key"] for m in call("GET", "/api/status")[1]["models"]]
        self.assertNotIn("video", keys())
        with bench.video():
            models = {m["key"]: m for m in call("GET", "/api/status")[1]["models"]}
            self.assertEqual(list(models), ["qwen", "h3", "video"])
            v = models["video"]
            self.assertEqual((v["name"], v["version"], v["steps"], v["modes"], v["init_image"], v["mask"],
                              v["negative_prompt"], v["max_refs"], v["preview_every"]),
                             ("Vidéo", "h3-video", [4], ["t2i"], True, False, False, 1, None))
            self.assertEqual((v["sizes"], v["frames"], v["lots"]),
                             ([[480, 288], [288, 480], [864, 480], [480, 864]], [56, 73, 124], False))
            with mock.patch.object(S, "engine", "master-959-d637cfb"):      # moteur trop ancien : absente
                self.assertNotIn("video", keys())
        self.assertNotIn("video", keys())


class VideoRefusalTest(VideoCase):
    def refused(self, body, needle):
        before = (len(S.jobs), sorted(os.listdir(launch.P("jobs"))))
        code, reply = post(body)
        self.assertEqual(code, 400, reply)
        self.assertIn(needle, reply["error"])
        self.assertEqual((len(S.jobs), sorted(os.listdir(launch.P("jobs")))), before)   # ni génération ni dossier

    def test_sizes_outside_the_four_are_refused(self):
        for w, h in ((512, 512), (480, 480), (864, 864), (288, 864), (960, 544)):
            self.refused(video_body(width=w, height=h), "taille")

    def test_frames_outside_the_three_or_malformed_are_refused(self):
        for frames in (None, 22, 57, 243, 0, -56, 56.0, "56", True, [56]):
            body = video_body(frames=frames)
            if frames is None:
                del body["frames"]
            self.refused(body, "frames")

    def test_frames_without_video_are_refused(self):
        self.refused(gen_body(frames=56), "frames")
        self.refused(gen_body(frames=56, model="h3", steps=6), "frames")

    def test_what_a_video_cannot_take_is_refused(self):
        img = bench.data_url(bench.png_bytes())
        for extra, needle in (({"steps": 8}, "étapes"),
                              ({"ref_images": [img]}, "images de référence"),
                              ({"mask_image": img, "init_image": img, "mode": "mask"}, "masque"),
                              ({"negative_prompt": "blur"}, "prompt négatif"),
                              ({"count": 2}, "lot"),
                              ({"mode": "edit", "campaign": [{"image": img, "width": 480, "height": 288}]}, "lot")):
            self.refused(video_body(**extra), needle)

    def test_a_lora_tag_in_the_prompt_is_refused(self):
        for prompt in ("a boat <lora:x:1>", "a boat <LORA:other:0.5>", "a boat <lora:x", "<Lora:../x:1> a boat"):
            self.refused(video_body(prompt), "lora")

    def test_a_prompt_with_a_bracket_or_the_word_lora_is_accepted(self):
        for prompt in ("a boat < a car", "a lora bird", "a boat <lora", "lora: a boat"):
            code, reply = post(video_body(f"HOLD=video-lora {prompt}"))
            self.assertEqual(code, 202, (prompt, reply))
            call("POST", f"/api/job/{reply['id']}/cancel")
            wait_job(reply["id"])

    def test_a_start_image_and_each_size_and_duration_are_accepted(self):
        img = bench.data_url(bench.png_bytes())
        bodies = [video_body("HOLD=video-accepte", init_image=img, count=1)]
        bodies += [video_body("HOLD=video-accepte", width=w, height=h, frames=f)
                   for w, h in ((480, 288), (288, 480), (864, 480), (480, 864)) for f in (56, 73, 124)]
        ids = []
        for body in bodies:
            code, reply = post(body)
            self.assertEqual(code, 202, (body["width"], body["height"], body["frames"], reply))
            ids.append(reply["id"])
        for jid in ids:
            call("POST", f"/api/job/{jid}/cancel")
        for jid in ids:
            wait_job(jid)

    def test_video_not_installed_is_refused_with_its_setup_option(self):
        os.rename(launch.VIDEO_FILES["lora"], launch.VIDEO_FILES["lora"] + ".absent")
        try:
            self.refused(video_body(), "--h3-video")
        finally:
            os.rename(launch.VIDEO_FILES["lora"] + ".absent", launch.VIDEO_FILES["lora"])


class VideoGenerationTest(VideoCase):
    def test_the_video_command_is_the_trial_one(self):
        j = wait_job(make_video("a boat at sunrise", seed=42, preview=True, cfg=3.5, preview_interval=1)["id"])
        self.assertEqual(j["status"], "done", j)
        cmd = S.jobs[j["id"]]["cmd"]
        f = launch.VIDEO_FILES
        head = [launch.P("sdcpp", S.backend, launch.EXE), "--diffusion-model", launch.VIDEO_DIFFUSION["h3-video"],
                "--vae", f["vae"], "--llm", f["llm"]] + launch.BACKENDS[S.backend]
        self.assertTrue(cmd.startswith(" ".join(head) + " "), cmd)
        lora = os.path.splitext(os.path.basename(f["lora"]))[0]
        for part in ("-M vid_gen ", "--rng cpu ", "--fps 24 ", "--steps 4 ", "--cfg-scale 1.0 ", "-s 42 ",
                     "-W 480 -H 288 ", "--video-frames 56", f"--lora-model-dir {os.path.dirname(f['lora'])} ",
                     f"-p a boat at sunrise<lora:{lora}:1> "):
            self.assertIn(part, cmd)
        for absent in ("--sampling-method", "--audio-vae", "--preview", "--strength", " -i ", " -r ", " -n "):
            self.assertNotIn(absent, cmd)
        self.assertTrue(S.jobs[j["id"]]["out"].endswith(".webp"), S.jobs[j["id"]]["out"])

    def test_a_qwen_start_image_keeps_its_strength(self):
        img = bench.data_url(bench.png_bytes())
        j = wait_job(bench.generate("a red car", mode="mask", init_image=img, mask_image=img, strength=0.4)["id"])
        self.assertIn(" --strength 0.4", S.jobs[j["id"]]["cmd"])

    def test_a_start_image_goes_through_init(self):
        img = bench.data_url(bench.png_bytes())
        j = wait_job(make_video(init_image=img, strength=0.4)["id"])
        self.assertEqual(j["status"], "done", j)
        cmd = S.jobs[j["id"]]["cmd"]
        self.assertIn(f" -i {os.path.join(S.jobs[j['id']]['dir'], 'init.png')} ", cmd + " ")
        self.assertNotIn("--strength", cmd)
        self.assertEqual(j["inputs"], ["init.png"])

    def test_the_finished_video_waits_in_the_pile_with_its_duration(self):
        j = wait_job(make_video("a harbor at dawn", width=288, height=480, frames=73)["id"])
        self.assertEqual(j["status"], "done", j)
        line = bench.journal()[-1]
        self.assertEqual((line["model"], line["frames"], line["prompt"]), ("h3-video", 73, "a harbor at dawn"))
        self.assertTrue(line["file"].endswith(".webp"), line)
        item = call("GET", "/api/pile")[1][0]
        self.assertEqual((item["name"], item["model"], item["frames"], item["prompt"]),
                         (os.path.basename(line["file"]), "h3-video", 73, "a harbor at dawn"))
        code, raw = call("GET", "/api/result?name=" + item["name"])
        self.assertEqual((code, raw[:4], raw[8:12]), (200, b"RIFF", b"WEBP"))

    def test_an_image_line_has_no_frames(self):
        self.assertEqual(wait_job(bench.generate("a red car")["id"])["status"], "done")
        self.assertNotIn("frames", bench.journal()[-1])
        self.assertIsNone(call("GET", "/api/pile")[1][0]["frames"])


def set_frames(name, value, drop=False):
    """Réécrit dans le journal du banc la ligne de l'image name : frames = value, ou sans frames (drop)."""
    path = launch.P("outputs", "journal.jsonl")
    with launch.JOURNAL_LOCK:
        lines = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
        for x in lines:
            if os.path.basename(x.get("file", "")) == name:
                x.pop("frames", None) if drop else x.update(frames=value)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(x) + "\n" for x in lines)


def pile_item(name):
    return next(it for it in call("GET", "/api/pile")[1] if it["name"] == name)


class VideoKeptDataTest(VideoCase):
    def test_frames_and_model_survive_keep(self):
        j = wait_job(make_video(frames=124)["id"])
        self.assertEqual(call("POST", "/api/keep", {"name": j["name"]}), (200, {"ok": True}))
        item = call("GET", "/api/history")[1][0]
        self.assertEqual((item["name"], item["model"], item["frames"]), (j["name"], "h3-video", 124))
        line = bench.journal()[-1]
        self.assertEqual((line["model"], line["frames"]), ("h3-video", 124))

    def test_a_line_without_or_with_odd_frames_stays_listed_sortable_and_erasable(self):
        for k, (value, drop) in enumerate(((None, True), ("x", False), (7, False), ([56], False), (None, False))):
            with self.subTest(value=value, drop=drop):
                j = wait_job(make_video(f"odd {k}")["id"])
                set_frames(j["name"], value, drop)
                self.assertEqual(pile_item(j["name"])["frames"], value)
                self.assertEqual(call("POST", "/api/keep", {"name": j["name"]}), (200, {"ok": True}))
                self.assertIn(j["name"], [it["name"] for it in call("GET", "/api/history")[1]])
                self.assertEqual(call("POST", "/api/delete", {"name": j["name"]}), (200, {"ok": True}))
                self.assertNotIn(j["name"], [it["name"] for it in call("GET", "/api/history")[1]])
                self.assertFalse([x for x in bench.journal() if os.path.basename(x["file"]) == j["name"]])
                self.assertEqual(bench.files("outputs", "**", f"*{j['id']}*"), [])

    def test_a_video_with_odd_frames_is_discarded_entirely(self):
        j = wait_job(make_video("odd discard")["id"])
        set_frames(j["name"], "x")
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(call("GET", "/api/pile")[1], [])
        self.assertEqual(bench.files("outputs", "**", f"*{j['id']}*"), [])


class PrivateVideoDataTest(bench.PrivateFilesCheck, VideoCase):
    """La fiche d'une vidéo privée garde model et frames ; une fiche sans frames ou hors forme reste lisible (le
    chiffrement, l'absence de clair et le type servi : test_private_video.py)."""

    def setUp(self):
        super().setUp()
        self.session = bench.create_private(CODE)

    def private(self, method, path, body=None):
        return call(method, path, body, private=self.session)

    def test_frames_and_model_survive_keep_in_the_private_space(self):
        code, j = post(video_body(private=True, frames=73), private=self.session)
        self.assertEqual(code, 202, j)
        self.assertEqual(wait_job(j["id"], private=self.session)["status"], "done")
        item = self.private("GET", "/api/private/pile")[1][0]
        self.assertEqual((item["model"], item.get("frames")), ("h3-video", 73))
        self.assertEqual(self.private("POST", "/api/private/keep", {"id": item["id"]}), (200, {"ok": True}))
        kept = self.private("GET", "/api/private/history")[1][0]
        self.assertEqual((kept["id"], kept["model"], kept.get("frames")), (item["id"], "h3-video", 73))

    def test_a_card_without_or_with_odd_frames_stays_listed_sortable_and_erasable(self):
        public = launch.read_space()["public"]
        for k, value in enumerate((None, "x", 7, [56])):
            with self.subTest(value=value):
                meta = {"mode": "t2i", "prompt": f"odd {k}", "width": 480, "height": 288, "steps": 4,
                        "model": "h3-video", "time": 1, "pile": True}
                if value is not None:
                    meta["frames"] = value
                item = launch.store_private(public, meta, bench.png_bytes(fmt="WEBP"), [])
                listed = {x["id"]: x for x in self.private("GET", "/api/private/pile")[1]}
                self.assertEqual(listed[item].get("frames"), value)
                self.assertEqual(self.private("POST", "/api/private/keep", {"id": item}), (200, {"ok": True}))
                self.assertIn(item, [x["id"] for x in self.private("GET", "/api/private/history")[1]])
                self.assertEqual(self.private("POST", "/api/private/delete", {"id": item}), (200, {"ok": True}))
                self.assertNotIn(item, [x["id"] for x in self.private("GET", "/api/private/history")[1]])


class VideoRunTest(VideoCase):
    def test_bars_at_the_start_image_and_decoding_are_not_steps(self):
        # NOISE : barres « k/25 » et « k/4 » à 99 s/it avant l'encodage du prompt (image de départ) et au décodage ;
        # la force reçue n'entre pas dans la commande d'une vidéo, ni donc dans la règle des étapes
        img = bench.data_url(bench.png_bytes())
        j = wait_job(make_video("NOISE a boat", init_image=img, strength=0.4)["id"])
        self.assertEqual(j["status"], "done", j)
        self.assertEqual((j["step"], j["total"]), (4, 4))
        self.assertEqual((j["sec_per_it"], j["sec_per_it_recent"]), (0.01, 0.01))

    def test_a_video_is_cancelled_like_an_image(self):
        jid = make_video("HOLD=video-annule a boat")["id"]
        wait_job(jid, ("running",))
        self.assertEqual(call("POST", f"/api/job/{jid}/cancel")[0], 200)
        bench.release("video-annule")
        self.assertEqual(wait_job(jid)["status"], "cancelled")
        self.assertEqual(call("GET", "/api/pile")[1], [])
        self.assertFalse(os.path.exists(S.jobs[jid]["dir"]))

    def test_the_end_notification_is_the_image_one(self):
        with bench.capture_push() as sent:
            j = wait_job(make_video()["id"])
            sent.wait(1)
        self.assertEqual(j["status"], "done", j)
        self.assertEqual(sent[0]["title"], "Image prête")
        self.assertIn("480×288", sent[0]["body"])

    def test_a_video_records_no_duration_sample(self):
        before = S.store.read()
        self.assertEqual(wait_job(make_video()["id"])["status"], "done")
        self.assertEqual(S.store.read(), before)
        self.assertNotIn(f"{S.backend}/h3-video", S.store.read())


if __name__ == "__main__":
    unittest.main()
