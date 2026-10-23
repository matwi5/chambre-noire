"""Droits des fichiers créés (décision du 23/10/2026) : le serveur et tools/calibrate.py posent d'abord un masque de
création 0o077, pour que tout ce qu'ils créent, et sd-cli avec eux (PNG privé en clair, qui porte le prompt ;
vignettes ; copies d'images d'entrée ; tirages), ne soit lisible que par le compte qui les fait tourner ; le dossier de
travail d'une génération privée est en 0o700 même sans ce masque."""
import ast, inspect, os, shutil, tempfile, unittest
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
            bench.wait_idle()
        self.assertEqual(seen, [0o700])


if __name__ == "__main__":
    unittest.main()
