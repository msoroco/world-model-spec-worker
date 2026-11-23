"""Positive and negative synthetic protocols for saved trace measurement."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_case_plan import AID, KINDS
from saved_measurement import measure
from source_bound_scene import sha
from tests.test_source_bound_scene import fixture


def body(x, y):
    return [[x-0.5,y-1,0],[x+0.5,y-1,0],[x+0.5,y+1,0],[x-0.5,y+1,0]]


def protocol(root, *, suffix="stopped_leftmost_clear", pedestrian=False):
    packet = fixture(root)
    if KINDS[suffix][2] == "two_way":
        packet["receiving"]["one_way_to_left"] = False
        receiving_source = root / "receiving_lanes.txt"
        receiving_source.write_text("synthetic CPU two-way receiving protocol\n")
        packet["sources"]["receiving_lanes"]["sha256"] = sha(receiving_source)
    site = root / "site.json"
    site.write_text(json.dumps(packet))
    case_id = AID + "__" + suffix
    x = 1.75 if KINDS[suffix][1] == "inner_lane" else -1.75
    traffic = suffix.endswith("traffic_yield") or suffix.endswith("traffic_advance")
    pedestrian = pedestrian or suffix.endswith("pedestrian_yield") or suffix.endswith("pedestrian_advance")
    rows=[]
    for number in range(13):
        time_s=number*0.05
        y=-4 if number < 12 else -1
        speed=0 if 1 <= number < 12 and KINDS[suffix][0] == "complete_stop" else 2
        ped=pedestrian and number == (10 if suffix.endswith("pedestrian_yield") else 12)
        conflicting_traffic=traffic and number == (10 if suffix.endswith("traffic_yield") else 12)
        ego={"actor_id":"1","location_xyz_m":[x,y,0],
             "velocity_xyz_mps":[0,speed,0],"body_vertices_xyz_m":body(x,y)}
        ped_actor={"actor_id":"2","body_vertices_xyz_m":body(-3,-1)}
        traffic_actor={"actor_id":"3","body_vertices_xyz_m":body(-2,-1)}
        frame={"origin":"native_world_snapshot","frame":number,"time_s":time_s,
               "ego":ego,"signal_actor_id":"protocol-signal","signal_state":"Red",
               "pedestrians":[ped_actor] if ped else [],
               "other_traffic":[traffic_actor] if conflicting_traffic else []}
        rows.append({"case_id":case_id,"source_packet_sha256":sha(site),
                     "selected_approach_lane_id":"east" if x > 0 else "west",
                     "original_sample_claim":True,
                     "time_s":time_s,"signal":"steady_red_alone",
                     "pedestrian_conflict":ped,"traffic_conflict":conflicting_traffic,
                     "native_frame":frame})
    trace=root/"trace.jsonl"
    trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
    return site,trace,case_id,rows


class SavedMeasurementTests(unittest.TestCase):
    def test_original_geometry_and_conflict_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            site,trace,case_id,_=protocol(root,pedestrian=True,
                suffix="stopped_leftmost_pedestrian_advance")
            result=measure(site,trace,case_id)
            self.assertTrue(result["engineering_stop_observed"])
            self.assertEqual(result["first_boundary_crossing_frame"],12)
            self.assertEqual(result["first_approach_lane_id"],"west")
            self.assertTrue(result["conflicts_at_first_boundary_crossing"]["pedestrian"])
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["legal_judgment"],"unresolved")

    def test_missing_frame_signal_actor_and_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            site,trace,case_id,rows=protocol(root)
            rows.pop(5)
            trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"frame sequence"):
                measure(site,trace,case_id)
            site,trace,case_id,rows=protocol(root)
            rows[0]["native_frame"]["signal_state"]="Green"
            trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"signal state differs"):
                measure(site,trace,case_id)
            site,trace,case_id,rows=protocol(root)
            rows[0]["native_frame"]["signal_actor_id"]="wrong"
            trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"signal actor differs"):
                measure(site,trace,case_id)
            site,trace,case_id,rows=protocol(root)
            (root/"opendrive.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError,"retained source missing or changed"):
                measure(site,trace,case_id)

    def test_missing_participant_and_unclaimed_sample_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            site,trace,case_id,rows=protocol(root,pedestrian=True,
                suffix="stopped_leftmost_pedestrian_advance")
            rows[12]["native_frame"]["pedestrians"]=[]
            trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"declared conflict lacks original participant"):
                measure(site,trace,case_id)
            site,trace,case_id,rows=protocol(root)
            rows[0]["original_sample_claim"]=False
            trace.write_text("".join(json.dumps(row)+"\n" for row in rows))
            with self.assertRaisesRegex(ValueError,"exact original case/source join"):
                measure(site,trace,case_id)


if __name__=="__main__":
    unittest.main()
