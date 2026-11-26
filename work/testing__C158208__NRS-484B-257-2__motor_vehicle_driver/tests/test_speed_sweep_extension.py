import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from speed_sweep_runner import prepare
from speed_sweep_comparison import compare
from test_yield_site import SOURCE_NAMES, World
from native_capture import capture


class SpeedSweepExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        sources = {}
        for name in SOURCE_NAMES:
            source = root / (name + ".txt")
            source.write_text("synthetic only " + name + "\n")
            sources[name] = {"path": str(source),
                             "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        def spawn(x):
            return {"blueprint_id": "vehicle.test", "source_citation": "fixture",
                    "route_source_citation": "fixture", "location_xyz_m": [x, 0, 0],
                    "rotation_rpy_deg": [0, 0, 0],
                    "route_points_xyz_m": [[x, 0, 0], [x + 10, 0, 0]],
                    "initial_station_m": x}
        self.packet = {"format": "c158208-reviewed-native-site-v1",
                       "cell_id": "C158208", "law_id": "NRS-484B-257-2",
                       "actor": "motor_vehicle_driver", "sources": sources,
                       "non_through_highway": True, "ego_yield_sign_present": True,
                       "other_obligated_to_stop_or_yield": False,
                       "officer_controls": False, "signal_controls": False,
                       "entrances": [{"id": "west", "control": "yield", "reviewed_source": "fixture"},
                                     {"id": "north", "control": "none", "reviewed_source": "fixture"}],
                       "ego_entrance_id": "west", "other_entrance_id": "north",
                       "stop_reference_station_m": 0, "intersection_entry_station_m": 4,
                       "intersection_polygon_source": "fixture",
                       "ego_route_continuity_review": True,
                       "other_route_continuity_review": True,
                       "spawn_plan": {"ego": spawn(-8), "other": spawn(1)}}
        self.site = root / "site.json"

    def test_three_exact_configs_preserve_fixed_conditions(self):
        extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
        self.assertEqual([(row["target_bin"], row["requested_station_m"])
                          for row in extension["station_selected_bindings"]],
                         [("below", 0), ("inside", 8), ("above", 35)])
        configs = []
        for row in extension["cases"]:
            self.packet["case_id"] = row["case_id"]
            self.site.write_text(json.dumps(self.packet) + "\n")
            config = prepare(row["case_id"], self.site)
            self.assertEqual(config["case"]["draft_variables"], row["draft_variables"])
            self.assertEqual(config["frame_count"], 900)
            self.assertEqual(len(config["cameras"]), 4)
            configs.append(config)
        fixed = [dict(config["case"]["draft_variables"]) for config in configs]
        for row in fixed:
            row.pop("requested_ego_crossing_speed_mps")
        self.assertEqual(fixed[0], fixed[1])
        self.assertEqual(fixed[1], fixed[2])
        selected_ids = [row["case_id"] for row in
                        json.loads((HERE / "execution-manifest.json").read_text())["cases"]]
        self.assertTrue(all(row["case_id"] in selected_ids for row in extension["cases"]))
        self.assertEqual(len(selected_ids), 7)

    def test_source_and_adapter_capability_gate(self):
        case = json.loads((HERE / "speed-sweep-extension.json").read_text())["cases"][0]["case_id"]
        self.packet["case_id"] = case
        self.site.write_text(json.dumps(self.packet) + "\n")
        adapter = type("Adapter", (), {"supports_speed_target": lambda self: False})()
        with self.assertRaisesRegex(ValueError, "lacks original speed-target"):
            prepare(case, self.site, adapter)
        self.packet["entrances"][1]["control"] = "yield"
        self.site.write_text(json.dumps(self.packet) + "\n")
        with self.assertRaisesRegex(ValueError, "entrance obligation mismatch"):
            prepare(case, self.site)

    def test_speed_target_reaches_every_original_control_tick(self):
        case = json.loads((HERE / "speed-sweep-extension.json").read_text())["cases"][1]["case_id"]
        self.packet["case_id"] = case
        self.site.write_text(json.dumps(self.packet) + "\n")

        class Adapter:
            world = World()
            transform_factory = staticmethod(lambda p, r: (p, r))

            def __init__(self):
                self.targets = []
                self.index = 0
                self.closed = False

            def supports_speed_target(self):
                return True

            def attach_cameras(self, actors, cameras):
                return {item["name"]: object() for item in cameras}

            def request_case_control(self, actors, site, variables, control, index):
                self.targets.append((variables["requested_ego_crossing_speed_mps"],
                                     control["requested_ego_crossing_speed_mps"], index))

            def tick_and_read(self, actors, cameras):
                index = self.index
                self.index += 1
                time_s = index / 20
                return {"frame": index, "time_s": time_s,
                        "camera_png": {name: b"\x89PNG\r\n\x1a\nfixture" for name in cameras},
                        "state": {"ego_id": 1, "other_id": 2},
                        "trace": {"frame": index, "time_s": time_s},
                        "video_frame": {"video_frame": index, "carla_frame": index,
                                        "time_s": time_s}}

            def finalize_media(self, output, views, mappings):
                media = {}
                for name in (*views, "raw"):
                    path = output / (name + ".mkv")
                    path.write_bytes(b"diagnostic media placeholder")
                    media[name] = path
                return media

            def close(self):
                self.closed = True
                return True

        adapter = Adapter()
        config = prepare(case, self.site, adapter)
        output = Path(self.temp.name) / "attempt"
        output.mkdir()
        (output / "construction.json").write_bytes(
            (HERE / "cases/approaching_near_response/construction.json").read_bytes())
        (output / "runner.py").write_bytes((HERE / "speed_sweep_runner.py").read_bytes())
        receipt = capture(adapter, config, self.site, output)
        target = config["control"]["requested_ego_crossing_speed_mps"]
        self.assertEqual(receipt["frame_count"], 900)
        self.assertEqual(adapter.targets, [(target, target, i) for i in range(900)])
        self.assertTrue(adapter.closed)
        self.assertTrue(all(actor.destroyed for actor in adapter.world.actors))
        self.assertTrue((output / "capture-seal.json").is_file())

    def test_independent_speed_comparison_checks_fixed_and_realized(self):
        extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
        records = []
        for row, mean in zip(extension["cases"], (1.0, 3.0, 5.0)):
            config = {"selected_case_id": row["case_id"],
                      "case": {"draft_variables": dict(row["draft_variables"])}}
            result = {"case_id": row["case_id"],
                      "realized_observables": {
                          "counterpart_center_station_first_m": 8.0,
                          "ego_speed_min_peak_to_stop_reference_mps": 0.004,
                          "ego_speed_mean_full_body_overlap_to_clear_mps": mean}}
            records.append((config, result))
        self.assertTrue(compare(records)["realized_bins_checked"])
        records[2][1]["realized_observables"]["ego_speed_mean_full_body_overlap_to_clear_mps"] = 3.0
        with self.assertRaisesRegex(ValueError, "missed planned above bin"):
            compare(records)
        records[2][1]["realized_observables"]["ego_speed_mean_full_body_overlap_to_clear_mps"] = 5.0
        records[2][0]["case"]["draft_variables"]["requested_other_station_m"] = 9
        with self.assertRaisesRegex(ValueError, "construction identity differs"):
            compare(records)


if __name__ == "__main__":
    unittest.main()
