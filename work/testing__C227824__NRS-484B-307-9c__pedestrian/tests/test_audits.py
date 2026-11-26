"""Synthetic signal source-shaped audit tests; no physical or legal acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ped_entry import CASES
from comparison_audit import PAIRS, audit as compare
from delivery_audit import ASSIGNMENT, CAMERAS, SOURCES, audit as deliver
from process_recorded_only import process
from reviewed_scene import plan
from runner import check_config
from test_ped_entry import rows, scene

SCRATCH = ROOT.parents[1] / ".runtime-work" / "c227824-audit-tests"


class AuditTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.site = {"reviewed_original_site": True, "source_refs": {}, "scenes": {}}
        for name in SOURCES:
            self.write(name + ".txt", "synthetic source for " + name + "\n")
            self.site["source_refs"][name] = self.ref(name + ".txt")
        for case in CASES:
            item = scene(case)
            for name in SOURCES:
                item[name + "_source_sha256"] = self.site["source_refs"][name]["sha256"]
            self.site["scenes"][case.case_id] = item
        self.write_json("site.json", self.site)
        self.site_ref = self.ref("site.json")

    def write(self, name, text):
        (self.root / name).write_text(text, encoding="utf-8")

    def write_json(self, name, data):
        self.write(name, json.dumps(data, sort_keys=True) + "\n")

    def ref(self, name):
        return {"path": name,
                "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def attempt(self, case):
        case_id = ASSIGNMENT + "__" + case.case_id
        item = self.site["scenes"][case.case_id]
        motion = rows(item, case)
        stem = case.case_id
        self.write_json(stem + "-trace.json", {"case_id": case_id, "frames": motion})
        frame_map = {"source_kind": "original_native_frame_map", "case_id": case_id,
                     "frames": [{"frame": i, "native_frame": 400 + i,
                                 "time_s": i / 20,
                                 "camera_frames": {name: 400 + i for name in CAMERAS}}
                                for i in range(900)]}
        self.write_json(stem + "-frames.json", frame_map)
        videos = {}
        for camera in CAMERAS:
            name = stem + "-" + camera + ".mkv"
            self.write(name, "synthetic video bytes\n")
            videos[camera] = self.ref(name)
        refs = [self.site_ref, self.ref(stem + "-trace.json"),
                self.ref(stem + "-frames.json"), *videos.values()]
        seal = {"source_kind": "original_native_capture_seal", "case_id": case_id,
                "attempt_id": stem + "-attempt", "recording_id": stem + "-recording",
                "sources": {ref["path"]: ref["sha256"] for ref in refs}}
        self.write_json(stem + "-seal.json", seal)
        return {"case_id": case_id, "source_kind": "original_native_attempt",
                "owner_released": True, "native_process_exit_code": 0,
                "attempt_id": seal["attempt_id"], "recording_id": seal["recording_id"],
                "site_ref": self.site_ref, "trace_ref": refs[1],
                "frame_map_ref": refs[2], "video_refs": videos,
                "capture_seal_ref": self.ref(stem + "-seal.json")}

    def video_probe(self, path):
        return {"nb_read_frames": "900", "r_frame_rate": "20/1",
                "width": 960, "height": 540}

    def test_four_source_bound_deliveries_and_three_comparisons(self):
        results = {case.case_id: deliver(self.root, self.attempt(case), self.video_probe)
                   for case in CASES}
        self.assertEqual(len(results), len(CASES))
        self.assertTrue(all(value["other_device_permission_under_nrs_484b_283"] == "unresolved"
                            for value in results.values()))
        for comparison_id, (left, right, _) in PAIRS.items():
            result = compare(comparison_id, self.site["scenes"][left],
                             self.site["scenes"][right], results[left], results[right])
            self.assertTrue(result["requested_difference_isolated"])
            self.assertFalse(result["physical_acceptance"])

    def test_delivery_rejects_unreleased_missing_video_and_stale_trace(self):
        receipt = self.attempt(CASES[0])
        receipt["owner_released"] = False
        with self.assertRaisesRegex(ValueError, "released original"):
            deliver(self.root, receipt, self.video_probe)
        receipt["owner_released"] = True
        receipt["video_refs"].pop("overview")
        with self.assertRaisesRegex(ValueError, "four original camera"):
            deliver(self.root, receipt, self.video_probe)
        receipt = self.attempt(CASES[0])
        (self.root / receipt["trace_ref"]["path"]).write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            deliver(self.root, receipt, self.video_probe)

    def test_comparison_rejects_reused_attempt_and_fixed_signal_change(self):
        left, right = CASES[0], CASES[1]
        left_result = deliver(self.root, self.attempt(left), self.video_probe)
        right_result = deliver(self.root, self.attempt(right), self.video_probe)
        right_result["attempt_id"] = left_result["attempt_id"]
        with self.assertRaisesRegex(ValueError, "reuses original"):
            compare("entry_vs_wait_none", self.site["scenes"][left.case_id],
                    self.site["scenes"][right.case_id], left_result, right_result)
        right_result["attempt_id"] = right.case_id + "-attempt"
        changed = dict(self.site["scenes"][right.case_id], steady_red=False)
        with self.assertRaisesRegex(ValueError, "fixed highway, signal"):
            compare("entry_vs_wait_none", self.site["scenes"][left.case_id],
                    changed, left_result, right_result)

    def test_saved_only_preserves_original_bytes(self):
        case = CASES[0]
        receipt = self.attempt(case)
        output = self.root.parent / (self.root.name + "-derived")
        self.addCleanup(lambda: __import__("shutil").rmtree(output, ignore_errors=True))
        original = receipt["trace_ref"]["sha256"]
        result = process(self.root, self.site_ref, receipt["trace_ref"],
                         receipt["case_id"], output)
        self.assertEqual(result["trace_sha256"], original)
        self.assertEqual(self.ref(receipt["trace_ref"]["path"])["sha256"], original)
        self.assertFalse(result["physical_acceptance"])
        with self.assertRaisesRegex(ValueError, "fresh derived output"):
            process(self.root, self.site_ref, receipt["trace_ref"], receipt["case_id"], output)

    def test_reviewed_native_plan_requires_distinct_signals_and_four_cameras(self):
        self.write("road.xodr", '<OpenDRIVE><road id="21"/></OpenDRIVE>\n')
        self.site["map_ref"] = self.ref("road.xodr")
        self.site["native_signal_assets"] = {"red_signal_actor_id": 10,
                                              "green_arrow_actor_id": 11,
                                              "other_device_actor_id": 12}
        pose = {key: 0.0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
        self.site["camera_profiles"] = {name: {"width": 960, "height": 540,
                                                "pose": pose} for name in CAMERAS}
        self.site["motion_controls"] = {"walk_speed_mps": 1.0}
        self.write_json("site.json", self.site)
        self.site_ref = self.ref("site.json")
        case_id = ASSIGNMENT + "__" + CASES[0].case_id
        scene_plan = plan(self.root, self.site_ref, case_id)
        self.assertEqual(scene_plan["frames"], 900)
        self.assertFalse(scene_plan["physical_acceptance"])
        config = {"law_id": "NRS-484B-307-9c", "cell_id": "C227824",
                  "actor": "pedestrian", "selected_case_id": case_id,
                  "diagnostic_only": True, "rate_hz": 20, "duration_s": 45,
                  "cameras": list(CAMERAS)}
        self.assertTrue(check_config(config))
        self.site["native_signal_assets"]["green_arrow_actor_id"] = 10
        self.write_json("site.json", self.site)
        self.site_ref = self.ref("site.json")
        with self.assertRaisesRegex(ValueError, "distinct Native"):
            plan(self.root, self.site_ref, case_id)
