import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import ASSIGNMENT, EXPECTED_FRAMES, VIEWS, audit, decode_original_cameras
from comparison_audit import audit_saved


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mode = "low_beam"
        self.case_id = ASSIGNMENT + "__" + self.mode
        rows = []
        maps = []
        for i in range(EXPECTED_FRAMES):
            frame = 100 + i
            rows.append({"frame": frame, "time_s": round(i * .05, 8),
                         "speed_mps": 0.0, "parking_brake": True,
                         "footprint_inside_reviewed_parking_polygon": True,
                         "light_state_bits": 3, "actor_id": 17})
            maps.append({"frame": frame, **{v + "_source_frame": frame for v in VIEWS}})
        for name, content in (("actor-state.jsonl", rows), ("camera-frame-map.jsonl", maps)):
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in content))
        receipt = {"format": "parked-headlamp-native-source-v1", "case_id": self.case_id,
                   "requested_mode": self.mode, "physical_acceptance_claimed": False,
                   "diagnostic_site": True, "frame_count": EXPECTED_FRAMES,
                   "commanded": {"requested_mode": self.mode, "requested_bits": 3,
                                 "readback_bits": 3},
                   "light_masks": {"low_beam": 2, "high_beam": 4},
                   "source_hashes": {name: sha(self.root / name) for name in
                                     ("actor-state.jsonl", "camera-frame-map.jsonl")}}
        (self.root / "native-receipt.json").write_text(json.dumps(receipt))
        self.manifest = {"format": "parked-headlamp-acquisition-v1", "case_id": self.case_id,
                         "acquisition_kind": "cpu_fixture", "physical_acceptance_claimed": False,
                         "native_receipt": {"path": "native-receipt.json",
                                            "sha256": sha(self.root / "native-receipt.json")},
                         "media": {}}
        for view in VIEWS:
            path = self.root / (view + ".txt")
            path.write_text("diagnostic original-media stand-in for " + view + "\n")
            self.manifest["media"][view] = {"path": path.name, "sha256": sha(path),
                                            "source_frame_count": EXPECTED_FRAMES}
        self.save_manifest()

    def save_manifest(self):
        (self.root / "acquisition.json").write_text(json.dumps(self.manifest))

    def run_audit(self, **kw):
        return audit(self.root, self.root / "acquisition.json", case_id=self.case_id, **kw)

    def test_positive_diagnostic_integrity_and_delivery_rejection(self):
        proof = self.run_audit(allow_diagnostic=True)
        self.assertTrue(proof["saved_source_integrity_passed"])
        self.assertFalse(proof["emission_and_aim_reviewed"])
        with self.assertRaisesRegex(ValueError, "Native acquisition"):
            self.run_audit()

    def test_tampered_media_and_attempt_escape_rejected(self):
        (self.root / "overview.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.run_audit(allow_diagnostic=True)
        self.manifest["media"]["overview"]["path"] = "../escape.txt"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "escapes attempt"):
            self.run_audit(allow_diagnostic=True)

    def test_source_duration_camera_and_case_mismatch_rejected(self):
        self.manifest["case_id"] = ASSIGNMENT + "__high_beam"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "case identity"):
            self.run_audit(allow_diagnostic=True)
        self.manifest["case_id"] = self.case_id
        self.manifest["media"]["overview"]["source_frame_count"] = 899
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "frame count"):
            self.run_audit(allow_diagnostic=True)
        self.manifest["media"]["overview"]["source_frame_count"] = EXPECTED_FRAMES
        self.save_manifest()
        rows = [json.loads(line) for line in (self.root / "camera-frame-map.jsonl").read_text().splitlines()]
        rows[1]["overview_source_frame"] = rows[0]["frame"]
        (self.root / "camera-frame-map.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt = json.loads((self.root / "native-receipt.json").read_text())
        receipt["source_hashes"]["camera-frame-map.jsonl"] = sha(self.root / "camera-frame-map.jsonl")
        (self.root / "native-receipt.json").write_text(json.dumps(receipt))
        self.manifest["native_receipt"]["sha256"] = sha(self.root / "native-receipt.json")
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "stale original camera"):
            self.run_audit(allow_diagnostic=True)

    def test_three_attempt_comparison_recomputes_fixed_sources(self):
        keys = ("reviewed_map_sha256", "parking_polygon_sha256", "vehicle_blueprint_sha256",
                "weather_sha256", "camera_policy_sha256", "parking_controller_sha256")
        attempts, manifests, packets = {}, {}, {}
        for mode, bits in (("unlit", 0), ("low_beam", 3), ("high_beam", 5)):
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name)
            shutil.copytree(self.root, root, dirs_exist_ok=True)
            case_id = ASSIGNMENT + "__" + mode
            states = [json.loads(line) for line in (root / "actor-state.jsonl").read_text().splitlines()]
            for state in states:
                state["light_state_bits"] = bits
            (root / "actor-state.jsonl").write_text("".join(json.dumps(row) + "\n" for row in states))
            receipt = json.loads((root / "native-receipt.json").read_text())
            receipt["case_id"] = case_id
            receipt["requested_mode"] = mode
            receipt["commanded"]["requested_mode"] = mode
            receipt["source_hashes"]["actor-state.jsonl"] = sha(root / "actor-state.jsonl")
            (root / "native-receipt.json").write_text(json.dumps(receipt))
            manifest = json.loads((root / "acquisition.json").read_text())
            manifest["case_id"] = case_id
            manifest["native_receipt"]["sha256"] = sha(root / "native-receipt.json")
            (root / "acquisition.json").write_text(json.dumps(manifest))
            sources = {}
            for key in keys:
                source = root / (key + ".txt")
                source.write_text("shared exact source for " + key + "\n")
                sources[key] = {"path": source.name, "sha256": sha(source)}
            packet = root / "fixed-packet.json"
            packet.write_text(json.dumps({"format": "parked-headlamp-fixed-sources-v1",
                                          "case_id": case_id, "sources": sources}))
            attempts[mode], manifests[mode], packets[mode] = root, root / "acquisition.json", packet
        proof = audit_saved(attempts, manifests, packets, allow_diagnostic=True)
        self.assertTrue(proof["saved_source_integrity_passed"])
        self.assertTrue(proof["readback_differences_confirmed"])
        self.assertFalse(proof["physical_acceptance_claimed"])
        weather = attempts["high_beam"] / "weather_sha256.txt"
        weather.write_text("different actual weather source\n")
        packet = json.loads(packets["high_beam"].read_text())
        packet["sources"]["weather_sha256"]["sha256"] = sha(weather)
        packets["high_beam"].write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "fixed condition changed"):
            audit_saved(attempts, manifests, packets, allow_diagnostic=True)
        weather.unlink()
        with self.assertRaisesRegex(ValueError, "missing or escapes"):
            audit_saved(attempts, manifests, packets, allow_diagnostic=True)

    def test_original_png_archives_join_native_frame_map(self):
        rows = [{"frame": frame, **{view + "_source_frame": frame for view in VIEWS}}
                for frame in (100, 101)]
        paths = {}
        for view in VIEWS:
            path = self.root / (view + ".zip")
            with zipfile.ZipFile(path, "w") as archive:
                for frame in (100, 101):
                    stream = io.BytesIO()
                    Image.new("RGB", (8, 6), "red").save(stream, format="PNG")
                    archive.writestr(f"{frame}.png", stream.getvalue())
            paths[view] = path
        sizes = {view: (8, 6) for view in VIEWS}
        self.assertEqual(decode_original_cameras(paths, rows, dimensions=sizes),
                         {view: 2 for view in VIEWS})
        rows[1]["overview_source_frame"] = 100
        with self.assertRaisesRegex(ValueError, "frame map differs"):
            decode_original_cameras(paths, rows, dimensions=sizes)
        rows[1]["overview_source_frame"] = 101
        sizes["overview"] = (9, 6)
        with self.assertRaisesRegex(ValueError, "PNG profile differs"):
            decode_original_cameras(paths, rows, dimensions=sizes)


if __name__ == "__main__":
    unittest.main()
