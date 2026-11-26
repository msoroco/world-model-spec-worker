import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import VIEWS, capture
from comparison_audit import audit_pair
from reviewed_site import SITE_ROLES
from saved_audit import audit_saved
from saved_finalizer import finalize
from yield_view import CASES


def fixture(root, case):
    site = {
        "cell_id": "C157964", "actor": "motor_vehicle_driver",
        "yield_sign_present": True, "stop_line_present": False,
        "near_crosswalk_present": False, "officer_controls": case.officer_controls,
        "signal_controls": False, "nearest_view_station_m": 0,
        "physical_reference_station_m": 2,
        "route_xy": [[-20, 0], [-4, 0], [4, 0]],
        "through_spawn_xy": [0, -20],
        "camera_dimensions": {view: [2, 2] for view in VIEWS},
    }
    sources = {}
    for role in SITE_ROLES:
        path = root / (role + ".json")
        path.write_text(json.dumps({"role": role, "source": "diagnostic_fixture"}) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sources[role] = {"path": path.name, "sha256": digest}
        site[role + "_source_sha256"] = digest
    packet = root / "packet.json"
    packet.write_text(json.dumps({"format": "c157964-reviewed-yield-site-v1",
                                  "provenance": "reviewed_original",
                                  "case_id": case.case_id,
                                  "site": site, "sources": sources}, sort_keys=True) + "\n")
    return packet


class FakeAdapter:
    def __init__(self, case, missing_view=False):
        self.case = case
        self.missing_view = missing_view
        self.events = []
        self.i = -1
        image = Image.new("RGB", (2, 2), (30, 60, 90))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        self.png = stream.getvalue()

    def provenance(self):
        return "diagnostic_fixture"

    def snapshot_settings(self):
        self.events.append("snapshot")
        return {"synchronous": False}

    def set_synchronous(self, delta):
        self.events.append(("sync", delta))

    def spawn_vehicle(self, position, role):
        self.events.append(("spawn", role))
        return role

    def set_yield_approach(self, ego, route, reference, policy):
        self.events.append(("approach", policy))

    def set_through_phase(self, through, phase):
        self.events.append(("through", phase))

    def set_officer_control(self, active):
        self.events.append(("officer", active))

    def start_cameras(self, owned, views, dimensions):
        self.events.append("cameras-start")
        assert views == VIEWS and len(owned) == 2

    def tick(self):
        self.i += 1
        return {"frame": 300 + self.i, "time_s": self.i / 20}

    def observe(self, owned, snapshot):
        i = self.i
        return {
            "ego_id": owned[0], "through_id": owned[1],
            "ego_speed_mps": 8 if i < 80 else
            (0 if self.case.approach_policy == "stop" and i < 110 else 4),
            "through_center_station_m": 12 - i * .01,
            "through_min_vertex_station_m": 9 - i * .01,
            "ego_leading_station_m": -2 if i < 120 else 3,
            "through_phase": self.case.through_state,
            "ego_across_or_within": i >= 120,
            "officer_controls": self.case.officer_controls,
            "signal_controls": False, "stop_line_present": False,
            "near_crosswalk_present": False,
            "sight_observation": {"clear_to_m": 30},
            "body_vertices": {"ego": [[0, 0]] * 8, "through": [[1, 1]] * 8},
            "control_readback": {"requested": self.case.approach_policy},
        }

    def camera_packets(self, snapshot):
        result = {view: {"frame": snapshot["frame"],
                         "time_s": snapshot["time_s"],
                         "sensor_id": "sensor-" + view,
                         "width": 2, "height": 2, "png": self.png}
                  for view in VIEWS}
        if self.missing_view and self.i == 3:
            del result["driver_reference"]
        return result

    def stop_cameras(self):
        self.events.append("cameras-stop")

    def destroy(self, actor):
        self.events.append(("destroy", actor))

    def restore_settings(self, settings):
        self.events.append("restore")


class CaptureTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_four_exact_diagnostic_attempts(self):
        attempts = {}
        for case in CASES:
            with self.subTest(case=case.case_id):
                source = self.root / case.case_id
                source.mkdir()
                packet = fixture(source, case)
                adapter = FakeAdapter(case)
                out = self.root / (case.case_id + "-attempt")
                seal = capture(adapter, packet, source, out, case, diagnostic=True)
                self.assertTrue(seal["diagnostic_fixture"])
                self.assertEqual(seal["frame_count"], 900)
                self.assertEqual(json.loads((out / "measurement.json").read_text())
                                 ["first_physical_reference_crossing_frame"], 420)
                self.assertEqual(sum(len(x) for x in json.loads(
                    (out / "camera-index.json").read_text()).values()), 3600)
                self.assertEqual(adapter.events[-4:],
                                 ["cameras-stop", ("destroy", "through"),
                                  ("destroy", "ego"), "restore"])
                audit = audit_saved(out, case, allow_diagnostic=True)
                attempts[case.case_id] = out
                self.assertEqual(audit["decoded_camera_frames"], 3600)
                self.assertEqual(audit["physical_completion"], "unverified")
                with self.assertRaisesRegex(ValueError, "diagnostic attempt cannot be original delivery"):
                    audit_saved(out, case)
                with self.assertRaisesRegex(ValueError, "independent reviewed site hash differs"):
                    audit_saved(out, case, allow_diagnostic=True,
                                expected_site_packet_sha256="0" * 64)
        for comparison_id, right_case in (("slow_vs_stop", CASES[1]),
                                          ("through_phase", CASES[2]),
                                          ("officer_exception", CASES[3])):
            with self.subTest(comparison=comparison_id):
                report = audit_pair(comparison_id, attempts[CASES[0].case_id],
                                    attempts[right_case.case_id], allow_diagnostic=True)
                self.assertEqual(report["decoded_camera_frames"], 7200)
                self.assertEqual(report["physical_difference"], "unverified")
        saved_output = self.root / "saved-finalization.json"
        final = finalize(attempts[CASES[0].case_id], saved_output,
                         CASES[0], allow_diagnostic=True)
        self.assertFalse(final["original_attempt_modified"])
        self.assertEqual(final["source_audit"]["decoded_camera_frames"], 3600)
        with self.assertRaisesRegex(ValueError, "output already exists"):
            finalize(attempts[CASES[0].case_id], saved_output,
                     CASES[0], allow_diagnostic=True)
        camera = attempts[CASES[0].case_id] / "cameras/overview/0000.png"
        camera.write_bytes(camera.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "saved camera bytes changed"):
            audit_saved(attempts[CASES[0].case_id], CASES[0], allow_diagnostic=True)

    def test_missing_camera_fails_without_seal_and_restores(self):
        case = CASES[0]
        source = self.root / "source"
        source.mkdir()
        packet = fixture(source, case)
        adapter = FakeAdapter(case, missing_view=True)
        out = self.root / "bad-attempt"
        with self.assertRaisesRegex(ValueError, "four original camera packets missing"):
            capture(adapter, packet, source, out, case, diagnostic=True)
        self.assertFalse((out / "seal.json").exists())
        self.assertEqual(adapter.events[-1], "restore")

    def test_original_mode_rejects_diagnostic_adapter_before_world_mutation(self):
        case = CASES[0]
        source = self.root / "source"
        source.mkdir()
        packet = fixture(source, case)
        adapter = FakeAdapter(case)
        with self.assertRaisesRegex(ValueError, "original Native adapter provenance missing"):
            capture(adapter, packet, source, self.root / "attempt", case)
        self.assertEqual(adapter.events, [])


if __name__ == "__main__":
    unittest.main()
