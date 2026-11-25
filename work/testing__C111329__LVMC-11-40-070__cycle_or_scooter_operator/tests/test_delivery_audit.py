import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit
from analysis import finalize
from native_capture import capture
from native_cameras import CAMERAS
from test_saved_cameras import Bike, World, officer_reader, png
from test_saved_instruction import CASE, SITE


class DeliveryAuditTests(unittest.TestCase):
    def test_diagnostic_join_and_unreviewed_rejection(self):
        scratch = REPO / ".runtime-work/c111329-delivery-test"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            folder = Path(temporary)
            site = dict(SITE, source_kind="original_local_native_site_inventory",
                        map_name="synthetic-test-map", jurisdiction_source="synthetic-test",
                        governed_approach="test-east", device_type="signal",
                        participant_class="human_powered_bicycle",
                        classification_source="reviewed-test bicycle",
                        device_authority_source="synthetic-test",
                        vehicle_applicability_source="synthetic-test")
            site_path = folder / "original-site.json"
            site_path.write_text(json.dumps(site) + "\n")
            site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
            world = World()
            bike = Bike(world)
            device = type("Device", (), {"id": 10})()
            payload = png()
            readers = {name: (lambda frame, value=payload: {"frame": frame, "png_bytes": value})
                       for name in CAMERAS}
            trace = folder / "original-instruction-trace.json"
            capture(world, bike, device, CASE, site, site_sha,
                    lambda _device, _snapshot: "red", officer_reader,
                    trace, readers, {name: (4, 4) for name in CAMERAS})
            trace_sha = hashlib.sha256(trace.read_bytes()).hexdigest()
            (folder / "original-source-hashes.json").write_text(json.dumps({"site": site_sha}) + "\n")
            analysis = finalize(folder, dict(CASE, device_type="signal"))
            self.assertEqual(analysis["measurements"]["observed_device_instruction"]["value"]["state_at_response"], "red")
            self.assertEqual(analysis["measurements"]["original_camera_decode"]["value"]["decoded_images"], 3600)
            diagnostic = audit(dict(CASE, device_type="signal"), site_path, site_sha,
                               trace, trace_sha, diagnostic=True)
            self.assertEqual(diagnostic["source_decode"]["decoded_images"], 3600)
            self.assertFalse(diagnostic["physical_acceptance"])
            with self.assertRaisesRegex(ValueError, "independent physical and pixel review"):
                audit(dict(CASE, device_type="signal"), site_path, site_sha, trace, trace_sha)
            with self.assertRaisesRegex(ValueError, "trace hash mismatch"):
                audit(dict(CASE, device_type="signal"), site_path, site_sha, trace, "0" * 64,
                      diagnostic=True)
            (folder / "original-source-hashes.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: original-source-hashes.json"):
                finalize(folder, dict(CASE, device_type="signal"))


if __name__ == "__main__":
    unittest.main()
