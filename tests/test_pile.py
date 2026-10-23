"""Pile de l'espace public, sur le banc à faux moteur (voir bench.py) : une image terminée y attend d'être triée
(outputs/.pile/), Garder la fait passer dans les tirages, Jeter l'efface entièrement, Supprimer un tirage aussi."""
import os, shutil, threading, unittest
from unittest import mock

import bench
from bench import call, files, generate, wait_job


def pile_names():
    code, items = call("GET", "/api/pile")
    assert code == 200, bench.short((code, items))
    return [it["name"] for it in items]


def history_names():
    return [it["name"] for it in call("GET", "/api/history")[1]]


class ArrivalTest(bench.BenchCase):
    def test_finished_image_waits_in_the_pile(self):
        ref = bench.data_url(bench.png_bytes())
        j = wait_job(generate("make it blue", mode="edit", ref_images=[ref])["id"])
        self.assertEqual(j["status"], "done")
        self.assertEqual(pile_names(), [j["name"]])
        self.assertNotIn(j["name"], history_names())
        self.assertEqual(files("outputs", ".pile", "*.png"), [bench.launch.P("outputs", ".pile", j["name"])])
        self.assertEqual(files("outputs", "*.png"), [])
        item = call("GET", "/api/pile")[1][0]
        self.assertEqual((item["prompt"], item["mode"], item["inputs"], item["lot"]),
                         ("make it blue", "edit", ["ref_1.png"], None))
        code, raw = call("GET", "/api/result?name=" + j["name"])
        self.assertEqual((code, raw[:8]), (200, b"\x89PNG\r\n\x1a\n"))
        code, raw = call("GET", "/api/thumb?name=" + j["name"])
        self.assertEqual((code, raw[:2]), (200, b"\xff\xd8"))
        code, raw = call("GET", f"/api/input?name={j['name']}&file=ref_1.png")
        self.assertEqual((code, raw[:8]), (200, b"\x89PNG\r\n\x1a\n"))

    def test_pile_lists_the_latest_first(self):
        first = wait_job(generate("first one")["id"])
        second = wait_job(generate("second one")["id"])
        self.assertEqual(pile_names(), [second["name"], first["name"]])

    def test_image_from_before_the_pile_is_a_print(self):
        with open(bench.launch.P("outputs", "20250101_120000_abcdef_t2i.png"), "wb") as f:
            f.write(bench.png_bytes())
        self.assertEqual(history_names(), ["20250101_120000_abcdef_t2i.png"])
        self.assertEqual(pile_names(), [])


class KeepTest(bench.BenchCase):
    def test_kept_image_becomes_a_print(self):
        ref = bench.data_url(bench.png_bytes())
        j = wait_job(generate("make it blue", mode="edit", ref_images=[ref])["id"])
        self.assertEqual(call("GET", "/api/thumb?name=" + j["name"])[0], 200)
        self.assertEqual(call("POST", "/api/keep", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(pile_names(), [])
        self.assertEqual(history_names(), [j["name"]])
        self.assertEqual(files("outputs", "*.png"), [bench.launch.P("outputs", j["name"])])
        self.assertEqual(files("outputs", ".pile", "*"), [])
        item = call("GET", "/api/history")[1][0]
        self.assertEqual((item["prompt"], item["inputs"]), ("make it blue", ["ref_1.png"]))
        for path in ("/api/result?name=", "/api/thumb?name="):
            self.assertEqual(call("GET", path + j["name"])[0], 200, path)
        self.assertEqual(call("GET", f"/api/input?name={j['name']}&file=ref_1.png")[0], 200)

    def test_second_sort_is_refused(self):
        j = wait_job(generate("a red car")["id"])
        self.assertEqual(call("POST", "/api/keep", {"name": j["name"]})[0], 200)
        for route in ("/api/keep", "/api/discard"):
            self.assertEqual(call("POST", route, {"name": j["name"]}), (404, {"error": "déjà triée"}), route)
        self.assertEqual(history_names(), [j["name"]])

    def test_keep_never_overwrites_a_print(self):
        j = wait_job(generate("a red car")["id"])
        with open(bench.launch.P("outputs", j["name"]), "wb") as f:
            f.write(b"tirage")
        code, reply = call("POST", "/api/keep", {"name": j["name"]})
        self.assertEqual(code, 409, reply)
        self.assertEqual(pile_names(), [j["name"]])
        with open(bench.launch.P("outputs", j["name"]), "rb") as f:
            self.assertEqual(f.read(), b"tirage")

    def test_names_outside_the_pile_are_unknown(self):
        for name in ("../journal.jsonl", ".pile", "", None, 3, "absente.png"):
            with self.subTest(name=name):
                self.assertEqual(call("POST", "/api/keep", {"name": name}), (404, {"error": "déjà triée"}))


def edited_image(test, prompt="make it blue"):
    """Image d'édition terminée, avec sa vignette et celle de son image d'entrée déjà faites : toutes ses pièces."""
    j = wait_job(generate(prompt, mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"])
    test.assertEqual(j["status"], "done")
    test.assertEqual(call("GET", "/api/thumb?name=" + j["name"])[0], 200)
    test.assertEqual(call("GET", f"/api/input?name={j['name']}&file=ref_1.png&thumb=1")[0], 200)
    return j


def pieces(j):
    """Ce qui reste sur le disque d'une image : PNG (pile ou tirage), vignettes, images d'entrée, dossier de travail,
    lignes du journal."""
    stem = j["name"][:-4]
    return {"png": files("outputs", j["name"]) + files("outputs", ".pile", j["name"]),
            "thumbs": files("outputs", ".thumbs", stem + "*"),
            "inputs": files("outputs", ".inputs", stem), "job": files("jobs", j["id"]),
            "journal": [line for line in journal_lines() if j["name"].encode() in line]}


def journal_lines():
    """Lignes du journal, en octets, illisibles comprises (bench.journal ne lit que des lignes JSON)."""
    try:
        with open(bench.launch.P("outputs", "journal.jsonl"), "rb") as f:
            return f.read().splitlines(True)
    except FileNotFoundError:
        return []


NOTHING = {"png": [], "thumbs": [], "inputs": [], "job": [], "journal": []}


class DiscardTest(bench.BenchCase):
    def test_discard_erases_everything(self):
        other = edited_image(self, "keep me")
        j = edited_image(self)
        self.assertTrue(all(pieces(j).values()), pieces(j))
        unreadable = [b"ligne illisible\n", b"\xff\xfe pas de l'UTF-8\n", b"[1, 2]\n", b'{"file": 3}\n']
        with open(bench.launch.P("outputs", "journal.jsonl"), "ab") as f:
            f.write(b"".join(unreadable))
        before = journal_lines()
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(j), NOTHING)
        self.assertEqual(pile_names(), [other["name"]])
        self.assertEqual(journal_lines(), [x for x in before if j["name"].encode() not in x])
        self.assertEqual(journal_lines()[-4:], unreadable)
        self.assertTrue(all(pieces(other).values()), pieces(other))
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (404, {"error": "déjà triée"}))

    def test_discard_skips_pieces_already_gone(self):
        j = edited_image(self)
        shutil.rmtree(bench.launch.P("jobs", j["id"]))
        shutil.rmtree(bench.launch.P("outputs", ".inputs"))
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(j), NOTHING)

    def test_discard_never_touches_a_print(self):
        j = edited_image(self)
        self.assertEqual(call("POST", "/api/keep", {"name": j["name"]})[0], 200)
        kept = pieces(j)
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (404, {"error": "déjà triée"}))
        self.assertEqual(pieces(j), kept)
        self.assertEqual(history_names(), [j["name"]])

    def test_delete_erases_a_print_as_completely(self):
        j = edited_image(self)
        self.assertEqual(call("POST", "/api/keep", {"name": j["name"]})[0], 200)
        self.assertEqual(call("POST", "/api/delete", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(j), NOTHING)
        self.assertEqual(history_names(), [])

    def test_delete_never_touches_the_pile(self):
        j = edited_image(self)
        kept = pieces(j)
        self.assertEqual(call("POST", "/api/delete", {"name": j["name"]})[0], 404)
        self.assertEqual(pieces(j), kept)

    def test_journal_survives_a_failed_rewrite(self):
        j = edited_image(self)
        fp = bench.launch.P("outputs", "journal.jsonl")
        before = journal_lines()
        real_replace = os.replace

        def replace(src, dst):
            if dst == fp:
                raise failure
            real_replace(src, dst)
        for failure in (OSError("disque plein"), KeyboardInterrupt()):
            points = {"write_synced": mock.patch.object(bench.launch, "write_synced", side_effect=failure),
                      "os.replace": mock.patch.object(bench.launch.os, "replace", replace)}
            for at, patch in points.items():
                with self.subTest(failure=type(failure).__name__, at=at):
                    with patch, self.assertRaises(type(failure)):
                        bench.launch.drop_from_journal(j["name"])
                    self.assertEqual(journal_lines(), before)
                    self.assertEqual(files("outputs", "journal.jsonl.tmp"), [])


    def test_a_failed_piece_does_not_stop_the_others(self):
        j = edited_image(self)
        with mock.patch.object(bench.launch, "delete_extras", side_effect=OSError("vignette verrouillée")):
            self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}),
                             (500, {"error": "effacement incomplet"}))
        left = pieces(j)
        self.assertEqual({k: v for k, v in left.items() if v}.keys(), {"thumbs", "inputs"}, left)


class ArrivalFailureTest(bench.BenchCase):
    def test_journal_failure_leaves_an_image_that_discard_erases(self):
        with mock.patch.object(bench.launch, "append_journal", side_effect=OSError("disque plein")):
            j = wait_job(generate("make it blue", mode="edit", ref_images=[bench.data_url(bench.png_bytes())])["id"])
        self.assertEqual(j["status"], "done")
        self.assertEqual(pile_names(), [j["name"]])
        self.assertEqual(pieces(j)["journal"], [])
        self.assertEqual(call("POST", "/api/discard", {"name": j["name"]}), (200, {"ok": True}))
        self.assertEqual(pieces(j), NOTHING)

    def test_an_interrupted_arrival_never_leaves_a_journal_line_without_its_image(self):
        d = bench.launch.P("jobs", "20261023_120000_abcdef")
        os.makedirs(d)
        out = os.path.join(d, "20261023_120000_abcdef_t2i.png")
        job = {"out": out, "dir": d, "status": "running"}
        for at in ("os.replace", "append_journal"):
            with self.subTest(at=at):
                with open(out, "wb") as f:
                    f.write(bench.png_bytes())
                target = (bench.launch.os, "replace") if at == "os.replace" else (bench.launch, "append_journal")
                with mock.patch.object(*target, side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
                    bench.launch.to_pile(dict(job), {"prompt": "zq5 coupée"})
                in_pile = files("outputs", ".pile", "*.png")
                self.assertEqual(in_pile != [], at == "append_journal")   # l'image n'arrive qu'entière, ou pas du tout
                self.assertEqual([x for x in journal_lines() if b"zq5" in x] if in_pile else [], [])
                for fp in in_pile:
                    os.remove(fp)

    def test_cancelled_during_the_arrival_leaves_nothing(self):
        real = bench.launch.to_pile

        def cancelled_first(job, meta):
            bench.launch.cancel_job(job)           # l'annulation arrive juste avant le passage dans la pile
            return real(job, meta)
        with bench.capture_push() as sent, mock.patch.object(bench.launch, "to_pile", cancelled_first):
            j = wait_job(generate("SLOW=0.05 a red car", steps=4)["id"])
            bench.wait_idle()
        self.assertEqual(j["status"], "cancelled")
        self.assertEqual((pile_names(), files("jobs", j["id"]), bench.journal(), sent.decided), ([], [], [], []))


class ThumbnailTest(bench.BenchCase):
    def test_a_thumbnail_finished_after_discard_does_not_stay(self):
        j = wait_job(generate("a red car")["id"])
        real = bench.launch.thumb_jpeg

        def discard_meanwhile(src):
            data = real(src)
            self.assertEqual(bench.launch.sort_image("discard", j["name"]), (200, {"ok": True}))
            return data
        with mock.patch.object(bench.launch, "thumb_jpeg", discard_meanwhile):
            self.assertEqual(call("GET", "/api/thumb?name=" + j["name"])[0], 404)
        self.assertEqual(files("outputs", ".thumbs", "*"), [])


def rev():
    return call("GET", "/api/status")[1]["rev"]


class RevTest(bench.BenchCase):
    def test_a_private_generation_does_not_move_the_public_rev(self):
        session = bench.create_private("Mot2passe!")
        before = rev()
        code, job = call("POST", "/api/generate", bench.gen_body("zq6 privée", private=True), private=session)
        self.assertEqual(code, 202, job)
        self.assertEqual(wait_job(job["id"], private=session)["status"], "done")
        bench.wait_idle()
        self.assertEqual(rev(), before)

    def test_rev_changes_with_the_pile_and_the_prints(self):
        start = rev()
        j = wait_job(generate("a red car")["id"])
        arrived = rev()
        self.assertNotEqual(arrived, start)
        other = wait_job(generate("a blue car")["id"])
        steps = [("keep", j["name"]), ("delete", j["name"]), ("discard", other["name"])]
        last = rev()
        for action, name in steps:
            with self.subTest(action=action):
                self.assertEqual(call("POST", "/api/" + action, {"name": name})[0], 200)
                self.assertNotEqual(rev(), last)
                last = rev()
        self.assertEqual(call("POST", "/api/discard", {"name": other["name"]})[0], 404)
        self.assertEqual(rev(), last)


class ConcurrentSortTest(bench.BenchCase):
    def test_first_sort_wins(self):
        """Un second geste arrive pendant le premier, entre sa vérification et son déplacement ou effacement (là où
        rev change) : il attend la fin du premier et ne trouve plus l'image."""
        for first, second in (("keep", "discard"), ("discard", "keep"), ("discard", "discard")):
            with self.subTest(gestures=(first, second)):
                j = edited_image(self)
                replies = {}
                racer = threading.Thread(target=lambda: replies.setdefault("second",
                                                                           bench.launch.sort_image(second, j["name"])))

                class Racing(dict):
                    def __setitem__(self, key, value):
                        super().__setitem__(key, value)
                        if threading.current_thread() is not racer and not racer.ident:
                            racer.start()
                            racer.join(0.5)        # bloqué par le premier geste, ou déjà fini sans verrou
                with mock.patch.object(bench.S, "rev", Racing(bench.S.rev)):
                    replies["first"] = bench.launch.sort_image(first, j["name"])
                racer.join()
                self.assertEqual(replies, {"first": (200, {"ok": True}), "second": (404, {"error": "déjà triée"})})
                if first == "keep":
                    self.assertEqual(history_names(), [j["name"]])
                    call("POST", "/api/delete", {"name": j["name"]})
                else:
                    self.assertEqual(pieces(j), NOTHING)
                self.assertEqual(pile_names(), [])


if __name__ == "__main__":
    unittest.main()
