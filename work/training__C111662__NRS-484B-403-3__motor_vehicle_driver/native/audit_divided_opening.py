"""Independent exact-source, topology, comparison and proof audit."""
import json
import math
import xml.etree.ElementTree as ET

from build import CASE, PLAN, POLICIES, SOURCE, SOURCE_SHA, put, sha
from divided_opening import BRANCH, CENTERS, OPENING_X


def audit():
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    law = source["law_record"]["text"]
    if (sha(SOURCE) != SOURCE_SHA or plan["source_law_text"] != law or
            "or on a divided highway where an appropriate opening or crossing place exists" not in law):
        raise ValueError("Divided branch statutory source changed")
    cases = {row["case_id"] for row in plan["cases"]}
    divided = {CASE.name + "__" + suffix for suffix in CENTERS}
    comparison = next((row for row in plan["comparisons"]
                       if row["comparison_id"].endswith("__comparison_divided_opening")), None)
    if not divided <= cases or comparison is None or set(comparison["case_ids"]) != divided or \
            comparison["deliberate_differences"] != ["median_open_at_u_turn_crossing"]:
        raise ValueError("Divided branch plan comparison changed")
    request_proof = json.loads((BRANCH / "proof.json").read_text())
    saved_proof = json.loads((BRANCH / "saved-proof.json").read_text())
    offline = json.loads((BRANCH / "pinned-offline-proof.json").read_text())
    original_shape = json.loads((BRANCH / "original-shape-audit.json").read_text())
    if (request_proof["exact_positive_count"] != 8 or request_proof["exact_negative_count"] != 32 or
            saved_proof["positive_count"] != 8 or saved_proof["negative_count"] != 48 or
            saved_proof["frames_joined"] != 6400 or
            saved_proof["trigger_positive_count"] != 2 or
            saved_proof["trigger_negative_count"] != 6 or
            offline["candidate_count"] != 8 or offline["cpu_tests_passed"] != 32 or
            offline["materialized_files_checked"] != 160 or
            original_shape["candidate_count"] != 8 or
            original_shape["positive_count"] != 8 or
            original_shape["negative_count"] != 56 or
            original_shape["controlled_pairs"] != 4 or
            original_shape["original_native_observed"] is not False):
        raise ValueError("Divided branch proof counts changed")
    joined = 0
    for candidate in POLICIES:
        pair = []
        for suffix in CENTERS:
            bundle = BRANCH / "drafts" / suffix / candidate
            cfg = json.loads((bundle / "config.json").read_text())
            xml = ET.parse(bundle / "divided-highway.xodr").getroot()
            roads = {int(road.attrib["id"]): road for road in xml.findall("road")}
            if set(roads) != {503, 504, 505}:
                raise ValueError("Divided road IDs changed")
            for ident, expected in ((503, "median"), (504, "driving"), (505, "median")):
                lane = next((lane for lane in roads[ident].findall("./lanes/laneSection/left/lane")
                             if lane.attrib.get("id") == "1"), None)
                if lane is None or lane.attrib["type"] != expected or \
                        lane.find("roadMark").attrib["type"] != ("broken" if ident == 504 else "solid"):
                    raise ValueError("Median opening topology changed")
            requests = [json.loads(line) for line in
                        (bundle / "requested-tracks.jsonl").read_text().splitlines()]
            raw_path = BRANCH / "synthetic" / suffix / candidate / "raw.json"
            raw = json.loads(raw_path.read_text())
            saved = json.loads((raw_path.parent / "saved.json").read_text())
            if (len(requests) != 800 or len(raw["rows"]) != 800 or
                    saved["raw_sha256"] != sha(raw_path) or saved["frames_joined"] != 800 or
                    saved["district_designation_verified"] or
                    saved["opening_exception_legally_verified"] or
                    saved["original_native_observed"] or cfg["status"] != "unselected_native_request"):
                raise ValueError("Divided saved source or status mismatch")
            crossings = []
            for frame, (request, observation) in enumerate(zip(requests, raw["rows"])):
                if (request["frame"] != frame or observation["frame"] != frame or
                        observation["video_frame"] != frame or
                        observation["request_frame"] != frame or
                        observation["ego"]["center_xyz_m"] != request["requested_ego_xyz_m"] or
                        observation["ego"]["actor_id"] != 10 or
                        abs(observation["ego"]["heading_rad"] -
                            request["requested_heading_rad"]) > 1e-9):
                    raise ValueError("Independent divided actor/video/request join mismatch")
                if request["requested_phase"] == "u_turn" and \
                        observation["ego"]["center_xyz_m"][1] >= 0:
                    crossings.append(frame)
                joined += 1
            if not crossings or saved["crossing_frame"] != crossings[0]:
                raise ValueError("Divided crossing frame changed")
            crossing = raw["rows"][crossings[0]]["ego"]["center_xyz_m"]
            in_opening = OPENING_X[0] <= crossing[0] <= OPENING_X[1]
            if saved["crossing_x_m"] != crossing[0] or \
                    saved["crossing_in_authored_opening"] != in_opening or \
                    in_opening != (suffix == "divided_opening") or \
                    abs(saved["heading_reversal_rad"] - math.pi) > .001:
                raise ValueError("Divided crossing or heading result changed")
            pair.append((bundle, cfg, saved))
        first, second = pair
        if (first[0].joinpath("divided-highway.xodr").read_bytes() !=
                second[0].joinpath("divided-highway.xodr").read_bytes() or
                first[1]["camera_policy"] != second[1]["camera_policy"] or
                first[1]["requested_approach_speed_mps"] !=
                second[1]["requested_approach_speed_mps"] or
                first[1]["pre_turn_dwell_s"] != second[1]["pre_turn_dwell_s"] or
                abs(second[2]["crossing_x_m"] - first[2]["crossing_x_m"] - 45) > .0002):
            raise ValueError("Divided controlled pair changed fixed conditions")
    result = {"format": "c111662-4033-divided-independent-audit-v1",
              "candidate_count": 8, "controlled_pairs": 4,
              "joined_rows": joined, "exact_positive_count": 8,
              "exact_negative_count": 32, "saved_positive_count": 8,
              "saved_negative_count": 48, "cpu_tests_passed": 32,
              "original_shape_positive_count": 8,
              "original_shape_negative_count": 56,
              "authored_median_opening_only": True,
              "district_designation_verified": False,
              "original_native_observed": False, "delivery_ready": False}
    put(BRANCH / "independent-audit.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(audit()))
