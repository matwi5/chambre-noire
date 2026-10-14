"""Prompts enregistrés : routes /api/prompts et fichier sur le disque, sur le banc (voir bench.py)."""
import json, os, unittest

import bench
from bench import call, launch


def saved():
    return call("GET", "/api/prompts")[1]["saved"]


def create(title="Ciel orange", text="Replace the sky with an orange sunset", usage="edit", **kw):
    code, p = call("POST", "/api/prompts", {"title": title, "text": text, "usage": usage, **kw})
    assert code == 200, (code, p)
    return p


class PromptsCase(bench.BenchCase):
    def setUp(self):
        super().setUp()
        if os.path.exists(launch.PROMPTS_FILE):
            os.remove(launch.PROMPTS_FILE)

    def on_disk(self):
        with open(launch.PROMPTS_FILE, encoding="utf-8") as f:
            return json.load(f)


class SavedPromptsTest(PromptsCase):
    def test_a_created_prompt_is_listed_and_kept_on_disk(self):
        self.assertEqual(saved(), [])
        p = create("Ciel orange", "Replace the sky with an orange sunset", "edit")
        self.assertEqual((p["title"], p["text"], p["usage"]), ("Ciel orange", "Replace the sky with an orange sunset", "edit"))
        self.assertEqual(saved(), [p])
        self.assertEqual(self.on_disk(), [p])

    def test_modifying_changes_title_and_text_only(self):
        p = create("Ciel", "orange sky", "edit")
        code, q = call("POST", "/api/prompts", {"id": p["id"], "title": " Ciel du soir ", "text": "red sky", "usage": "t2i"})
        self.assertEqual(code, 200)
        self.assertEqual(q, {**p, "title": "Ciel du soir", "text": "red sky"})   # même usage, même dernière utilisation
        self.assertEqual(saved(), [q])
        self.assertEqual(call("POST", "/api/prompts", {"id": "inconnu", "title": "a", "text": "b"})[0], 404)

    def test_deleting_removes_the_prompt(self):
        a, b = create("A", "first"), create("B", "second")
        self.assertEqual(call("POST", "/api/prompts/delete", {"id": a["id"]}), (200, {"ok": True}))
        self.assertEqual(saved(), [b])
        self.assertEqual(self.on_disk(), [b])
        self.assertEqual(call("POST", "/api/prompts/delete", {"id": a["id"]})[0], 404)

    def test_list_is_sorted_by_last_use(self):
        a, b, c = create("A", "first"), create("B", "second"), create("C", "third")
        self.assertEqual([p["title"] for p in saved()], ["C", "B", "A"])   # un prompt créé passe en tête
        code, used = call("POST", "/api/prompts/used", {"id": a["id"]})
        self.assertEqual((code, used["id"]), (200, a["id"]))
        self.assertGreater(used["used"], c["used"])
        self.assertEqual([p["title"] for p in saved()], ["A", "C", "B"])
        self.assertEqual(call("POST", "/api/prompts/used", {"id": "inconnu"})[0], 404)

    def test_only_title_text_and_usage_are_kept(self):
        p = create("Portrait", "a portrait", "t2i", width=1024, height=768, steps=20, seed=42)
        self.assertEqual(sorted(p), ["id", "text", "title", "usage", "used"])
        self.assertEqual(sorted(self.on_disk()[0]), ["id", "text", "title", "usage", "used"])

    def test_invalid_requests_are_refused(self):
        p = create("Gardé", "kept")
        for body in ({"title": "", "text": "x", "usage": "t2i"}, {"title": "   ", "text": "x", "usage": "t2i"},
                     {"title": "x", "text": " \n", "usage": "t2i"}, {"title": "x", "usage": "t2i"},
                     {"title": 3, "text": "x", "usage": "t2i"}, {"title": "x", "text": ["x"], "usage": "t2i"},
                     {"title": "x" * 81, "text": "x", "usage": "t2i"}, {"title": "x", "text": "x" * 4001, "usage": "t2i"},
                     {"title": "x", "text": "x", "usage": "hist"}, {"title": "x", "text": "x"},
                     {"id": p["id"], "title": "", "text": "x"}, {"id": 12, "title": "x", "text": "x"}, []):
            with self.subTest(body=body):
                self.assertEqual(call("POST", "/api/prompts", body)[0], 400)
        for path in ("/api/prompts/delete", "/api/prompts/used"):
            self.assertEqual(call("POST", path, {})[0], 400)
            self.assertEqual(call("POST", path, {"id": None})[0], 400)
        self.assertEqual(call("POST", "/api/prompts", {"title": "x" * 80, "text": "x" * 4000, "usage": "mask"})[0], 200)
        self.assertEqual(saved()[1], p)

    def test_the_list_has_a_ceiling(self):
        with bench.mock.patch.object(launch, "MAX_SAVED_PROMPTS", 2):
            create("A", "a"), create("B", "b")
            self.assertEqual(call("POST", "/api/prompts", {"title": "C", "text": "c", "usage": "t2i"})[0], 400)
        self.assertEqual(len(saved()), 2)

    def test_the_file_is_never_half_written(self):
        p = create("Gardé", "kept")
        before = open(launch.PROMPTS_FILE, "rb").read()

        def half(data, f, **kw):                    # disque plein au milieu de l'écriture
            f.write(json.dumps(data)[:10])
            raise OSError("disque plein")
        with bench.mock.patch.object(launch.json, "dump", side_effect=half):
            code, err = call("POST", "/api/prompts", {"title": "Perdu", "text": "lost", "usage": "t2i"})
        self.assertEqual(code, 500)
        self.assertIn("disque plein", err["error"])
        self.assertEqual(open(launch.PROMPTS_FILE, "rb").read(), before)
        self.assertEqual(saved(), [p])
        self.assertEqual(bench.files("tools", "saved_prompts.json*"), [launch.PROMPTS_FILE])

    def test_an_unreadable_file_is_reported_and_never_overwritten(self):
        for content in ("{pas du json", "{}", '[{"title": "sans id"}]'):   # fichier modifié à la main
            with self.subTest(content=content):
                with open(launch.PROMPTS_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                self.assertEqual(call("GET", "/api/prompts")[0], 500)
                self.assertEqual(call("POST", "/api/prompts", {"title": "A", "text": "a", "usage": "t2i"})[0], 500)
                self.assertEqual(open(launch.PROMPTS_FILE, encoding="utf-8").read(), content)

    def test_simultaneous_saves_are_all_kept(self):
        threads = [bench.threading.Thread(target=create, args=(f"P{k}", f"prompt {k}")) for k in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(p["title"] for p in self.on_disk()), sorted(f"P{k}" for k in range(12)))


class PromptTypesTest(PromptsCase):
    def test_the_validated_prompt_types_are_listed(self):
        types = call("GET", "/api/prompts")[1]["types"]
        self.assertEqual([(t["title"], t["usage"]) for t in types], [
            ("Repeindre", "edit"), ("Changer l'arrière-plan", "edit"), ("Retirer un élément", "edit"),
            ("Fond blanc produit", "edit"), ("Style aquarelle", "edit"), ("Heure dorée", "edit"),
            ("Ajouter un texte", "edit"), ("Photo réaliste", "t2i"), ("Portrait studio", "t2i"),
            ("Illustration plate", "t2i"), ("Remplacer la zone", "mask")])
        self.assertEqual(types[0]["text"], "Repeins [l'objet] en [couleur], en gardant les reflets, les ombres et tout le "
                                           "reste de l'image identique.")
        self.assertEqual(types[6]["text"], "Ajoute le texte « [texte] » sur [l'emplacement], dans une typographie [style] "
                                           "lisible et bien intégrée.")
        self.assertEqual(len({t["id"] for t in types}), 11)
        self.assertTrue(all(sorted(t) == ["id", "text", "title", "usage"] for t in types))

    def test_no_route_changes_the_prompt_types(self):
        types = call("GET", "/api/prompts")[1]["types"]
        before = open(launch.PROMPT_TYPES_FILE, "rb").read()
        t = types[0]
        self.assertEqual(call("POST", "/api/prompts", {"id": t["id"], "title": "Changé", "text": "changed"})[0], 404)
        self.assertEqual(call("POST", "/api/prompts/used", {"id": t["id"]})[0], 404)
        self.assertEqual(call("POST", "/api/prompts/delete", {"id": t["id"]})[0], 404)
        self.assertEqual(call("GET", "/api/prompts")[1], {"saved": [], "types": types})
        self.assertEqual(open(launch.PROMPT_TYPES_FILE, "rb").read(), before)

    def test_duplicating_a_prompt_type_makes_an_editable_saved_prompt(self):
        t = call("GET", "/api/prompts")[1]["types"][7]
        p = create(t["title"], t["text"], t["usage"])                # « Dupliquer » de l'interface
        self.assertNotEqual(p["id"], t["id"])
        q = call("POST", "/api/prompts", {"id": p["id"], "title": "Ma photo", "text": t["text"]})[1]
        self.assertEqual((q["title"], q["usage"]), ("Ma photo", "t2i"))
        self.assertEqual(call("GET", "/api/prompts")[1]["types"][7], t)


class PromptsAccessTest(PromptsCase):
    def test_other_devices_share_the_same_prompts_with_the_access_cookie(self):
        p = create("Mac", "saved on the Mac")
        self.assertEqual(call("GET", "/api/prompts", remote=True)[1]["saved"], [p])
        code, q = call("POST", "/api/prompts", {"title": "Téléphone", "text": "saved on the phone", "usage": "t2i"}, remote=True)
        self.assertEqual(code, 200)
        self.assertEqual(saved(), [q, p])

    def test_prompt_routes_follow_the_access_rules(self):
        p = create()
        self.assertEqual(call("GET", "/api/prompts", remote=True, cookie=False)[0], 401)
        for path, body in (("/api/prompts", {"title": "x", "text": "x", "usage": "t2i"}),
                           ("/api/prompts/delete", {"id": p["id"]}), ("/api/prompts/used", {"id": p["id"]})):
            with self.subTest(path=path):
                self.assertEqual(call("POST", path, body, remote=True, cookie=False)[0], 401)
                self.assertEqual(call("POST", path, body, headers={"Content-Type": "text/plain"})[0], 415)
                self.assertEqual(call("POST", path, body, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(saved(), [p])


if __name__ == "__main__":
    unittest.main()
