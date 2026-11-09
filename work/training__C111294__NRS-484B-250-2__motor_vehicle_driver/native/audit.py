"""Independent copied-source, right-approach, saved-entry and pair audit."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = CASE / "case-plan.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    manifest = json.loads((HERE / "manifest.json").read_text())
    if (manifest["assignment_sha256"] != sha(SOURCE) or
            manifest["case_plan_sha256"] != sha(PLAN) or len(manifest["entries"]) != 8 or
            plan["source_law"]["text"] != source["law_record"]["text"]):
        raise ValueError("Source or manifest mismatch")
    pairs = {}
    joins = 0
    for entry in manifest["entries"]:
        suffix = entry["case_id"].split("__")[-1]
        candidate = entry["candidate_id"]
        bundle = HERE / "drafts" / suffix / candidate
        cfg = json.loads((bundle / "config.json").read_text())
        raw_path = HERE / "synthetic" / suffix / candidate / "raw.json"
        saved_path = raw_path.parent / "saved.json"
        raw = json.loads(raw_path.read_text())
        saved = json.loads(saved_path.read_text())
        if ((bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or
                (bundle / "case-plan.json").read_bytes() != PLAN.read_bytes() or
                entry["config_sha256"] != sha(bundle / "config.json") or
                cfg["road_sha256"] != sha(bundle / "crossroads.xodr") or
                cfg["tracks_sha256"] != sha(bundle / "requested-tracks.jsonl") or
                raw["config_sha256"] != sha(bundle / "config.json") or
                saved["raw_sha256"] != sha(raw_path) or
                saved["synthetic"] is not True or saved["delivery_ready"] is not False):
            raise ValueError("Copied or saved source digest mismatch")
        road = ET.parse(bundle / "crossroads.xodr").getroot()
        connections = {(int(c.attrib["incomingRoad"]), int(c.attrib["connectingRoad"]))
                       for c in road.findall("./junction/connection")}
        if connections != {(250, 251), (253, 254)} or \
                any(r.find("signals/signal") is not None for r in road.findall("road")):
            raise ValueError("Two-road uncontrolled junction mismatch")
        requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
        observations = raw["rows"]
        if len(requests) != 600 or len(observations) != 600:
            raise ValueError("Frame count mismatch")
        ego_entry = other_entry = None
        for index, (request, observed) in enumerate(zip(requests, observations)):
            if (request["frame"] != index or observed["frame"] != index or
                    observed["video_frame"] != index or observed["request_frame"] != index or
                    abs(observed["time_s"] - index/20) > 1e-9 or
                    observed["ego"]["center_xyz_m"] != request["requested_ego_xyz_m"] or
                    observed["other"]["center_xyz_m"] != request["requested_other_xyz_m"] or
                    observed["ego"]["actor_id"] != 10 or observed["other"]["actor_id"] != 11):
                raise ValueError("Independent frame/actor/source join")
            ex, ey, _ = observed["ego"]["center_xyz_m"]
            ox, oy, _ = observed["other"]["center_xyz_m"]
            if abs(ey+1.75)>1e-9 or abs(ox-1.75)>1e-9:
                raise ValueError("Approach side changed")
            expected_ego = {(round(ex+dx,6), round(ey+dy,6)) for dx in (-2,2) for dy in (-.9,.9)}
            expected_other = {(round(ox+dy,6), round(oy+dx,6)) for dx in (-2,2) for dy in (-.9,.9)}
            if ({(round(p[0],6),round(p[1],6)) for p in observed["ego"]["body_xyz_m"]} != expected_ego or
                    {(round(p[0],6),round(p[1],6)) for p in observed["other"]["body_xyz_m"]} != expected_other):
                raise ValueError("Independent body footprint mismatch")
            if ego_entry is None and max(p[0] for p in observed["ego"]["body_xyz_m"]) >= -20:
                ego_entry = index/20
            if other_entry is None and max(p[1] for p in observed["other"]["body_xyz_m"]) >= -20:
                other_entry = index/20
            joins += 1
        if (saved["ego_front_entry_s"] != ego_entry or saved["other_front_entry_s"] != other_entry or
                saved["ego_minus_other_front_entry_s"] != (None if ego_entry is None else round(ego_entry-other_entry,6))):
            raise ValueError("Independent entry-time mismatch")
        pairs[(suffix,candidate)] = {"requests": requests, "saved": saved}
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        left = pairs[("controlled_1",candidate)]["requests"]
        right = pairs[("controlled_2",candidate)]["requests"]
        if [r["requested_other_xyz_m"] for r in left] != [r["requested_other_xyz_m"] for r in right]:
            raise ValueError("Controlled pair changed right-hand vehicle")
        if [r["requested_ego_xyz_m"] for r in left] == [r["requested_ego_xyz_m"] for r in right] and candidate != "fallback3":
            raise ValueError("Controlled pair omitted yielding variation")
    result = {"format": "c111294-2502-independent-audit-v1", "candidates": 8,
              "joined_rows": joins, "controlled_pairs": 4,
              "primary_entry_gaps_s": {suffix:pairs[(suffix,"primary")]["saved"]["ego_minus_other_front_entry_s"] for suffix in ("controlled_1","controlled_2")},
              "synthetic_only": True, "original_native_observed": False,
              "delivery_ready": False}
    (HERE / "independent-audit.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit()))
