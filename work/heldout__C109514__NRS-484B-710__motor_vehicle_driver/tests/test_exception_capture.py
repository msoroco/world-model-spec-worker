import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "exception_capture.py"
spec = importlib.util.spec_from_file_location("exception_capture", MODULE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class ExceptionCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source_packets").mkdir()
        self.context = {"subject_authorized_emergency": True,
                        "subject_official_business": True}
        for name in ("authorization", "official_business"):
            (self.root / "source_packets" / (name + ".json")).write_text(
                json.dumps({"ego_id": 47, "asserted": True,
                            "source_ref": "dispatch/" + name + "/original"}) + "\n")

    def test_retains_both_independent_actor_bound_packets(self):
        target = capture.retain_exception_source(self.root, 47, self.context)
        source = json.loads(target.read_text())
        self.assertEqual(source["ego_id"], 47)
        self.assertNotEqual(source["authorized_emergency"]["packet_sha256"],
                            source["official_business"]["packet_sha256"])
        self.assertEqual(source["official_business"]["packet"],
                         "source_packets/official_business.json")

    def test_rejects_missing_and_wrong_actor_packet(self):
        (self.root / "source_packets" / "official_business.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing original exception packet"):
            capture.retain_exception_source(self.root, 47, self.context)
        (self.root / "source_packets" / "official_business.json").write_text(
            json.dumps({"ego_id": 48, "asserted": True, "source_ref": "dispatch/duty"}))
        with self.assertRaisesRegex(ValueError, "actor or assertion differs"):
            capture.retain_exception_source(self.root, 47, self.context)

    def test_rejects_changed_assertion_and_existing_output(self):
        self.context["subject_official_business"] = False
        with self.assertRaisesRegex(ValueError, "actor or assertion differs"):
            capture.retain_exception_source(self.root, 47, self.context)
        self.context["subject_official_business"] = True
        capture.retain_exception_source(self.root, 47, self.context)
        with self.assertRaisesRegex(ValueError, "Retain prior"):
            capture.retain_exception_source(self.root, 47, self.context)

    def test_ordinary_subject_needs_no_exception_packet(self):
        context = {"subject_authorized_emergency": False,
                   "subject_official_business": False}
        self.assertIsNone(capture.retain_exception_source(self.root, 47, context))
