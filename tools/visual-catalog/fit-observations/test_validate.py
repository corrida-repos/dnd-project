"""Negative tests: the validator must reject corrupted data (run from repo root)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class ValidatorTest(unittest.TestCase):
    def _run(self, mutate=None):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            dst = t / "tools/visual-catalog/fit-observations"
            shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("contact-sheets", "__pycache__"))
            (t / "backend/data").mkdir(parents=True)
            shutil.copy(ROOT / "backend/data/species-groups.json", t / "backend/data/")
            (t / "frontend").symlink_to(ROOT / "frontend")
            if mutate:
                p = dst / "landmarks.json"
                d = json.loads(p.read_text())
                mutate(d)
                p.write_text(json.dumps(d))
            r = subprocess.run([sys.executable, str(dst / "validate.py")], capture_output=True, text=True)
            return r.returncode, r.stdout

    def test_clean_data_passes(self):
        code, out = self._run()
        self.assertEqual(code, 0, out)
        self.assertIn("cannot validate clothing fit or grips", out)

    def test_invented_coordinate_on_occluded(self):
        def m(d):
            d["images"][5]["landmarks"]["knee.imageLeft"] = {"kind": "point", "status": "occluded", "x": 1, "y": 1}
        code, out = self._run(m)
        self.assertEqual(code, 1)
        self.assertIn("must have null coordinates", out)

    def test_out_of_bounds(self):
        def m(d):
            d["images"][6]["landmarks"]["foot.imageLeft"]["x"] = 5000
        code, out = self._run(m)
        self.assertIn("outside image", out)

    def test_hash_mismatch_and_missing_roster_entry(self):
        def m(d):
            d["images"][7]["source"]["sha256"] = "0" * 64
            d["images"].pop(0)
        code, out = self._run(m)
        self.assertIn("sha256 mismatch", out)
        self.assertIn("roster entries without data", out)

    def test_missing_status(self):
        def m(d):
            d["images"][9]["landmarks"]["elbow.imageRight"].pop("status")
        code, out = self._run(m)
        self.assertIn("not explicit", out)


if __name__ == "__main__":
    unittest.main()
