"""Construct three physical standing/visibility contrast scenes for CPU review."""
from __future__ import annotations

import json
import hashlib
import copy
from pathlib import Path

from standing_geometry import STATUTORY_SIGHT_DISTANCE_M, measure
from native_construction import candidate_opendrive

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + "__"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def base():
    return {"source_kind": "worker engineering candidate; Native realization unverified",
            "paved_road_xy_m": [-80,-3.5,80,3.5],
            "shoulder_negative_y_xy_m": [-80,-6,80,-3.5],
            "shoulder_positive_y_xy_m": [-80,3.5,80,6],
            "standing_body_xy_m": [-2.5,-3.5,2.5,-1.5],
            "standing_side": "negative_y",
            "other_vehicle_centers_xy_m": [[65,2.2],[10,2.2],[0,2.2],[-10,2.2],[-65,2.2]],
            "other_vehicle_half_length_m": 2.5,
            "other_vehicle_half_width_m": 1.0,
            "sight_eye_y_m": 2.2,
            "sight_probe_distances_m": [60.0,STATUTORY_SIGHT_DISTANCE_M,61.9],
            "sight_occluders_xy_m": [],
            "administrative_context": {"highway_status":"unverified",
                                       "business_district_status":"unverified",
                                       "residence_district_status":"unverified"},
            "disability_exception_context": {"disabled":"unverified",
                                             "unavoidable_stopping":"unverified",
                                             "temporary_duration":"unverified"}}


def main():
    map_path=HERE/"candidate-standing-road.xodr"
    map_path.write_text(candidate_opendrive())
    map_sha=hashlib.sha256(map_path.read_bytes()).hexdigest()
    scenes={}
    clear=base();scenes["passage_clear_view"]=clear
    # Translate one ordinary-size car into the opposite route. A wider
    # authored box would not be constructible with the fixed Model 3 actor.
    blocked=base();blocked["standing_body_xy_m"]=[-2.5,-.1,2.5,1.9]
    scenes["passage_blocked"]=blocked
    occluded=base();occluded["sight_occluders_xy_m"]=[[-31,-.5,-29,.3],[29,-.5,31,.3]]
    scenes["view_occluded_both"]=occluded
    for suffix,scene in scenes.items():
        scene["case_id"]=PREFIX+suffix
        scene.update(map_source="../../candidate-standing-road.xodr",
                     map_source_sha256=map_sha,
                     capture_rate_hz=20,duration_s=9,
                     standing_blueprint_id="vehicle.tesla.model3",
                     passing_blueprint_id="vehicle.tesla.model3",
                     occluder_blueprint_id="static.prop.streetbarrier" if suffix=="view_occluded_both" else None,
                     disabled_physical_mechanism="engine_off_brake_locked")
        measured=measure(scene)
        folder=HERE/"cases"/suffix
        write(folder/"scene.json",scene)
        write(folder/"cpu-geometry.json",{"case_id":scene["case_id"],
                                          "provenance_kind":"worker_engineering_candidate",
                                          "measured":measured,
                                          "legal_verdict_claimed":False,
                                          "native_capture_claimed":False})
        fallback=copy.deepcopy(scene)
        if suffix=="passage_clear_view":
            fallback["standing_body_xy_m"]=[-2.5,-4.0,2.5,-2.0]
        elif suffix=="passage_blocked":
            fallback["standing_body_xy_m"]=[-2.5,.2,2.5,2.2]
        else:
            # Keep the visibility pair's standing footprint identical when
            # both physical-risk fallbacks are selected.
            fallback["standing_body_xy_m"]=[-2.5,-4.0,2.5,-2.0]
            fallback["sight_occluders_xy_m"]=[[-31,-.9,-29,-.1],[29,-.9,31,-.1]]
        fallback["candidate_id"]="fallback1"
        fallback_measured=measure(fallback)
        write(folder/"fallback1-scene.json",fallback)
        write(folder/"fallback1-cpu-geometry.json",{
            "case_id":scene["case_id"],"candidate_id":"fallback1",
            "provenance_kind":"worker_engineering_candidate",
            "measured":fallback_measured,"native_capture_claimed":False})
        print(suffix,"physical_passage",measured["physical_passage_observed"],
              "opposite_width_m",measured["unobstructed_opposite_width_m"],
              "two_sided_200ft_visibility",
              [measured["sight_probes"][f"{side}:60.960m"]["visible"]
               for side in ("negative_x","positive_x")])
    plan_path=HERE/"case-plan.json";plan=json.loads(plan_path.read_text())
    gap={"id":"passage-and-200ft-view-unverified",
         "requirement":"In-every-event unobstructed passage width opposite a standing vehicle and clear view from 200 feet in each direction",
         "source":{"path":"inputs/"+HERE.name+"/assignment.json",
                   "sha256":next(item["sha256"] for item in plan["sources"] if item["path"].endswith("/assignment.json"))},
         "why_existing_insufficient":"No accepted recording or original source with passage and two-sided visibility measurements exists in the frozen inventory."}
    plan["evidence_review"]["gaps"]=[gap]
    purposes={"passage_clear_view":"standing footprint leaves a full-body route and both 200-foot sight lines clear",
              "passage_blocked":"standing footprint intersects the other vehicle's full-body route while sight geometry stays fixed",
              "view_occluded_both":"two authored occluder rectangles block the 200-foot sight lines while passage remains clear"}
    risks={"passage_clear_view":"Native car and road footprint may differ from authored clearance",
           "passage_blocked":"Native driver may steer around the standing vehicle instead of exposing blocked passage",
           "view_occluded_both":"Authored occluders may not block camera sight lines in live CARLA"}
    plan["cases"]=[{"case_id":PREFIX+suffix,"target_law_id":plan["law_id"],
                    "purpose":purposes[suffix],"construction_candidate":f"cases/{suffix}/scene.json",
                    "status":"engineering_candidate_cpu_geometry_checked_native_unverified",
                    "gap_ids":[gap["id"]],
                    "physical_risk_assessment":{"status":"physical","risk":risks[suffix],
                                                "fallback_policy":"source-inspect and test fallback1 geometry if primary Native target fails",
                                                "fallback_construction":f"cases/{suffix}/fallback1-scene.json",
                                                "trigger":"original actor body or sight measurement misses the requested physical target"}}
                   for suffix in scenes]
    plan["comparisons"]=[{"comparison_id":"passage_width_with_fixed_view",
                          "case_ids":[PREFIX+"passage_clear_view",PREFIX+"passage_blocked"],
                          "deliberate_differences":["standing full-body intrusion into passing path"],
                          "fixed_conditions":["same road, other vehicle path, dimensions and clear sight sources"],
                          "status":"cpu_geometry_pair_tested_native_pair_pending"},
                         {"comparison_id":"two_sided_visibility_with_fixed_passage",
                          "case_ids":[PREFIX+"passage_clear_view",PREFIX+"view_occluded_both"],
                          "deliberate_differences":["two explicit sight occluder footprints"],
                          "fixed_conditions":["same road, standing footprint and other vehicle passage path"],
                          "status":"cpu_geometry_pair_tested_native_pair_pending"}]
    plan["observations"]=[{"name":"standing_body_xy_m","mandatory":True,
                            "source":"original Native actor bounding box each stopped frame"},
                           {"name":"other_vehicle_body_xy_m","mandatory":True,
                            "source":"original Native other-vehicle bounding box and path each frame"},
                           {"name":"two_sided_200ft_sight","mandatory":True,
                            "source":"original camera geometry, occluders and full decoded pixels at both statutory probe positions"}]
    branch=plan["selected_branches"][0]
    plan["requirement_dispositions"]=[{"requirement":gap["requirement"],
                                        "source":{"path":branch["source"],
                                                  "sha256":branch["source_sha256"],
                                                  "source_index":branch["source_index"]},
                                        "status":"selected_required",
                                        "case_ids":[PREFIX+suffix for suffix in scenes],
                                        "evidence_or_gap":"No accepted original; three CPU geometry candidates contrast passage and two-sided sight, with Native proof pending."}]
    plan["planning_status"]="three_cpu_geometry_candidates_native_and_delivery_pending"
    write(plan_path,plan)


if __name__=="__main__":main()
