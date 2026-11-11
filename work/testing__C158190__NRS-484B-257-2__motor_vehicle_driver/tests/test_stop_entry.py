import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stop_entry_measurements", ROOT / "stop_entry_measurements.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StopEntryTests(unittest.TestCase):
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
