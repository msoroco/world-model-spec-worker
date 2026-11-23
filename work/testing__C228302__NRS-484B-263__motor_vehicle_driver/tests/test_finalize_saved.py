import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from controlled_access_exit import CASES, measure_history
from test_controlled_access_exit import rows, site
from test_saved_audit import packet

spec = importlib.util.spec_from_file_location("finalize_saved", root / "finalize_saved.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Tests(unittest.TestCase):
    def _files(self, directory):
        base = Path(directory)
        s, h, p, o = [base / x for x in ("site.json", "history.json", "packet.json", "out.json")]
        s.write_text(json.dumps(site()))
        h.write_text(json.dumps(rows(CASES[0])))
        data = packet()
        data["site_sha256"] = hashlib.sha256(s.read_bytes()).hexdigest()
        data["original_history_sha256"] = hashlib.sha256(h.read_bytes()).hexdigest()
        data["measurement"] = {**measure_history(rows(CASES[0]), site(), CASES[0]),
                               "source_history_sha256": data["original_history_sha256"]}
        p.write_text(json.dumps(data))
        return s, h, p, o

    def test_positive_saved_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            s, h, p, o = self._files(directory)
            result = module.process(s, h, p, o)
            self.assertEqual(result["measurement"]["first_entry_frame"], 120)
            self.assertTrue(o.exists())
            self.assertIsNone(result["legal_judgment"])

    def test_reject_stale_history(self):
        with tempfile.TemporaryDirectory() as directory:
            s, h, p, o = self._files(directory)
            h.write_text(h.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "sealed history hash mismatch"):
                module.process(s, h, p, o)
            self.assertFalse(o.exists())

    def test_reject_false_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            s, h, p, o = self._files(directory)
            data = json.loads(p.read_text())
            data["measurement"]["first_entry_frame"] = 110
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "packet measurement differs"):
                module.process(s, h, p, o)
            self.assertFalse(o.exists())
