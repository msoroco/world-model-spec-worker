import hashlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_site_contract import packet

spec = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
audit_spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)


class Adapter:
    def __init__(self, source, *, drift=False, missing_camera=False,
                 missing_act=False, changed_map=False, start_time_s=0.0):
        self.source = source
        self.index = -1
        self.drift = drift
        self.missing_camera = missing_camera
        self.missing_act = missing_act
        self.changed_map = changed_map
        self.start_time_s = start_time_s
        self.commands = []
        self.cleaned = False
        stream = io.BytesIO()
        Image.new("RGB", (2, 2), (1, 2, 3)).save(stream, format="PNG")
        self.image = stream.getvalue()

    def map_sha256(self):
        if self.changed_map and self.index >= 0:
            return "0" * 64
        return self.source["map_sha256"]

    def configure_site(self, source, site):
        self.site = site

    def spawn_parked(self, source):
        return "parked"

    def spawn_passing(self, source, variant):
        self.variant = variant
        return "passing"

    def spawn_driver(self, source):
        return "driver"

    def attach_cameras(self, parked, cameras):
        self.cameras = cameras

    def command_act(self, driver, parked, act, side):
        self.commands.append((driver, parked, act, side))

    def tick(self):
        self.index += 1
        return self.index, self.start_time_s + self.index / 20 + (0.001 * self.index if self.drift else 0)

    def observe(self, frame_id, driver, parked, passing):
        active = frame_id == 201 and not self.missing_act
        return {"selected_driver_id": driver, "observed_act":
                self.site["selected_act"] if active else "none",
                "act_side": self.site["selected_door_side"] if active else None,
                "passing_center_xy": [frame_id / 20, 4],
                "passing_speed_mps": 1,
                "act_envelope_xy": [[1, 2], [2, 2]],
                "passing_body_xy": [[1, 4], [2, 4]],
                "passing_response": {"brake": 0, "acceleration_mps2": 0}}

    def camera_frame(self, view, frame_id):
        if self.missing_camera and view == "rear" and frame_id == 3:
            return None
        return self.image

    def cleanup(self):
        self.cleaned = True


class NativeCaptureTests(unittest.TestCase):
    def run_case(self, *, case_key="board_near", drift=False, missing_camera=False,
                 missing_act=False, changed_map=False, start_time_s=0.0):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = packet()
            survey = base / "survey.json"
            survey.write_text(json.dumps(source))
            digest = hashlib.sha256(survey.read_bytes()).hexdigest()
            adapter = Adapter(source, drift=drift, missing_camera=missing_camera,
                              missing_act=missing_act, changed_map=changed_map,
                              start_time_s=start_time_s)
            output = base / "out"
            case = ROOT.name + "__" + case_key
            if drift or missing_camera or missing_act or changed_map:
                with self.assertRaises(ValueError):
                    native.capture(adapter, survey_path=survey, survey_sha256=digest,
                                   case_id=case, output=output)
                self.assertTrue(adapter.cleaned)
                self.assertFalse((output / "native-trace.json").exists())
                return
            receipt = native.capture(adapter, survey_path=survey, survey_sha256=digest,
                                     case_id=case, output=output)
            trace = json.loads((output / "native-trace.json").read_text())
            self.assertEqual(receipt["frame_count"], 900)
            self.assertEqual(receipt["camera_frame_count"], 3600)
            self.assertEqual(len(trace["frames"]), 900)
            self.assertEqual(trace["frames"][0]["sim_time_s"], 0.0)
            self.assertEqual(trace["frames"][0]["native_elapsed_time_s"], start_time_s)
            self.assertEqual(len(list((output / "cameras").rglob("*.png"))), 3600)
            expected_act = native.CASE_ACTIONS[case_key][0]
            expected_side = "right" if case_key == "open_far_side" else "left"
            self.assertEqual(adapter.commands, [("driver", "parked", expected_act,
                                                 expected_side)])
            checked = audit.audit_saved(output, trace_sha256=receipt["original_trace_sha256"],
                                        case_id=case, act=expected_act, side=expected_side,
                                        expected_dimensions={view: (2, 2) for view in native.CAMERAS},
                                        survey_path=survey, survey_sha256=digest)
            self.assertEqual(checked["decoded_camera_frames"], 3600)
            self.assertTrue(checked["original_site_binding"]["original_site_binding_checked"])
            for field, value in (("map_sha256", "wrong-map"),
                                 ("driver_id", "wrong-driver"),
                                 ("traffic_route_id", "wrong-route")):
                altered = copy.deepcopy(trace)
                altered["fixed_context"][field] = value
                with self.assertRaisesRegex(ValueError, "differs from original"):
                    audit.audit_site_binding(altered, survey_path=survey,
                                             survey_sha256=digest, case_id=case,
                                             act=expected_act, side=expected_side)
            altered = copy.deepcopy(trace)
            altered["parked_center_xy"][0] += 1
            with self.assertRaisesRegex(ValueError, "parked pose differs"):
                audit.audit_site_binding(altered, survey_path=survey,
                                         survey_sha256=digest, case_id=case,
                                         act=expected_act, side=expected_side)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit.audit_site_binding(trace, survey_path=survey,
                                         survey_sha256="0" * 64, case_id=case,
                                         act=expected_act, side=expected_side)
            self.assertEqual(checked["act_on_closest_side"], case_key != "open_far_side")
            dimensions = base / "dimensions.json"
            dimensions.write_text(json.dumps({view: [2, 2] for view in native.CAMERAS}))
            command = [sys.executable, str(ROOT / "process_saved.py"), "--attempt", str(output),
                       "--trace-sha256", receipt["original_trace_sha256"],
                       "--survey", str(survey), "--survey-sha256", digest,
                       "--case-id", case, "--act", expected_act, "--side", expected_side,
                       "--dimensions", str(dimensions), "--output", str(base / "checked.json")]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads((base / "checked.json").read_text())["decoded_camera_frames"], 3600)
            replacement = io.BytesIO()
            Image.new("RGB", (2, 2), (9, 9, 9)).save(replacement, format="PNG")
            (output / "cameras" / "rear" / "000001.png").write_bytes(replacement.getvalue())
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            with self.assertRaisesRegex(ValueError, "differ from sealed"):
                audit.audit_saved(output, trace_sha256=receipt["original_trace_sha256"],
                                  case_id=case, act=expected_act, side=expected_side,
                                  expected_dimensions={view: (2, 2) for view in native.CAMERAS})
            (output / "cameras" / "rear" / "000001.png").write_bytes(b"corrupt")
            with self.assertRaises(Exception):
                audit.audit_saved(output, trace_sha256=receipt["original_trace_sha256"],
                                  case_id=case, act=expected_act, side=expected_side,
                                  expected_dimensions={view: (2, 2) for view in native.CAMERAS})
            self.assertTrue(adapter.cleaned)

    def test_complete_original_capture(self):
        for key in native.CASE_ACTIONS:
            with self.subTest(key=key):
                self.run_case(case_key=key)

    def test_clock_drift_rejected_with_cleanup(self):
        self.run_case(drift=True)

    def test_nonzero_native_clock_keeps_episode_time_axis(self):
        self.run_case(start_time_s=1234.5)

    def test_missing_camera_rejected_with_cleanup(self):
        self.run_case(missing_camera=True)

    def test_unobserved_act_rejected_before_sealing(self):
        self.run_case(missing_act=True)

    def test_map_change_rejected_before_sealing(self):
        self.run_case(changed_map=True)


if __name__ == "__main__":
    unittest.main()
