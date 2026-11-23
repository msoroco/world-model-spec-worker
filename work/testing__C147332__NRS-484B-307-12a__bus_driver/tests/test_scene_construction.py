import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scene_construction", ROOT / "scene_construction.py")
scenes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenes)


class SceneConstructionTests(unittest.TestCase):
    def test_four_exact_drafts_hold_one_road_and_source_contract(self):
        paths = scenes.build()
        self.assertEqual(len(paths), 4)
        values = {path.parent.name: scenes.check_scene(json.loads(path.read_text()), scenes.MAP)
                  for path in paths}
        self.assertEqual(len({value["map_source_sha256"] for value in values.values()}), 1)
        self.assertEqual(values["adjacent_dark_drive"]["route_waypoint_centers_m"],
                         values["second_green_drive"]["route_waypoint_centers_m"])
        self.assertEqual(values["green_selected_drive"]["route_waypoint_centers_m"][0],
                         values["green_selected_stand"]["route_waypoint_centers_m"][0])
        self.assertEqual([s["display"] for s in values["adjacent_dark_drive"]["signals"]],
                         ["down_green_arrow", "dark"])
        self.assertEqual([s["display"] for s in values["second_green_drive"]["signals"]],
                         ["down_green_arrow", "down_green_arrow"])
        self.assertTrue(all(signal["official_device_source"] is None
                            for value in values.values() for signal in value["signals"]))

    def test_tampered_lane_mapping_and_bus_route_rejected(self):
        value = scenes.scene("second_green_drive", scenes.check_map(scenes.MAP))
        value["signals"][1]["governed_lane_id"] = "east"
        with self.assertRaisesRegex(ValueError, "scene"):
            scenes.check_scene(value, scenes.MAP)
        value = scenes.scene("second_green_drive", scenes.check_map(scenes.MAP))
        value["route_waypoint_centers_m"][1][1] = 0
        with self.assertRaisesRegex(ValueError, "scene"):
            scenes.check_scene(value, scenes.MAP)


if __name__ == "__main__":
    unittest.main()
