"""Synthetic sealed-source diagnostics never establish Native acceptance."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "independent"))
from parking_cameras import CAMERAS
from parking_delivery_audit import ORIGINALS, audit_attempt, verify_native_map_binding
from delivery_audit import verify_scene_binding
from parking_pose import construct
from parking_scene import build
from source_review import validate
from test_parking_finalizer import write_history
from test_source_review import fixture


def put(path, value):
    Path(path).write_text(json.dumps(value) + "\n")


def rows(path, values):
    Path(path).write_text("".join(json.dumps(value) + "\n" for value in values))


def diagnostic(root):
    root = Path(root)
    packet, data = fixture(root)
    scene = build(packet, root, "park_parallel_lawful")
    pose = construct(validate(packet, source_root=root), "park_parallel_lawful")
    history, _ = write_history(root, pose, [1, 0, 0])
    history.rename(root / "parking-history.jsonl")
    (root / "road.xodr").write_text("synthetic map\n")
    (root / "carla_recorder.log").write_text("synthetic recorder\n")
    (root / "runner.py").write_text("# synthetic diagnostic only\n")
    put(root / "construction.json", scene)
    original = [json.loads(line) for line in (root / "parking-history.jsonl").read_text().splitlines()]
    rows(root / "video_frames.jsonl", [{"video_frame": i, "carla_frame": i, "time_s": i * .05}
                                     for i in range(3)])
    rows(root / "camera-frame-map.jsonl", [{"frame": i, "time_s": i * .05,
                                             "camera_names": list(CAMERAS)} for i in range(3)])
    rows(root / "trace.jsonl", [{"frame": i, "time_s": i * .05} for i in range(3)])
    rows(root / "controller-history.jsonl", [{"frame": i, "time_s": i * .05} for i in range(3)])
    for name in CAMERAS:
        (root / (name + ".mkv")).write_text("synthetic video placeholder\n")
    source_names = [item["path"] for item in data["sources"].values()]
    names = [*ORIGINALS, *source_names]
    sealed = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    put(root / "capture-seal.json",
        {"format": "worker-sealed-capture", "provenance_kind": "diagnostic",
         "diagnostic_fixture": True, "frames": 3,
         "events": ["capture_finished", "encoders_closed", "restoration_verified"],
         "restoration": {"restored": True},
         "encoder_exit_codes": {name: 0 for name in CAMERAS}, "sources": sealed})
    return original


class ParkingDeliveryAuditTests(unittest.TestCase):
    def test_reviewed_map_requires_exact_original_hash_and_pipeline_name(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "capture").mkdir()
            (root / "road.xodr").write_text("original authored map\n")
            put(root / "capture/manifest.json", {"map": "reviewed-map"})
            digest = lambda path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            hashes = {name: digest(name) for name in ("road.xodr", "capture/manifest.json")}
            packet = {"context": {"native_map_name": "reviewed-map",
                                  "native_opendrive_sha256": hashes["road.xodr"]}}
            verify_native_map_binding(root, packet, hashes)
            packet["context"]["native_map_name"] = "other-map"
            with self.assertRaisesRegex(ValueError, "pipeline map name differs"):
                verify_native_map_binding(root, packet, hashes)
            packet["context"]["native_map_name"] = "reviewed-map"
            (root / "road.xodr").write_text("substituted map\n")
            with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
                verify_native_map_binding(root, packet, hashes)

    def test_synthetic_source_join_and_native_rejection(self):
        with TemporaryDirectory() as tmp:
            diagnostic(tmp)
            result = audit_attempt(tmp, diagnostic=True, decoder=lambda path: 3)
            self.assertEqual(result["case_id"], ROOT.name + "__park_parallel_lawful")
            self.assertEqual(len(result["saved_observations"]["observations"]), 3)
            self.assertFalse(result["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "original Native acquisition required"):
                audit_attempt(tmp, decoder=lambda path: 3)

    def test_changed_source_frame_and_decode_count_rejected(self):
        with TemporaryDirectory() as tmp:
            diagnostic(tmp)
            with self.assertRaisesRegex(ValueError, "decoded original camera frame count"):
                audit_attempt(tmp, diagnostic=True, decoder=lambda path: 2)
            (Path(tmp) / "parking-history.jsonl").write_text("changed")
            with self.assertRaisesRegex(ValueError, "sealed original source missing or changed"):
                audit_attempt(tmp, diagnostic=True, decoder=lambda path: 3)
        with TemporaryDirectory() as tmp:
            diagnostic(tmp)
            path = Path(tmp) / "camera-frame-map.jsonl"
            data = [json.loads(line) for line in path.read_text().splitlines()]
            data[1]["frame"] = 9
            rows(path, data)
            seal_path = Path(tmp) / "capture-seal.json"
            seal = json.loads(seal_path.read_text())
            seal["sources"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            put(seal_path, seal)
            with self.assertRaisesRegex(ValueError, "frame join incomplete"):
                audit_attempt(tmp, diagnostic=True, decoder=lambda path: 3)

    def test_resealed_backward_timestamp_rejected(self):
        with TemporaryDirectory() as tmp:
            diagnostic(tmp)
            root = Path(tmp)
            for name in ("video_frames.jsonl", "camera-frame-map.jsonl",
                         "parking-history.jsonl", "trace.jsonl", "controller-history.jsonl"):
                path = root / name
                data = [json.loads(line) for line in path.read_text().splitlines()]
                data[2]["time_s"] = 0.01
                rows(path, data)
                seal_path = root / "capture-seal.json"
                seal = json.loads(seal_path.read_text())
                seal["sources"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
                put(seal_path, seal)
            with self.assertRaisesRegex(ValueError, "frame join incomplete"):
                audit_attempt(root, diagnostic=True, decoder=lambda path: 3)

    def test_independent_original_scene_must_be_sealed_and_match_construction(self):
        with TemporaryDirectory() as tmp:
            diagnostic(tmp)
            root = Path(tmp)
            scene = json.loads((root / "construction.json").read_text())
            put(root / "scene.json", scene)
            with self.assertRaisesRegex(ValueError, "original scene absent from sealed Native capture"):
                verify_scene_binding(root)
            seal_path = root / "capture-seal.json"
            seal = json.loads(seal_path.read_text())
            seal["sources"]["scene.json"] = hashlib.sha256((root / "scene.json").read_bytes()).hexdigest()
            put(seal_path, seal)
            verify_scene_binding(root)
            scene["activity_request"] = "standing"
            put(root / "scene.json", scene)
            seal["sources"]["scene.json"] = hashlib.sha256((root / "scene.json").read_bytes()).hexdigest()
            put(seal_path, seal)
            with self.assertRaisesRegex(ValueError, "sealed scene and construction differ: activity_request"):
                verify_scene_binding(root)


if __name__ == "__main__":
    unittest.main()
