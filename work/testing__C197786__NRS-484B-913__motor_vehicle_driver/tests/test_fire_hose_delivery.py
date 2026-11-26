import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import os


MODULE_PATH = Path(__file__).resolve().parents[1] / "fire_hose_delivery.py"
spec = importlib.util.spec_from_file_location("fire_hose_delivery", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def source(**kwargs):
    return {"source_path": "native/saved.json", "sha256": "a" * 64, **kwargs}


def packet():
    return {
        "case_id": "case-a",
        "native": {"result_sha256": "a" * 64, "frames": [
            {"frame": 10, "elapsed_seconds": 0.5, "ego_xy": [0, -1]},
            {"frame": 11, "elapsed_seconds": 0.55, "ego_xy": [0, 1]}]},
        "hose": source(segment_xy=[[-1, 0], [1, 0]], fire_department_affiliation=True,
                       protection="unprotected"),
        "road": source(private_way_owner="owner-1", permitted_access=["owner-1"]),
        "incident": source(purpose="fire"),
        "command_official": source(identity="captain-1", in_command=True),
        "consent": source(status="none"),
        "vehicle": source(ordinary_motor_vehicle=True, human_driver=True),
    }


class FakeActor:
    id = 9
    type_id = "static.prop.firehose"
    is_alive = True


class FakeLibrary:
    def find(self, key):
        return type("Blueprint", (), {"id": key})() if key == "static.prop.firehose" else None


class FakeWorld:
    def get_blueprint_library(self):
        return FakeLibrary()

    def try_spawn_actor(self, blueprint, transform):
        return FakeActor()

    def get_actor(self, actor_id):
        return FakeActor() if actor_id == 9 else None


class HoseTests(unittest.TestCase):
    def test_complete_body_cli_source_join_and_negative_passage(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as tmp:
            root = Path(tmp)
            (root / "original.txt").write_text("diagnostic source only\n")
            source_hash = hashlib.sha256((root / "original.txt").read_bytes()).hexdigest()
            p = packet()
            for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
                p[key].update(source_path="original.txt", sha256=source_hash)
            p["native"]["frames"] = [
                {"frame": i, "elapsed_seconds": i / 20, "ego_xy": [0, -2],
                 "ego_body_corners_xy": [[-0.2, -2.2], [0.2, -2.2],
                                          [0.2, -1.8], [-0.2, -1.8]]}
                for i in range(900)]
            p["native"]["frames"][500]["ego_body_corners_xy"] = [
                [-0.2, -0.2], [0.2, -0.2], [0.2, 0.2], [-0.2, 0.2]]
            rows = root / "frames.jsonl"
            rows.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                    for row in p["native"]["frames"]))
            p["native"].update(source_path="frames.jsonl",
                               source_sha256=hashlib.sha256(rows.read_bytes()).hexdigest())
            packet_path = root / "packet.json"
            packet_path.write_text(json.dumps(p))
            cmd = [sys.executable, str(MODULE_PATH.parent / "delivery_audit.py"),
                   "--packet", str(packet_path), "--source-root", str(root),
                   "--case-id", "case-a", "--output", str(root / "audit.json"),
                   "--require-complete-body", "--expected-passage", "cross"]
            passed = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertEqual(json.loads((root / "audit.json").read_text())[
                "physical_completion"]["original_body_contact_frames"], [500])
            wrong = subprocess.run(cmd[:-1] + ["avoid"], text=True, capture_output=True)
            self.assertNotEqual(wrong.returncode, 0)
            self.assertIn("original body passage differs", wrong.stderr)
            p["native"]["source_sha256"] = "0" * 64
            packet_path.write_text(json.dumps(p))
            stale = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("Native original frame source hash mismatch", stale.stderr)

    def test_complete_body_footprint_contact_and_avoidance(self):
        p = packet()
        p["native"]["frames"] = [
            {"frame": i, "elapsed_seconds": i / 20, "ego_xy": [0, -2],
             "ego_body_corners_xy": [[-0.2, -2.2], [0.2, -2.2],
                                      [0.2, -1.8], [-0.2, -1.8]]}
            for i in range(900)]
        p["native"]["frames"][500]["ego_body_corners_xy"] = [
            [-0.2, -0.2], [0.2, -0.2], [0.2, 0.2], [-0.2, 0.2]]
        self.assertEqual(module.body_over_hose_frames(p, "case-a"), [500])
        p["native"]["frames"][500]["ego_body_corners_xy"] = [
            [1.8, -0.2], [2.2, -0.2], [2.2, 0.2], [1.8, 0.2]]
        self.assertEqual(module.body_over_hose_frames(p, "case-a"), [])
        del p["native"]["frames"][500]["ego_body_corners_xy"]
        with self.assertRaisesRegex(ValueError, "body footprint missing"):
            module.body_over_hose_frames(p, "case-a")
        p["native"]["frames"].pop()
        with self.assertRaisesRegex(ValueError, "complete original"):
            module.body_over_hose_frames(p, "case-a")

    def test_saved_audit_cli_positive_and_negative(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as tmp:
            root = Path(tmp)
            packet_path = root / "packet.json"
            output_path = root / "audit.json"
            source_file = root / "native" / "saved.json"
            source_file.parent.mkdir()
            source_file.write_text("original saved source bytes\n")
            good_packet = packet()
            for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
                good_packet[key]["sha256"] = hashlib.sha256(source_file.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(good_packet))
            cmd = [sys.executable, str(MODULE_PATH.parent / "delivery_audit.py"),
                   "--packet", str(packet_path), "--source-root", str(root),
                   "--case-id", "case-a", "--output", str(output_path)]
            good = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(output_path.read_text())["observed"]["crossing_frames"], [11])
            bad = copy.deepcopy(good_packet)
            del bad["hose"]["sha256"]
            packet_path.write_text(json.dumps(bad))
            failed = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("hose original source binding missing", failed.stderr)
            bad = copy.deepcopy(good_packet)
            bad["hose"]["sha256"] = "0" * 64
            packet_path.write_text(json.dumps(bad))
            failed = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("hose original source hash mismatch", failed.stderr)
            bad = copy.deepcopy(good_packet)
            bad["hose"]["source_path"] = "../../outside.json"
            packet_path.write_text(json.dumps(bad))
            failed = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("hose original source file missing or outside root", failed.stderr)

    def test_native_spawn_readback(self):
        self.assertEqual(module.construct_hose(FakeWorld(), "static.prop.firehose", object()).id, 9)
        with self.assertRaisesRegex(ValueError, "hose-specific asset id"):
            module.construct_hose(FakeWorld(), "static.prop.cone", object())

    def test_crossing_and_no_crossing(self):
        self.assertEqual(module.inspect_saved_hose(packet(), "case-a")["crossing_frames"], [11])
        other = packet()
        other["native"]["frames"][1]["ego_xy"] = [0, -0.5]
        self.assertEqual(module.inspect_saved_hose(other, "case-a")["crossing_frames"], [])

    def test_missing_sources_rejected(self):
        for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
            p = packet()
            del p[key]["sha256"]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "source binding missing"):
                module.inspect_saved_hose(p, "case-a")

    def test_frame_cadence_rejected(self):
        p = packet()
        p["native"]["frames"][1]["elapsed_seconds"] = 0.60
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            module.inspect_saved_hose(p, "case-a")

    def test_qualifying_context_rejected(self):
        cases = [("hose", "fire_department_affiliation", False),
                 ("road", "private_way_owner", None), ("incident", "purpose", "parade"),
                 ("vehicle", "human_driver", False), ("command_official", "in_command", False)]
        for group, key, value in cases:
            p = packet()
            p[group][key] = value
            with self.subTest(group=group), self.assertRaises(ValueError):
                module.inspect_saved_hose(p, "case-a")

    def test_consent_requires_command_identity_scope_and_timing(self):
        p = packet()
        p["consent"].update(status="given", official_identity="captain-1", scope="cross this hose", frame=9)
        self.assertEqual(module.inspect_saved_hose(p, "case-a")["consent_status"], "given")
        for key in ("official_identity", "scope", "frame"):
            broken = copy.deepcopy(p)
            del broken["consent"][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "consent source"):
                module.inspect_saved_hose(broken, "case-a")

    def test_comparison_rejects_fixed_context_change(self):
        a, b = packet(), packet()
        b["native"]["result_sha256"] = "b" * 64
        b["consent"]["status"] = "withheld"
        self.assertIsNone(module.compare_saved_hose(a, b, "consent")["legal_verdict"])
        b["road"]["private_way_owner"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed road"):
            module.compare_saved_hose(a, b, "consent")

    def test_comparison_rejects_missing_contrast_or_reused_attempt(self):
        a, b = packet(), packet()
        with self.assertRaisesRegex(ValueError, "independent Native"):
            module.compare_saved_hose(a, b, "consent")
        b["native"]["result_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "contrast absent"):
            module.compare_saved_hose(a, b, "consent")


if __name__ == "__main__":
    unittest.main()
