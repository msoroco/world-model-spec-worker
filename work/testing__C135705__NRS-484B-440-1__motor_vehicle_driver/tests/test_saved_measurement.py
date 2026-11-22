"""Source join, physical contrast and independent comparison rejection tests."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from saved_measurement import measure_original
from comparison_audit import audit as compare
from delivery_audit import audit as audit_delivery


def body(x,y,hx=2.5,hy=1):
    return [[x-hx,y-hy],[x+hx,y-hy],[x+hx,y+hy],[x-hx,y+hy]]


def source_rows(scene):
    positions=(65,0,-65)
    standing_rect=scene["standing_body_xy_m"]
    cy=(standing_rect[1]+standing_rect[3])/2
    standing=[];passing=[];props=[];mechanical=[];mapping=[]
    for i,x in enumerate(positions):
        frame=101+i;time=20+i*.05
        mapping.append({"video_frame":i,"carla_frame":frame,"time_s":time})
        standing.append({"frame":frame,"time_s":time,"actor_id":1,
                         "body_vertices_xy_m":body(0,cy)})
        passing.append({"frame":frame,"time_s":time,"actor_id":2,
                        "body_vertices_xy_m":body(x,2.2)})
        actors=[]
        for j,r in enumerate(scene["sight_occluders_xy_m"]):
            actors.append({"actor_id":3+j,"body_vertices_xy_m":body((r[0]+r[2])/2,(r[1]+r[3])/2,
                                                                        (r[2]-r[0])/2,(r[3]-r[1])/2)})
        props.append({"frame":frame,"time_s":time,"actors":actors})
        mechanical.append({"frame":frame,"time_s":time,"standing_actor_id":1,
                           "physics_disabled_by_worker":True,"brake_requested":1.,
                           "hand_brake_requested":True})
    return mapping,standing,passing,props,mechanical


class SavedMeasurementTests(unittest.TestCase):
    def scene(self,suffix):return json.loads((HERE/"cases"/suffix/"scene.json").read_text())

    def test_original_rows_measure_three_different_physical_targets(self):
        results={}
        for suffix in ("passage_clear_view","passage_blocked","view_occluded_both"):
            scene=self.scene(suffix)
            results[suffix]=measure_original(scene,*source_rows(scene))
        self.assertTrue(results["passage_clear_view"]["physical_passage_observed"])
        self.assertFalse(results["passage_blocked"]["physical_passage_observed"])
        self.assertTrue(results["passage_blocked"]["passing_body_collision_frames"])
        self.assertTrue(results["view_occluded_both"]["physical_passage_observed"])
        self.assertFalse(results["view_occluded_both"]["sight_probes"]["negative_x:60.960m"]["clear_xy_geometry"])
        self.assertFalse(results["view_occluded_both"]["sight_probes"]["positive_x:60.960m"]["clear_xy_geometry"])
        self.assertTrue(all(r["legal_verdict_claimed"] is False for r in results.values()))

    def test_frame_join_and_real_prop_requirement_reject_missing_evidence(self):
        scene=self.scene("view_occluded_both");streams=source_rows(scene)
        altered=copy.deepcopy(streams);altered[2][1]["frame"]+=10
        with self.assertRaisesRegex(ValueError,"join failed"):
            measure_original(scene,*altered)
        altered=copy.deepcopy(streams);altered[3][1]["actors"]=[]
        with self.assertRaisesRegex(ValueError,"occluder actor count"):
            measure_original(scene,*altered)

    def test_delivery_audit_rejects_missing_saved_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"missing saved-only"):
                audit_delivery(tmp)

    def test_comparison_rejects_changed_fixed_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/"a";b=Path(tmp)/"b";a.mkdir();b.mkdir()
            clear=self.scene("passage_clear_view");blocked=self.scene("passage_blocked")
            blocked["other_vehicle_centers_xy_m"][0][1]=1.5
            (a/"scene.json").write_text(json.dumps(clear))
            (b/"scene.json").write_text(json.dumps(blocked))
            for root,scene in ((a,clear),(b,blocked)):
                (root/"standing-measurement.json").write_text(json.dumps({
                    "measured":measure_original(scene,*source_rows(scene))}))
            receipts=[{"case_id":clear["case_id"]},{"case_id":blocked["case_id"]}]
            with patch("comparison_audit.audit_delivery",side_effect=receipts):
                with self.assertRaisesRegex(ValueError,"fixed construction"):
                    compare("passage_width_with_fixed_view",a,b)


if __name__=="__main__":unittest.main()
