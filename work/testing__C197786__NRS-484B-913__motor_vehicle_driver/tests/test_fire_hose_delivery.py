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
CAPTURE_PATH = MODULE_PATH.parent / "native_capture.py"
capture_spec = importlib.util.spec_from_file_location("native_capture", CAPTURE_PATH)
capture_module = importlib.util.module_from_spec(capture_spec)
sys.modules[capture_spec.name] = capture_module
capture_spec.loader.exec_module(capture_module)
AUDIT_PATH = MODULE_PATH.parent / "delivery_audit.py"
audit_spec = importlib.util.spec_from_file_location("delivery_audit", AUDIT_PATH)
audit_module = importlib.util.module_from_spec(audit_spec)
sys.modules[audit_spec.name] = audit_module
audit_spec.loader.exec_module(audit_module)
ADAPTER_PATH = MODULE_PATH.parent / "native_adapter.py"
adapter_spec = importlib.util.spec_from_file_location("native_adapter", ADAPTER_PATH)
adapter_module = importlib.util.module_from_spec(adapter_spec)
sys.modules[adapter_spec.name] = adapter_module
adapter_spec.loader.exec_module(adapter_module)


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


class FakeAdapter:
    world = FakeWorld()

    def __init__(self):
        self.index = -1
        self.restored = False
        self.stopped = False
        self.destroyed = []

    def provenance(self):
        return "diagnostic_fixture"

    def snapshot_settings(self):
        return "settings"

    def set_synchronous(self, delta):
        assert delta == 0.05

    def hose_transform(self, reviewed):
        return object()

    def spawn_ego(self, vehicle, private_way):
        assert vehicle["human_driver"] is True
        return type("Ego", (), {"id": 5})()

    def set_route(self, ego, points, crossing):
        assert ego.id == 5 and len(points) == 2 and crossing is True

    def start_cameras(self, views):
        assert set(views) == set(capture_module.VIEWS)

    def tick(self):
        self.index += 1
        return {"frame": 100 + self.index, "time_s": self.index / 20}

    def observe(self, snapshot, hose):
        y = 0 if self.index == 1 else -2
        return {"ego_xy": [0, y], "ego_body_corners_xy": [
            [-0.2, y - 0.2], [0.2, y - 0.2], [0.2, y + 0.2], [-0.2, y + 0.2]],
            "ego_actor_id": 5}

    def camera_packets(self, snapshot):
        return {view: {"frame": snapshot["frame"], "time_s": snapshot["time_s"],
                       "sensor_id": view, "png": capture_module.PNG_SIGNATURE + b"diagnostic",
                       "width": 1920 if view == "overview" else 1280,
                       "height": 1080 if view == "overview" else 720}
                for view in capture_module.VIEWS}

    def stop_cameras(self):
        self.stopped = True

    def destroy(self, actor):
        self.destroyed.append(actor.id)

    def restore_settings(self, settings):
        assert settings == "settings"
        self.restored = True


class HoseTests(unittest.TestCase):
    def test_native_route_and_body_geometry(self):
        self.assertAlmostEqual(adapter_module.steering_to((0, 0), 0, (10, 0)), 0)
        self.assertGreater(adapter_module.steering_to((0, 0), 0, (0, 10)), 0)
        transform = type("Transform", (), {
            "location": type("Loc", (), {"x": 1, "y": 2})(),
            "rotation": type("Rot", (), {"yaw": 0})()})()
        extent = type("Ext", (), {"x": 2, "y": 1})()
        self.assertEqual(adapter_module.body_corners(transform, extent),
                         [[-1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [-1.0, 3.0]])

    def test_diagnostic_native_capture_seal_and_cleanup(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as tmp:
            root = Path(tmp)
            reviewed = {}
            original = {
                "private_way": {"owner": "owner", "permitted_access": ["owner"],
                                "ego_route_xy": [[0, -2], [0, 2]]},
                "hose": {"blueprint_id": "static.prop.firehose", "segment_xy": [[-1, 0], [1, 0]],
                         "fire_department_affiliation": True, "protection": "unprotected"},
                "incident": {"purpose": "fire"},
                "official": {"identity": "captain", "in_command": True},
                "consent": {"status": "none"},
                "vehicle": {"ordinary_motor_vehicle": True, "human_driver": True},
            }
            for role, value in original.items():
                source_path = root / (role + ".json")
                source_path.write_text(json.dumps(value, sort_keys=True) + "\n")
                reviewed[role] = dict(value, path=source_path.name,
                                      sha256=hashlib.sha256(source_path.read_bytes()).hexdigest())
            packet_path = root / "reviewed.json"
            packet_path.write_text(json.dumps(reviewed) + "\n")
            config = {"selected_case_id": "case-a", "case": {"planned_hose_crossing": True},
                      "camera_dimensions": {view: ([1920, 1080] if view == "overview"
                                                   else [1280, 720]) for view in capture_module.VIEWS}}
            adapter = FakeAdapter()
            seal = capture_module.capture(adapter, config, reviewed, packet_path, root,
                                          root / "attempt", diagnostic=True, frame_count=3)
            self.assertEqual(seal["body_contact_frames"], [101])
            self.assertTrue(adapter.restored and adapter.stopped)
            self.assertEqual(adapter.destroyed, [5, 9])
            saved = json.loads((root / "attempt" / "saved-packet.json").read_text())
            self.assertEqual(saved["native"]["source_sha256"],
                             hashlib.sha256((root / "attempt" / "frames.jsonl").read_bytes()).hexdigest())
            self.assertEqual(saved["road"]["private_way_owner"], "owner")
            self.assertEqual(len(json.loads((root / "attempt" / "camera-index.json").read_text())), 4)
            audit_module.verify_camera_sources(saved, root / "attempt", expected_frames=3)
            changed_image = root / "attempt" / "cameras" / "overview" / "0001.png"
            changed_image.write_bytes(changed_image.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "camera source PNG/hash mismatch"):
                audit_module.verify_camera_sources(saved, root / "attempt", expected_frames=3)
            class BadCameraAdapter(FakeAdapter):
                def camera_packets(self, snapshot):
                    packets = super().camera_packets(snapshot)
                    packets["overview"]["width"] = 100
                    return packets

            bad_adapter = BadCameraAdapter()
            bad_out = root / "attempt-fail"
            with self.assertRaisesRegex(ValueError, "camera dimensions differ"):
                capture_module.capture(bad_adapter, config, reviewed, packet_path, root,
                                       bad_out, diagnostic=True, frame_count=3)
            self.assertTrue(bad_adapter.restored and bad_adapter.stopped)
            self.assertEqual(bad_adapter.destroyed, [5, 9])
            self.assertFalse((bad_out / "seal.json").exists())

    def test_complete_body_cli_source_join_and_negative_passage(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as tmp:
            root = Path(tmp)
            p = packet()
            for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
                original = {name: value for name, value in p[key].items()
                            if name not in ("source_path", "sha256")}
                path = root / (key + ".json")
                path.write_text(json.dumps(original, sort_keys=True) + "\n")
                p[key].update(source_path=path.name,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest())
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
            seal = {"case_id": "case-a", "frame_count": 900, "rate_hz": 20,
                    "frames_sha256": p["native"]["source_sha256"],
                    "physical_completion": "unreviewed"}
            (root / "seal.json").write_text(json.dumps(seal) + "\n")
            p["native"]["result_sha256"] = hashlib.sha256((root / "seal.json").read_bytes()).hexdigest()
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
            p["native"]["source_sha256"] = hashlib.sha256(rows.read_bytes()).hexdigest()
            p["hose"]["protection"] = "protected"
            packet_path.write_text(json.dumps(p))
            altered = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(altered.returncode, 0)
            self.assertIn("hose original source content mismatch", altered.stderr)
            p["hose"]["protection"] = "unprotected"
            p["native"]["result_sha256"] = "0" * 64
            packet_path.write_text(json.dumps(p))
            unsealed = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(unsealed.returncode, 0)
            self.assertIn("sealed Native result source hash mismatch", unsealed.stderr)

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

    def test_passage_comparison_allows_only_route_variation(self):
        a, b = packet(), packet()
        b["native"]["result_sha256"] = "b" * 64
        b["road"]["ego_route_xy"] = [[2, -1], [2, 1]]
        b["native"]["frames"][0]["ego_xy"] = [2, -1]
        b["native"]["frames"][1]["ego_xy"] = [2, 1]
        a["road"]["ego_route_xy"] = [[0, -1], [0, 1]]
        self.assertEqual(module.compare_saved_hose(a, b, "passage")["comparison_variable"], "passage")
        b["road"]["private_way_owner"] = "changed"
        with self.assertRaisesRegex(ValueError, "fixed road"):
            module.compare_saved_hose(a, b, "passage")


if __name__ == "__main__":
    unittest.main()
