"""Droits des fichiers créés (décision du 23/10/2026) : le serveur et tools/calibrate.py posent d'abord un masque de
création 0o077, pour que tout ce qu'ils créent, et sd-cli avec eux (PNG privé en clair, qui porte le prompt ;
vignettes ; copies d'images d'entrée ; tirages), ne soit lisible que par le compte qui les fait tourner ; le dossier de
travail d'une génération privée est en 0o700 même sans ce masque."""
import ast, inspect, os, shutil, sys, tempfile, unittest
from unittest import mock

import bench
import calibrate

CODE = "Mot2passe!"


def first_call(function):
    """Nom de la première fonction appelée par function (sa docstring sautée), lu dans son arbre de syntaxe : le banc
    n'exécute ni main() ni tools/calibrate.py ; None si la première instruction n'est pas un appel."""
    body = ast.parse(inspect.getsource(function)).body[0].body
    if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Call):
        return ast.unparse(first.value.func)
    return None


class RestrictNewFilesTest(unittest.TestCase):
    def test_the_server_and_the_calibration_restrict_new_files_first(self):
        self.assertEqual(first_call(bench.launch.main), "restrict_new_files")
        self.assertEqual(first_call(calibrate.main), "launch.restrict_new_files")

    @unittest.skipIf(os.name == "nt", "droits Unix")
    def test_input_copies_follow_the_mask_not_their_source(self):
        old, d = os.umask(0o022), tempfile.mkdtemp()
        try:
            job, out = os.path.join(d, "job"), os.path.join(d, "image.png")
            os.mkdir(job)
            with open(os.path.join(job, "init.png"), "wb") as f:     # entrée d'avant, en 0o644
                f.write(bench.png_bytes())
            bench.launch.restrict_new_files()
            with mock.patch.object(bench.launch, "INPUTS", os.path.join(d, ".inputs")):
                bench.launch.save_inputs(job, out)
            copy = os.path.join(d, ".inputs", "image", "init.png")
            self.assertEqual(os.stat(copy).st_mode & 0o777, 0o600)
        finally:
            os.umask(old)
            shutil.rmtree(d)


def calls_in(function):
    """Noms des fonctions appelées par function, lus dans son arbre de syntaxe."""
    return {ast.unparse(node.func) for node in ast.walk(ast.parse(inspect.getsource(function)))
            if isinstance(node, ast.Call)}


class ClosedFoldersTest(bench.BenchCase):
    """Au lancement, le serveur ferme ses dossiers aux autres comptes (0o700) : ils ne peuvent plus y lister les noms
    des images, ni voir apparaître les dossiers de travail privés (décision du 23/10/2026)."""

    def test_main_closes_the_folders(self):
        self.assertIn("close_folders", calls_in(bench.launch.main))

    @unittest.skipIf(os.name == "nt", "droits Unix")
    def test_folders_from_before_are_closed(self):
        folders = [bench.launch.P(*p) for p in (("outputs",), ("outputs", ".pile"), ("outputs", ".thumbs"),
                                                ("outputs", ".inputs"), ("jobs",), ("logs",))]
        for d in folders:
            os.makedirs(d, exist_ok=True)
            os.chmod(d, 0o755)
        bench.launch.close_folders()
        self.assertEqual([os.stat(d).st_mode & 0o777 for d in folders], [0o700] * len(folders))

    @unittest.skipIf(os.name == "nt", "droits Unix")
    def test_a_folder_that_refuses_does_not_stop_the_start(self):
        real_chmod, bench.LOG[:] = os.chmod, []

        def chmod(path, mode):
            if path == bench.launch.P("jobs"):
                raise PermissionError("autre propriétaire")
            real_chmod(path, mode)
        with mock.patch.object(bench.launch.os, "chmod", chmod):
            bench.launch.close_folders()
        self.assertEqual(os.stat(bench.launch.P("logs")).st_mode & 0o777, 0o700)
        self.assertEqual(bench.LOG, ["[launch] dossiers non fermés aux autres comptes"])


@unittest.skipIf(sys.platform != "darwin", "LaunchAgent macOS")
class ServiceMaskTest(unittest.TestCase):
    def test_the_service_creates_its_log_for_the_owner_only(self):
        import make_service
        spec = make_service.service_spec()
        self.assertEqual(spec["Umask"], 0o077)          # 63 : launchd le pose avant d'ouvrir logs/service.log
        self.assertEqual(spec["StandardOutPath"], spec["StandardErrorPath"])


@unittest.skipIf(os.name == "nt", "droits Unix")
class PrivateWorkFolderTest(bench.BenchCase):
    def test_a_private_work_folder_is_owner_only_without_the_mask(self):
        session = bench.create_private(CODE)
        seen = []
        real = bench.launch.run_job

        def look(job):
            seen.append(os.stat(job["dir"]).st_mode & 0o777)
            return real(job)
        with mock.patch.object(bench.launch, "run_job", look):
            code, job = bench.call("POST", "/api/generate", bench.gen_body("zq9", private=True), private=session)
            self.assertEqual(code, 202, job)
            bench.wait_job(job["id"], private=session)
        self.assertEqual(seen, [0o700])


if __name__ == "__main__":
    unittest.main()
