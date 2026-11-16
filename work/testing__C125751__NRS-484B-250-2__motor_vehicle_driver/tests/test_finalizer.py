import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE.parents[1] / "runtime/scenario_pipeline"))
from finalizer import CASES, finalize
from entry_measurements import analyze as measure_entry


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def body(x, y):
    return {"position_xy_m": [x,y], "body_vertices_xy_m":
            [[x-.3,y-.3],[x+.3,y-.3],[x+.3,y+.3],[x-.3,y+.3]]}


class SavedFinalizerTests(unittest.TestCase):
    def sources(self, root):
        case = next(k for k,v in CASES.items() if v == "Off")
        (root / "config.json").write_text(json.dumps({
            "selected_case_id": case, "law_id": "NRS-484B-250-2", "cell_id": "C125751",
            "target_signal_state": "Off", "duration_s": .2, "rate_hz": 20,
            "recording_description": {"channels": [
                {"name": "signal_state", "unit": "structured record", "method": "Native signal state",
                 "time_window": "capture", "reference_frame": "original", "uncertainty": "synthetic",
                 "sampling_rate_hz": 20},
                {"name": "stop_state", "unit": "structured record", "method": "original speed/body",
                 "time_window": "capture", "reference_frame": "original", "uncertainty": "synthetic",
                 "sampling_rate_hz": 20}],
                "context_inputs": [{"name": "entry_context", "unit": "structured record",
                                    "method": "saved-source entry/signal/stop join"}],
                "limitations": ["synthetic diagnostic only"]},
            "physical_completion": {"context_sources": ["road_geometry.json"]},
            "site": {"routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                                "other": [[0,-10],[0,-4],[0,0],[0,10]]}}}))
        (root / "road_geometry.json").write_text(json.dumps({
            "intersection_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
            "intersection_id": 7, "ego_highway_id": 1, "other_highway_id": 2,
            "device_inventory_source": "synthetic signal inventory",
            "ego_approach_heading_deg": 0, "other_approach_heading_deg": 90,
            "approach_geometry_source": "synthetic source",
            "ego_approach_origin_xy_m": [-8,0], "other_approach_origin_xy_m": [0,-8]}))
        (root / "turn_route_context.json").write_text(json.dumps({
            "intersection_id": 7,
            "routes": {"ego": [[-10,0],[-4,0],[0,0],[10,0]],
                       "other": [[0,-10],[0,-4],[0,0],[0,10]]},
            "approach_geometry_source": "synthetic source"}))
        frames = [100,101,102,103]
        times = [0,.05,.1,.15]
        crossing=[];signal=[];stop=[];mapping=[];trace=[]
        for i,(frame,t) in enumerate(zip(frames,times)):
            ex,oy = (-8,-8) if i == 0 else ((-8,-5.2) if i == 1 else ((-5.2,-4) if i == 2 else (-4,-3)))
            ego, other = body(ex,0), body(0,oy)
            ego.update(heading_deg=0, native_road_id=1, native_lane_id=-1)
            other.update(heading_deg=90, native_road_id=2, native_lane_id=-1)
            crossing.append({"frame":frame,"time_s":t,"ego":ego,"other":other})
            signal.append({"frame":frame,"time_s":t,"native_signal_id":55,
                           "state":"Off" if i>=2 else "Red",
                           "other_native_signal_id":56,"other_state":"Off"})
            stop.append({"frame":frame,"time_s":t,
                         "ego":{"speed_mps":0 if i==1 else 2,"front_xy_m":[ex+.3,0],
                                "body_inside_crossing":i>=2},
                         "other":{"speed_mps":0 if i==0 else 2,"front_xy_m":[0,oy+.3],
                                  "body_inside_crossing":i>=1}})
            mapping.append({"video_frame":i,"carla_frame":frame,"time_s":t})
            trace.append({"frame":frame,"time_s":t,"position_m":[ex,0,0]})
        write_rows(root/"crossing_history.jsonl",crossing)
        write_rows(root/"signal_history.jsonl",signal)
        write_rows(root/"stop_history.jsonl",stop)
        write_rows(root/"video_frames.jsonl",mapping)
        write_rows(root/"trace.jsonl",trace)
        (root/"signal_context.json").write_text(json.dumps({"intersection_id":7,
            "native_signal_id":55,"native_map_id":"SyntheticFixtureTown",
            "governed_road_id":1,"governed_lane_id":-1,
            "other_native_signal_id":56,"other_governed_road_id":2,
            "other_governed_lane_id":-1}))
        (root/"stop_context.json").write_text(json.dumps({"intersection_id":7,
            "selected_references":{
                "ego":{"kind":"marked_stop_line","segment_xy_m":[[-5,-2],[-5,2]],
                       "geometry_source":"synthetic ego line","reference_review_source":"synthetic diagnostic"},
                "other":{"kind":"marked_stop_line","segment_xy_m":[[-2,-5],[2,-5]],
                         "geometry_source":"synthetic other line","reference_review_source":"synthetic diagnostic"}}}))
        (root/"capture").mkdir()
        (root/"capture/evidence.jsonl").write_text('{}\n')
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (root/(name+".mkv")).write_bytes(b"synthetic placeholder; not a media proof")
        (root/"head_visibility_review.json").write_text(json.dumps({
            "camera":"approach","video_frame":2,"carla_frame":102,"native_signal_id":55,
            "source_video_sha256":hashlib.sha256((root/"approach.mkv").read_bytes()).hexdigest(),
            "head_region_px":[10,10,30,30],"installed":True,"uncovered":True,
            "review_basis":"synthetic diagnostic; no physical pixel claim"}))
        (root/"other_head_visibility_review.json").write_text(json.dumps({
            "camera":"reference_corner","video_frame":2,"carla_frame":102,"native_signal_id":56,
            "source_video_sha256":hashlib.sha256((root/"reference_corner.mkv").read_bytes()).hexdigest(),
            "head_region_px":[10,10,30,30],"installed":True,"uncovered":True,
            "review_basis":"synthetic diagnostic; no physical pixel claim"}))

    def test_saved_sources_create_four_measurements(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.sources(root)
            measurements=finalize(root,root/"analysis-report.json")
            self.assertEqual(set(measurements),{"body_entry_timing","signal_at_entry","stop_order","turn_context"})
            self.assertTrue(measurements["turn_context"]["value"]["original_heading_complete"])
            self.assertEqual(measurements["signal_at_entry"]["value"]["at_body_entry"]["ego"]["native_state"],"Off")
            self.assertEqual(measurements["stop_order"]["value"]["statutory_stop_judgment"],"unresolved")
            result=json.loads((root/"result.json").read_text())
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["source_evidence_hashes"]["approach.mkv"],
                             hashlib.sha256((root/"approach.mkv").read_bytes()).hexdigest())
            self.assertEqual(result["source_evidence_hashes"]["reference_corner.mkv"],
                             hashlib.sha256((root/"reference_corner.mkv").read_bytes()).hexdigest())
            self.assertTrue((root/"channels/signal_state.jsonl").is_file())
            self.assertTrue((root/"channels/stop_state.jsonl").is_file())

    def test_missing_original_stop_history_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.sources(root)
            (root/"stop_history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError,"Missing required source: stop_history.jsonl"):
                finalize(root,root/"analysis-report.json")

    def test_entry_arrival_sweep_preserves_unresolved_legal_judgment(self):
        """Exercise measured order across a controller-like, one-frame arrival sweep.

        The shifted tracks are synthetic diagnostic sources. They establish that
        the saved-source measurement responds to arrival order, not that the
        selected Native intersection can realize any of these points.
        """
        source = PACKAGE / "diagnostic-sources"
        original = [json.loads(line) for line in
                    (source / "crossing_history.jsonl").read_text().splitlines()]
        results = []
        for shift in (-1, 0, 1, 2):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ("road_geometry.json", "video_frames.jsonl"):
                    (root / name).write_bytes((source / name).read_bytes())
                rows = []
                for i, row in enumerate(original):
                    shifted = dict(row)
                    donor = min(max(i - shift, 0), len(original) - 1)
                    shifted["other"] = original[donor]["other"]
                    rows.append(shifted)
                write_rows(root / "crossing_history.jsonl", rows)
                measured = measure_entry(root)
                results.append(measured["ego_minus_other_entry_time_s"])
                self.assertEqual(measured["first_body_entry"]["ego"]["frame"], 102)
                self.assertEqual(measured["approximately_same_time_judgment"],
                                 "unresolved; no numeric legal threshold")
                self.assertEqual(measured["right_of_way_judgment"], "unresolved")
        for observed, expected in zip(results, (.10, .05, 0, -.05)):
            self.assertAlmostEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
