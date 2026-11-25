import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("crosswalk_native_review_runner", HERE / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class NativeReviewEntryTests(unittest.TestCase):
    def test_diagnostic_packet_is_rejected_before_capture(self):
        packet = json.loads((HERE / "site_packet.json").read_text())
        with self.assertRaisesRegex(ValueError, "before capture"):
            runner.require_native_site_review(packet)
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            (stage / "construction.json").write_text("{}\n")
            (stage / "site_packet.json").write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "before capture"):
                runner.capture(SimpleNamespace(output_dir=str(stage)), {})

    def test_complete_review_declaration_is_accepted(self):
        packet = json.loads((HERE / "site_packet.json").read_text())
        packet.update(site_review_status="reviewed_native_site", reviewer="source reviewer",
                      district_review_basis="signed original district source review",
                      crosswalk_review_basis="signed original crosswalk marking review",
                      camera_review_basis="four original camera placements reviewed")
        runner.require_native_site_review(packet)
        del packet["camera_review_basis"]
        with self.assertRaisesRegex(ValueError, "before capture"):
            runner.require_native_site_review(packet)


if __name__ == "__main__":
    unittest.main()
