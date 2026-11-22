import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("stop_entry_measurements", ROOT / "stop_entry_measurements.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
import stop_construction
import stop_site


class StopEntryTests(unittest.TestCase):
    def test_authored_stop_site_and_case_staging_plans(self):
        receipt = stop_site.validate_authored_site()
        self.assertEqual(receipt['approach_road_id'], 158190)
        self.assertEqual(receipt['approach_lane_id'], -1)
        self.assertEqual(receipt['stop_signal_id'], '1581902')
        prefix = stop_construction.PREFIX
        inside = stop_construction.plan_case(prefix + 'stop_other_inside')
        approaching = stop_construction.plan_case(prefix + 'stop_other_approaching')
        clear = stop_construction.plan_case(prefix + 'stop_no_other')
        rolling = stop_construction.plan_case(prefix + 'stop_no_halt')
        self.assertEqual(inside['other_start_road_id'], 158195)
        self.assertEqual(approaching['other_start_road_id'], 158194)
        self.assertIsNone(clear['other_point_xy_m'])
        self.assertTrue(rolling['rolling_response_requested'])
        self.assertEqual(inside['ego_point_xy_m'], approaching['ego_point_xy_m'])
        with self.assertRaisesRegex(ValueError, 'different control construction'):
            stop_construction.plan_case(prefix + 'signal_control_exception')

    def test_mutated_authored_stop_control_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrong-sign.xodr'
            path.write_text(stop_site.ROAD.read_text().replace('type="206"', 'type="205"'))
            with self.assertRaisesRegex(ValueError, 'Stop sign does not govern'):
                stop_site.validate_authored_site(path)

    def test_stop_stage_holds_until_observed_stillness_and_clear_path(self):
        prefix = stop_construction.PREFIX
        stage = stop_construction.StopStage(prefix + 'stop_other_inside', hold_frames=2)
        state = dict(before_reference=True, within_intersection=False,
                     other_clear=False)
        self.assertEqual(stage.target(2, 1, **state), 0)
        self.assertEqual(stage.target(2, 0, **state), 0)
        self.assertEqual(stage.target(2, 0, **state), 0)
        self.assertEqual(stage.stopped_frames, 2)
        self.assertEqual(stage.target(2, 0, before_reference=True,
                                      within_intersection=False, other_clear=True), 5)
        self.assertTrue(stage.released)
        rolling = stop_construction.StopStage(prefix + 'stop_no_halt')
        self.assertEqual(rolling.target(2, 3, **state), 4)
        self.assertFalse(rolling.released)
        with self.assertRaisesRegex(ValueError, 'crossed stop reference'):
            stop_construction.StopStage(prefix + 'stop_no_other').target(
                0, 3, before_reference=False, within_intersection=False,
                other_clear=True)

    def fixture(self, root):
        context = {"native_map_id":"TownX", "intersection_id":42,"ego_approach_road_id":7,
                   "native_stop_sign_id":25,"sign_governance_source":"Native-trigger-and-face",
                   "entrance_inventory_source":"all-entrances-map-and-cameras",
                   "stop_reference_source":"stop-line-original-frame",
                   "highway_status_source":"road-review", "non_through_highway":True,
                   "police_control":False,"traffic_signal_control":False,
                   "ego_entrance_device":"stop",
                   "entrances":[{"road_id":7,"device":"stop"},{"road_id":9,"device":"none"}]}
        (root/"intersection_context.json").write_text(json.dumps(context))
        rows=[]
        for i,(speed,entry,before,other) in enumerate(((3,False,True,False),(0,False,True,True),(2,True,False,True))):
            rows.append({"frame":100+i,"time_s":1+i*.05,"ego_road_id":7,
                         "ego_speed_source":"actor.get_velocity","ego_speed_mps":speed,
                         "ego_body_in_intersection":entry,"ego_body_before_stop_reference":before,
                         "other_body_in_intersection":other})
        frames=[{"video_frame":i,"carla_frame":r["frame"],"time_s":r["time_s"]} for i,r in enumerate(rows)]
        (root/"entry_history.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
        (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))

    def test_stopped_before_entry_with_other_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            result=module.analyze(root)
            self.assertTrue(result["observed_full_stop_before_reference"])
            self.assertTrue(result["observed_other_occupancy"])
            self.assertEqual(result["legal_conclusion"],"unresolved")

    def test_unsourced_exception_and_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            context=json.loads((root/"intersection_context.json").read_text())
            context["police_control"]=True
            (root/"intersection_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError,"exception"):
                module.analyze(root)
            self.fixture(root)
            frames=[json.loads(r) for r in (root/"video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"]=999
            (root/"video_frames.jsonl").write_text("".join(json.dumps(r)+"\n" for r in frames))
            with self.assertRaisesRegex(ValueError,"frame join"):
                module.analyze(root)


if __name__ == "__main__":
    unittest.main()
