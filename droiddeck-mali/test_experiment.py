import importlib.util
from pathlib import Path
import tempfile
import unittest

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

patch = load("patch", "patch_mali_icd.py")
check = load("check", "check_lavapipe.py")

class Tests(unittest.TestCase):
    def test_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            f = Path(temp) / "source"
            for old, new in [(patch.OLD_ICD, patch.NEW_ICD), (patch.OLD_SESSION, patch.NEW_SESSION)]:
                f.write_text("start\n" + old + "\nend")
                self.assertEqual(patch.apply(f, old, new), "patched")
                self.assertEqual(patch.apply(f, old, new), "already patched")
    def test_unknown_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f = Path(temp) / "source"
            f.write_text("different upstream")
            with self.assertRaises(RuntimeError):
                patch.apply(f, patch.OLD_ICD, patch.NEW_ICD)
    def test_missing_lavapipe_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):
                check.inspect(Path(temp))

if __name__ == "__main__":
    unittest.main()
