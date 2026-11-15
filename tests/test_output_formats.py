"""Sorties PNG ou WebP animé (vidéo), sur le banc à faux moteur (voir bench.py) : une sortie se reconnaît par son
extension réelle (`.png` ou `.webp`, casse quelconque) dans la pile, les tirages, le tri, les vignettes et les routes
qui servent une image ; rien ne produit encore de WebP côté serveur, le banc en pose un avec sa ligne du journal."""
import os, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

import bench

FAKE = os.path.join(bench.HERE, "fake_sdcli.py")


def fake_engine(*args, prompt="a red car"):
    """Lance le faux moteur comme le ferait le serveur ; (code de sortie, sortie)."""
    run = subprocess.run([sys.executable, FAKE, "-p", prompt, *args], capture_output=True, text=True, timeout=60)
    return run.returncode, run.stdout


def video_in_pile(prompt="a boat at dawn", jid="20260101_120000_abcdef", mode="t2i", ref=True):
    """Pose dans la pile du banc un WebP animé au nom que le serveur écrit (<identifiant>_<mode>.webp), avec sa ligne
    du journal et son image d'entrée, par le même chemin qu'une génération finie (to_pile) : dossier de travail,
    sortie du faux moteur, puis arrivée dans la pile. Renvoie {"id", "name"}."""
    d = bench.launch.P("jobs", jid)
    os.makedirs(d)
    if ref:
        with open(os.path.join(d, "ref_1.png"), "wb") as f:
            f.write(bench.png_bytes())
    out = os.path.join(d, f"{jid}_{mode}.webp")
    code, log = fake_engine("-W", "64", "-H", "48", "--steps", "2", "-o", out)
    assert code == 0, log
    job = {"id": jid, "dir": d, "out": out, "status": "running"}
    meta = {"mode": mode, "prompt": prompt, "width": 64, "height": 48, "steps": 4, "seed": 1, "model": "h3-video"}
    assert bench.launch.to_pile(job, meta)
    return {"id": jid, "name": os.path.basename(out)}


def pile_items():
    code, items = bench.call("GET", "/api/pile")
    assert code == 200, bench.short((code, items))
    return items


def history_names():
    return [it["name"] for it in bench.call("GET", "/api/history")[1]]


class WebpInThePileTest(bench.BenchCase):
    def test_a_webp_in_the_pile_is_listed_and_served(self):
        v = video_in_pile()
        items = pile_items()
        self.assertEqual([it["name"] for it in items], [v["name"]])
        self.assertEqual((items[0]["prompt"], items[0]["model"], items[0]["inputs"]),
                         ("a boat at dawn", "h3-video", ["ref_1.png"]))
        code, raw, headers = bench.call_full("GET", "/api/result?name=" + v["name"])
        self.assertEqual((code, raw[:4], raw[8:12], headers["Content-Type"]), (200, b"RIFF", b"WEBP", "image/webp"))
        code, raw, headers = bench.call_full("GET", f"/api/result?name={v['name']}&download=1")
        self.assertIn(f'filename="{v["name"]}"', headers["Content-Disposition"])
        code, raw = bench.call("GET", f"/api/input?name={v['name']}&file=ref_1.png")
        self.assertEqual((code, raw[:8]), (200, b"\x89PNG\r\n\x1a\n"))

    def test_the_thumbnail_of_a_webp_is_its_first_frame(self):
        from PIL import Image
        import io
        v = video_in_pile()
        code, raw = bench.call("GET", "/api/thumb?name=" + v["name"])
        self.assertEqual((code, raw[:2]), (200, b"\xff\xd8"))
        with Image.open(io.BytesIO(raw)) as im:
            r, g, b = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
        # première image du faux moteur : (220, 40, 40), rouge ; la dernière tire vers le bleu
        self.assertTrue(r > 180 and b < 80, (r, g, b))


def put(folder, name, raw=None):
    """Fichier name dans folder (chemin relatif à la racine du banc), PNG valide par défaut."""
    with open(bench.launch.P(*folder.split("/"), name), "wb") as f:
        f.write(bench.png_bytes() if raw is None else raw)


class NameTableTest(bench.BenchCase):
    """Table des noms reçus (spec, « Fichier de sortie : image ou vidéo ») : par /api/result et /api/keep."""

    def setUp(self):
        super().setUp()
        os.makedirs(bench.launch.P("outputs", ".pile"), exist_ok=True)

    def assertServed(self, name, served):
        code = bench.call("GET", f"/api/result?name={name}")[0] if name is not None else \
            bench.call("GET", "/api/result")[0]
        self.assertEqual(code, 200 if served else 404, name)

    def test_empty_or_absent_is_rejected(self):
        for name in ("", None):
            with self.subTest(name=name):
                self.assertServed(name, False)
                self.assertEqual(bench.call("POST", "/api/keep", {"name": name})[0], 404)

    def test_a_hidden_name_is_rejected(self):
        put("outputs/.pile", ".20260101_120000_abcdef_t2i.webp")
        put("outputs/.pile", ".20260101_120000_abcdef_t2i.png")
        for name in (".20260101_120000_abcdef_t2i.webp", ".20260101_120000_abcdef_t2i.png"):
            with self.subTest(name=name):
                self.assertServed(name, False)
                self.assertEqual(bench.call("POST", "/api/keep", {"name": name})[0], 404)

    def test_png_and_webp_in_any_case_are_accepted_when_present(self):
        names = ["a_t2i.png", "b_t2i.webp", "c_t2i.PNG", "d_t2i.WebP"]
        for name in names:
            put("outputs", name)
        self.assertEqual(sorted(history_names()), sorted(names))
        for name in names:
            with self.subTest(name=name):
                self.assertServed(name, True)
        self.assertServed("absente_t2i.webp", False)

    def test_another_extension_is_rejected(self):
        for name in ("e_t2i.jpg", "f_t2i.webm", "g_t2i.png.txt", "h_t2i"):
            put("outputs", name)
            with self.subTest(name=name):
                self.assertServed(name, False)
                self.assertEqual(bench.call("POST", "/api/delete", {"name": name})[0], 404)
                self.assertTrue(os.path.exists(bench.launch.P("outputs", name)))
        self.assertEqual(history_names(), [])

    def test_only_the_file_name_counts_in_a_path(self):
        v = video_in_pile()
        for name in (f"../../outputs/.pile/{v['name']}", f"autre/{v['name']}"):
            with self.subTest(name=name):
                self.assertServed(name, True)
        self.assertServed(f"../{v['name'][:-5]}.png", False)

    def test_an_unreadable_pile_lists_nothing_and_the_server_still_answers(self):
        put("outputs", "a_t2i.png")
        pile = bench.launch.P("outputs", ".pile")
        os.rmdir(pile)
        with open(pile, "wb") as f:                     # la pile n'est plus un dossier : os.listdir lève
            f.write(b"pas un dossier")
        try:
            self.assertEqual(bench.call("GET", "/api/pile"), (200, []))
            self.assertEqual(history_names(), ["a_t2i.png"])
            self.assertServed("a_t2i.png", True)
            bench.launch.restore_hidden_images()
        finally:
            os.remove(pile)

    def test_a_name_whose_case_differs_from_the_disk_is_unknown(self):
        # sur un disque insensible à la casse, « …_T2I.WEBP » ouvrirait « …_t2i.webp » : son effacement laisserait la
        # ligne du journal, qui porte le nom exact
        v = video_in_pile()
        other = v["name"].upper()
        self.assertServed(other, False)
        self.assertEqual(bench.call("POST", "/api/discard", {"name": other})[0], 404)
        self.assertEqual([it["name"] for it in pile_items()], [v["name"]])
        self.assertEqual([line["file"].rsplit(os.sep, 1)[-1] for line in bench.journal()], [v["name"]])

    def test_a_webp_next_to_a_png_of_the_same_stem_is_another_image(self):
        v = video_in_pile()
        twin = v["name"][:-5] + ".png"
        put("outputs/.pile", twin)
        self.assertEqual(sorted(it["name"] for it in pile_items()), sorted([v["name"], twin]))
        self.assertEqual(bench.call("POST", "/api/discard", {"name": twin}), (200, {"ok": True}))
        # l'autre image du même radical garde ses vignettes, ses entrées, son dossier de travail et sa ligne
        self.assertEqual([it["name"] for it in pile_items()], [v["name"]])
        self.assertEqual(pile_items()[0]["inputs"], ["ref_1.png"])
        self.assertTrue(os.path.isdir(bench.launch.P("jobs", v["id"])))
        self.assertEqual(bench.call("GET", "/api/thumb?name=" + v["name"])[0], 200)
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(v), NOTHING)

    def test_twins_have_their_own_thumbnails(self):
        from PIL import Image
        import io
        v = video_in_pile()                                               # première image rouge
        twin = v["name"][:-5] + ".png"
        self.assertEqual(bench.call("GET", "/api/thumb?name=" + v["name"])[0], 200)
        buf = io.BytesIO()
        Image.new("RGB", (64, 48), (30, 30, 220)).save(buf, "PNG")       # PNG bleu, plus récent que la vidéo
        put("outputs/.pile", twin, buf.getvalue())

        def color(name):
            code, raw = bench.call("GET", "/api/thumb?name=" + name)
            self.assertEqual(code, 200, name)
            with Image.open(io.BytesIO(raw)) as im:
                r, g, b = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
            return "rouge" if r > b else "bleu"
        self.assertEqual([color(twin), color(v["name"]), color(twin)], ["bleu", "rouge", "bleu"])

    def test_an_erased_twin_takes_its_own_thumbnail_and_leaves_the_shared_pieces(self):
        v = with_thumbs(self, video_in_pile())          # vignette faite depuis la vidéo
        twin = v["name"][:-5] + ".png"
        put("outputs/.pile", twin)
        stem = v["name"][:-5]
        self.assertEqual(bench.call("GET", "/api/thumb?name=" + twin)[0], 200)
        self.assertEqual(len(bench.files("outputs", ".thumbs", stem + "*.jpg")), 3)    # vidéo, PNG, entrée
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(bench.files("outputs", ".thumbs", v["name"] + ".jpg"), [])   # vignette de la vidéo effacée
        self.assertNotEqual(bench.files("outputs", ".thumbs", stem + ".jpg"), [])     # celle du PNG reste
        self.assertNotEqual(bench.files("outputs", ".thumbs", stem + "__*.jpg"), [])
        self.assertEqual(bench.files("outputs", ".inputs", stem, "*"), [bench.launch.P("outputs", ".inputs", stem,
                                                                                         "ref_1.png")])
        self.assertTrue(os.path.isdir(bench.launch.P("jobs", v["id"])))
        self.assertEqual([it["name"] for it in pile_items()], [twin])
        code, raw = bench.call("GET", "/api/thumb?name=" + twin)       # refaite depuis le PNG restant
        self.assertEqual(code, 200)

    def test_a_twin_left_hidden_by_a_cut_erase_keeps_the_shared_pieces(self):
        v = video_in_pile()
        stem = v["name"][:-5]
        put("outputs/.pile", "." + stem + ".png")       # effacement coupé : le PNG reviendra au démarrage
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertTrue(os.path.isdir(bench.launch.P("outputs", ".inputs", stem)))
        self.assertTrue(os.path.isdir(bench.launch.P("jobs", v["id"])))
        bench.launch.restore_hidden_images()
        self.assertEqual([(it["name"], it["inputs"]) for it in pile_items()], [(stem + ".png", ["ref_1.png"])])

    def test_a_twin_whose_stem_differs_only_by_case_shares_what_the_disk_shares(self):
        # un disque insensible à la casse (macOS par défaut) range « X » et « x » sous les mêmes entrées : elles
        # restent avec l'autre image ; un disque sensible les sépare : la vidéo jetée part en entier
        v = video_in_pile()
        stem = v["name"][:-5]
        put("outputs", stem.upper() + ".png")
        insensitive = os.path.isdir(bench.launch.P("outputs", ".inputs", stem.upper()))
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(os.path.isdir(bench.launch.P("outputs", ".inputs", stem)), insensitive)
        self.assertFalse(os.path.isdir(bench.launch.P("jobs", v["id"])))   # l'identifiant en majuscules n'en a pas
        self.assertEqual(history_names(), [stem.upper() + ".png"])


def pieces(v):
    """Ce qui reste sur le disque d'une sortie : fichier (pile, tirage, noms cachés), vignettes, images d'entrée,
    dossier de travail, lignes du journal."""
    stem, files = os.path.splitext(v["name"])[0], bench.files
    return {"file": files("outputs", v["name"]) + files("outputs", ".pile", v["name"])
            + files("outputs", "." + v["name"]) + files("outputs", ".pile", "." + v["name"]),
            "thumbs": files("outputs", ".thumbs", stem + "*"), "inputs": files("outputs", ".inputs", stem),
            "job": files("jobs", v["id"]),
            "journal": [line for line in bench.journal() if line.get("file", "").endswith(v["name"])]}


NOTHING = {"file": [], "thumbs": [], "inputs": [], "job": [], "journal": []}


def with_thumbs(test, v):
    """Vignette de la vidéo et de son image d'entrée faites : toutes ses pièces existent."""
    test.assertEqual(bench.call("GET", "/api/thumb?name=" + v["name"])[0], 200)
    test.assertEqual(bench.call("GET", f"/api/input?name={v['name']}&file=ref_1.png&thumb=1")[0], 200)
    test.assertTrue(all(pieces(v).values()), pieces(v))
    return v


def remains(name, jid):
    """Ce qui reste sur le disque d'une sortie de nom name : fichier (pile, tirages, noms cachés), vignettes et
    vignettes d'entrées (à la casse près : un disque insensible à la casse les confond), images d'entrée, dossier de
    travail, lignes du journal."""
    stem = os.path.splitext(name)[0]
    thumbs = [n for n in os.listdir(bench.launch.THUMBS) if n.casefold().startswith(stem.casefold())] \
        if os.path.isdir(bench.launch.THUMBS) else []
    folders = (bench.launch.P("outputs"), bench.launch.P("outputs", ".pile"))
    return {"file": [n for d in folders for n in (name, "." + name) if os.path.exists(os.path.join(d, n))],
            "thumbs": thumbs, "inputs": os.path.isdir(bench.launch.P("outputs", ".inputs", stem)),
            "job": os.path.isdir(bench.launch.P("jobs", jid)),
            "journal": [line for line in bench.journal() if os.path.basename(line.get("file", "")) == name]}


def listing(name):
    """(nom, prompt, images d'entrée) d'une sortie dans la pile ou les tirages, ou None."""
    for path in ("/api/pile", "/api/history"):
        for it in bench.call("GET", path)[1]:
            if it["name"] == name:
                return it["name"], it["prompt"], it["inputs"]
    return None


class TwinTableTest(bench.BenchCase):
    """Deux sorties de même radical (que le serveur n'écrit jamais : un identifiant par génération), pour chaque forme :
    effacer A laisse B listée telle qu'elle était, et effacer B ensuite ne laisse rien ni de l'une ni de l'autre."""

    def twin(self, b_folder, b_name, hidden=False, restorable=True):
        a = with_thumbs(self, video_in_pile())
        b_path = bench.launch.P(*b_folder.split("/"), ("." if hidden else "") + b_name)
        with open(b_path, "wb") as f:
            f.write(bench.png_bytes())
        bench.launch.append_journal({"file": bench.launch.P(*b_folder.split("/"), b_name), "prompt": "jumelle"})
        if not hidden:
            self.assertEqual(bench.call("GET", "/api/thumb?name=" + b_name)[0], 200)
            # 200 quand B partage les entrées de A sur ce disque, 404 sinon
            self.assertIn(bench.call("GET", f"/api/input?name={b_name}&file=ref_1.png&thumb=1")[0], (200, 404))
        before = listing(b_name)
        route = "/api/discard"
        self.assertEqual(bench.call("POST", route, {"name": a["name"]}), (200, {"ok": True}))
        if hidden:
            bench.launch.restore_hidden_images()
            if not restorable:
                self.assertIsNone(listing(b_name))                     # reste caché : rien d'elle ne revient
                left = remains(a["name"], a["id"])
                self.assertEqual((left["file"], left["thumbs"], left["inputs"], left["job"]), ([], [], False, False))
                os.remove(b_path)
                return
            self.assertEqual(listing(b_name)[:2], (b_name, "jumelle"))
        else:
            self.assertEqual(listing(b_name), before)
        b_route = "/api/discard" if b_folder.endswith(".pile") else "/api/delete"
        self.assertEqual(bench.call("POST", b_route, {"name": b_name}), (200, {"ok": True}))
        empty = {"file": [], "thumbs": [], "inputs": False, "job": False, "journal": []}
        self.assertEqual(remains(a["name"], a["id"]), empty)
        self.assertEqual(remains(b_name, a["id"]), empty)

    def test_another_extension(self):
        self.twin("outputs/.pile", "20260101_120000_abcdef_t2i.png")

    @unittest.skipIf(os.name != "posix", "droits Unix")
    def test_a_folder_that_cannot_be_listed_stops_the_erase(self):
        # la pile illisible (listage refusé) cache peut-être une jumelle : l'effacement s'arrête, rien ne part
        v = with_thumbs(self, video_in_pile())
        print_name = v["name"][:-5] + ".png"
        put("outputs", print_name)
        before = remains(print_name, v["id"]), remains(v["name"], v["id"])
        pile = bench.launch.P("outputs", ".pile")
        os.chmod(pile, 0o300)
        try:
            self.assertEqual(bench.call("POST", "/api/delete", {"name": print_name}),
                             (500, {"error": "effacement incomplet"}))
        finally:
            os.chmod(pile, 0o700)
        self.assertEqual((remains(print_name, v["id"]), remains(v["name"], v["id"])), before)
        self.assertEqual(history_names(), [print_name])

    def test_a_stem_that_differs_only_by_case(self):
        self.twin("outputs", "20260101_120000_ABCDEF_T2I.png")

    def test_a_hidden_twin_that_comes_back(self):
        self.twin("outputs/.pile", "20260101_120000_abcdef_t2i.png", hidden=True)

    def test_a_hidden_twin_that_never_comes_back(self):
        # identifiant en majuscules : pas un nom du serveur, le démarrage ne le rend pas (comes_back)
        self.twin("outputs/.pile", "20260101_120000_ABCDEF_t2i.png", hidden=True, restorable=False)


class WebpSortTest(bench.BenchCase):
    def test_a_kept_webp_becomes_a_print(self):
        v = with_thumbs(self, video_in_pile())
        self.assertEqual(bench.call("POST", "/api/keep", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual((pile_items(), history_names()), ([], [v["name"]]))
        item = bench.call("GET", "/api/history")[1][0]
        self.assertEqual((item["prompt"], item["model"], item["inputs"]), ("a boat at dawn", "h3-video", ["ref_1.png"]))
        code, raw, headers = bench.call_full("GET", "/api/result?name=" + v["name"])
        self.assertEqual((code, headers["Content-Type"]), (200, "image/webp"))

    def test_a_discarded_webp_is_erased_entirely(self):
        other = video_in_pile("keep me", jid="20260101_120001_abcdef")
        v = with_thumbs(self, video_in_pile())
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(v), NOTHING)
        self.assertEqual([it["name"] for it in pile_items()], [other["name"]])
        left = pieces(other)
        self.assertTrue(all(left[k] for k in ("file", "inputs", "job", "journal")), left)

    def test_a_deleted_webp_print_is_erased_entirely(self):
        v = with_thumbs(self, video_in_pile())
        self.assertEqual(bench.call("POST", "/api/keep", {"name": v["name"]})[0], 200)
        self.assertEqual(bench.call("POST", "/api/delete", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(v), NOTHING)
        self.assertEqual(history_names(), [])

    def test_a_webp_that_resists_stays_to_discard_again(self):
        v = with_thumbs(self, video_in_pile())
        with mock.patch.object(bench.launch, "drop_from_journal", side_effect=OSError("journal verrouillé")):
            self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}),
                             (500, {"error": "effacement incomplet"}))
        self.assertEqual([it["name"] for it in pile_items()], [v["name"]])
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(v), NOTHING)


class HiddenWebpTest(bench.BenchCase):
    def test_hidden_webps_left_by_a_crash_come_back_at_start(self):
        kept = video_in_pile("gardée", jid="20260101_120001_abcdef")
        waiting = video_in_pile("en attente")
        self.assertEqual(bench.call("POST", "/api/keep", {"name": kept["name"]})[0], 200)
        out, pile = bench.launch.P("outputs"), bench.launch.P("outputs", ".pile")
        os.replace(os.path.join(out, kept["name"]), os.path.join(out, "." + kept["name"]))
        os.replace(os.path.join(pile, waiting["name"]), os.path.join(pile, "." + waiting["name"]))
        other = os.path.join(pile, "._autre.webp")          # fichier caché d'un volume exFAT ou SMB
        put("outputs/.pile", "._autre.webp", b"AppleDouble")
        self.assertEqual((pile_items(), history_names()), ([], []))
        bench.launch.restore_hidden_images()
        self.assertEqual(([it["name"] for it in pile_items()], history_names()), ([waiting["name"]], [kept["name"]]))
        self.assertTrue(os.path.exists(other))

    def test_a_hidden_copy_of_a_visible_webp_is_removed_at_start(self):
        v = video_in_pile()
        pile = bench.launch.P("outputs", ".pile")
        shutil.copy(os.path.join(pile, v["name"]), os.path.join(pile, "." + v["name"]))
        bench.launch.restore_hidden_images()
        self.assertEqual(bench.files("outputs", ".pile", "." + v["name"]), [])
        self.assertEqual([it["name"] for it in pile_items()], [v["name"]])

    def test_an_interrupted_erase_of_a_webp_comes_back_at_start(self):
        v = with_thumbs(self, video_in_pile())
        real_remove = os.remove

        def remove(fp):
            if os.path.basename(fp) == "." + v["name"]:
                raise KeyboardInterrupt()             # arrêt brutal juste avant le dernier effacement
            real_remove(fp)
        with mock.patch.object(bench.launch.os, "remove", remove), mock.patch.object(bench.launch, "unhide"):
            with self.assertRaises(KeyboardInterrupt):
                with bench.launch.JOURNAL_LOCK:
                    bench.launch.delete_output(bench.launch.P("outputs", ".pile", v["name"]))
        self.assertEqual(pile_items(), [])
        bench.launch.restore_hidden_images()
        self.assertEqual([it["name"] for it in pile_items()], [v["name"]])
        self.assertEqual(bench.call("POST", "/api/discard", {"name": v["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(v), NOTHING)


class FakeEngineTest(unittest.TestCase):
    def test_fake_engine_writes_an_animated_webp(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "20260101_120000_abcdef_t2i.webp")
            code, log = fake_engine("-W", "64", "-H", "48", "--steps", "2", "-o", out)
            self.assertEqual(code, 0, log)
            with open(out, "rb") as f:
                head = f.read(12)
            self.assertEqual((head[:4], head[8:12]), (b"RIFF", b"WEBP"))
            with Image.open(out) as im:
                self.assertTrue(im.is_animated)
                self.assertGreater(im.n_frames, 1)
                self.assertEqual(im.size, (64, 48))
                first = im.convert("RGB").getpixel((32, 24))
                im.seek(im.n_frames - 1)
                last = im.convert("RGB").getpixel((32, 24))
            self.assertNotEqual(first, last, "toutes les images de la vidéo se ressemblent")


if __name__ == "__main__":
    unittest.main()
