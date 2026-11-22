import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import decode_original_videos, verify_frame_joins, verify_saved_sources
from native_capture import CAMERA_SPECS


class DeliveryAuditTests(unittest.TestCase):
    def sources(self):
        scene = json.loads((ROOT/"cases/roadway_walk/scene.json").read_text())
        mapping = []
        bodies = []
        traces = []
        joins = []
        for index in range(3):
            frame = index+10
            time_s = index/20
            x = 2+.06*index
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s})
            bodies.append({"case_id": scene["case_id"], "actor_id": 17,
                           "frame": frame, "time_s": time_s,
                           "source_kind": "original_native_world_vertices",
                           "body_xy_m": [[x-.2, 1.25], [x+.2, 1.25],
                                         [x+.2, 1.75], [x-.2, 1.75]]})
            traces.append({"actor_id": 17, "frame": frame,
                           "time_s": time_s, "position_m": [x, 1.5, .1]})
            joins.append({"case_id": scene["case_id"], "walker_actor_id": 17,
                          "frame": frame, "time_s": time_s,
                          "cameras": {name: {"frame": frame, "width": width,
                               "height": height, "pixel_format": "bgra",
                               "bytes": width*height*4}
                                      for name, (width, height) in CAMERA_SPECS.items()}})
        return scene, mapping, bodies, traces, joins

    def test_original_source_join_positive_and_missing_rows(self):
        groups = self.sources()
        result = verify_frame_joins(*groups)
        self.assertEqual(result["frame_count"], 3)
        self.assertTrue(result["time_join_passed"])
        self.assertFalse(result["physical_acceptance_claimed"])
        with self.assertRaisesRegex(ValueError, "missing rows"):
            verify_frame_joins(*groups[:-1], groups[-1][:-1])

    def test_resealed_identity_timestamp_and_camera_changes_rejected(self):
        for kind in ("body_actor", "trace_time", "trace_position", "camera_frame", "map_frame"):
            with self.subTest(kind=kind):
                scene, mapping, bodies, traces, joins = copy.deepcopy(self.sources())
                if kind == "body_actor": bodies[1]["actor_id"] = 19
                if kind == "trace_time": traces[1]["time_s"] += .01
                if kind == "trace_position": traces[1]["position_m"][1] = 3.5
                if kind == "camera_frame": joins[1]["cameras"]["approach"]["frame"] = 12
                if kind == "map_frame": mapping[1]["native_frame"] = 12
                with self.assertRaises(ValueError):
                    verify_frame_joins(scene, mapping, bodies, traces, joins)

    def test_saved_audit_rejects_absent_capture_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                verify_saved_sources(directory)
            with self.assertRaises(FileNotFoundError):
                decode_original_videos(directory)

    def test_synthetic_unit_seal_checks_source_bytes_without_pixel_claim(self):
        scene, mapping, bodies, traces, joins = self.sources()
        scratch = ROOT.parents[1]/".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            attempt = Path(directory)
            (attempt/"scene.json").write_text(json.dumps(scene))
            source = (ROOT/"candidate-corridor.xodr").read_bytes()
            (attempt/"candidate-corridor.xodr").write_bytes(source)
            (attempt/"road.xodr").write_bytes(source)
            for name, values in (("video_frames.jsonl", mapping),
                                 ("walker-body-history.jsonl", bodies),
                                 ("trace.jsonl", traces),
                                 ("camera-frame-joins.jsonl", joins)):
                (attempt/name).write_text("".join(json.dumps(value)+"\n" for value in values))
            for name in CAMERA_SPECS:
                (attempt/(name+".mkv")).write_bytes(b"unit-test-media-placeholder")
            (attempt/"acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": False}))
            names = ["scene.json", "candidate-corridor.xodr", "road.xodr",
                     "video_frames.jsonl", "walker-body-history.jsonl", "trace.jsonl",
                     "camera-frame-joins.jsonl", *(name+".mkv" for name in CAMERA_SPECS)]
            sha = lambda path: hashlib.sha256((attempt/path).read_bytes()).hexdigest()
            (attempt/"acquisition.json").write_text(json.dumps({
                name: {"kind": "original_native", "sha256": sha(name)} for name in names}))
            inventory = {path.name: sha(path.name) for path in attempt.iterdir() if path.is_file()}
            digest = hashlib.sha256(json.dumps(inventory, sort_keys=True,
                        separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            (attempt/"capture-seal.json").write_text(json.dumps({
                "format": "worker-sealed-capture", "provenance_kind": "native",
                "diagnostic_fixture": False, "restoration": {"restored": True},
                "encoder_exit_codes": {name: 0 for name in CAMERA_SPECS},
                "sources": inventory, "source_digest": digest, "frames": 3}))
            verified = verify_saved_sources(attempt)
            self.assertTrue(verified["original_source_integrity_passed"])
            self.assertFalse(verified["full_video_decode_passed"])
            (attempt/"approach.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                verify_saved_sources(attempt)
