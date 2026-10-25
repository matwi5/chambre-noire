"""Copies de la palette et fichiers de l'application installée : les couleurs partagées (fond, texte, accent, halo,
erreur) sont les mêmes dans les jetons de tools/ui/index.html, ceux de la page du code (LOGIN_PAGE de tools/launch.py)
et la page hors ligne de tools/ui/sw.js ; theme-color et le manifeste prennent le fond de l'interface ; les icônes ont
leur taille et leurs coins (transparents pour « any », opaques pour « maskable » et l'icône d'Apple) ; chaque icône du
manifeste existe et est servie sans code d'accès (PUBLIC_FILES)."""
import json, os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "..", "tools", "ui")
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import launch  # noqa: E402

SHARED = ("void", "ink", "ink2", "accent", "on-accent", "halo", "err")
ICONS = {"icon-192.png": (192, "transparent"), "icon-512.png": (512, "transparent"),
         "icon-maskable-512.png": (512, "opaque"), "apple-touch-icon.png": (180, "opaque")}


def read_ui(name):
    with open(os.path.join(UI, name), encoding="utf-8") as f:
        return f.read()


def root_tokens(css):
    """Jetons --nom:valeur du premier bloc :root d'une feuille de style : {nom : valeur, sans espaces}."""
    block = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    return {m.group(1): re.sub(r"\s+", "", m.group(2)) for m in re.finditer(r"--([\w-]+)\s*:\s*([^;}]+)", block)}


def offline_colors(sw):
    """Couleurs de la page hors ligne de sw.js, rangées sous le nom du jeton qu'elles recopient."""
    style = re.search(r"<style>(.*?)</style>", sw, re.S).group(1).replace("\n", "")
    body = re.search(r"body\{([^}]*)\}", style).group(1)
    button = re.search(r"button\{([^}]*)\}", style).group(1)
    return {"ink": re.search(r"(?<![-\w])color:([^;]+)", body).group(1),
            "halo": re.search(r"radial-gradient\([^,]+,(rgba?\([^)]*\))", body).group(1),
            "void": re.search(r"\)\s*(#[0-9a-fA-F]{3,8})", body).group(1),
            "ink2": re.search(r"p\{color:([^;}]+)", style).group(1),
            "accent": re.search(r"background:([^;]+)", button).group(1),
            "on-accent": re.search(r"(?<![-\w])color:([^;]+)", button).group(1)}


def theme_color(html):
    return re.search(r'<meta name="theme-color" content="([^"]+)"', html).group(1)


def palette_faults(index, login, sw):
    """Différences entre les copies de la palette : [texte], vide si tout concorde."""
    ui, page, offline = root_tokens(index), root_tokens(login), offline_colors(sw)
    faults = [f"--{n} : index.html {ui.get(n)}, LOGIN_PAGE {page.get(n)}" for n in SHARED
              if n in page and page[n] != ui.get(n)]
    faults += [f"--{n} : index.html {ui.get(n)}, sw.js {v}" for n, v in offline.items() if v != ui.get(n)]
    faults += [f"theme-color de {where} : {theme_color(html)}, --void {ui['void']}"
               for where, html in (("index.html", index), ("LOGIN_PAGE", login), ("sw.js", sw))
               if theme_color(html) != ui["void"]]
    return faults


class PaletteTest(unittest.TestCase):
    def test_the_three_copies_share_the_palette(self):
        index, sw = read_ui("index.html"), read_ui("sw.js")
        self.assertGreaterEqual(len([n for n in SHARED if n in root_tokens(launch.LOGIN_PAGE)]), 6)
        self.assertEqual(len(offline_colors(sw)), 6)
        self.assertEqual(palette_faults(index, launch.LOGIN_PAGE, sw), [])

    def test_a_changed_value_is_caught(self):
        index, sw = read_ui("index.html"), read_ui("sw.js")
        self.assertEqual(len(palette_faults(index, launch.LOGIN_PAGE.replace("--accent:#ffa53a", "--accent:#ffa53b"),
                                            sw)), 1)
        self.assertEqual(len(palette_faults(index, launch.LOGIN_PAGE, sw.replace("#1c1006", "#1c1007"))), 1)
        changed = index.replace("--halo:rgba(190,28,18,.22)", "--halo:rgba(190,28,18,.30)", 1)
        self.assertEqual(len(palette_faults(changed, launch.LOGIN_PAGE, sw)), 2)   # LOGIN_PAGE et sw.js


class InstalledAppTest(unittest.TestCase):
    def test_icons_have_their_size_and_corners(self):
        from PIL import Image
        for name, (size, corners) in ICONS.items():
            with Image.open(os.path.join(UI, name)) as im:
                self.assertEqual(im.size, (size, size), name)
                alpha = im.convert("RGBA").getpixel((0, 0))[3]
            self.assertEqual(alpha, 0 if corners == "transparent" else 255, f"{name} : coin {corners} attendu")

    def test_the_manifest_points_to_served_icons_on_the_interface_background(self):
        manifest = json.loads(read_ui("manifest.webmanifest"))
        void = root_tokens(read_ui("index.html"))["void"]
        self.assertEqual((manifest["theme_color"], manifest["background_color"]), (void, void))
        self.assertEqual(len(manifest["icons"]), 3)
        for icon in manifest["icons"]:
            self.assertIn(icon["src"], launch.PUBLIC_FILES, icon["src"])
            self.assertTrue(os.path.isfile(os.path.join(UI, launch.PUBLIC_FILES[icon["src"]][0])), icon["src"])
            name = icon["src"].lstrip("/")
            self.assertEqual(icon["sizes"], "{0}x{0}".format(ICONS[name][0]), name)
        self.assertEqual([i["purpose"] for i in manifest["icons"]], ["any", "any", "maskable"])


if __name__ == "__main__":
    unittest.main()
