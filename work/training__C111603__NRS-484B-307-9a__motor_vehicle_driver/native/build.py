"""Source-pinned, unselected Native requests for NRS 484B.307(9)(a)."""
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
TEMPLATE = ROOT / "work/training__C110919__NRS-484B-307-8a__motor_vehicle_driver/native/road.xodr"
SOURCE_SHA = "aa4cb76c4fc251e5dc1ad7f2e95776abc317c737f1dff66fc6ce41e8df1f3b8d"
FRAMES = 480
RATE = 20
POLICIES = {
    "primary": (8.0, "standard", 0.0),
    "fallback1": (5.0, "standard", 0.0),
    "fallback2": (8.0, "elevated_overview", 0.0),
    "fallback3": (8.0, "standard", 2.0),
}
CASES = {"witness_1": "right_arrow_turn", "witness_2": "straight_against_right_arrow"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_text():
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen C111603 assignment changed")
    source = json.loads(SOURCE.read_text())
    law = next(item for item in source["law_records"] if item["id"] == "NRS-484B-307-9a") if "law_records" in source else None
    if law is None:
        plan = json.loads(PLAN.read_text())
        text = plan["source_law"]["text"]
    else:
        text = law["text"]
    for clause in ("steady red with a green turn arrow", "movement indicated by the green turn arrow",
                   "other traffic lawfully using the intersection"):
        if clause not in text:
            raise ValueError("Statutory clause missing: " + clause)
    return text


def road():
    """Reuse a source-independent intersection footprint; add an arrow head."""
    tree = ET.fromstring(TEMPLATE.read_text())
    tree.find("header").set("name", "C111603-red-plus-green-arrow-request")
    tree.find("header").set("date", "2026-11-08")
    first = tree.find("./road[@id='1']")
    signals = first.find("signals")
    red = signals.find("signal")
    if red is None:
        raise ValueError("Template lacks approach signal")
    red.set("name", "south-approach-steady-red-request")
    arrow = ET.SubElement(signals, "signal", dict(red.attrib))
    arrow.set("id", "1603")
    arrow.set("name", "south-approach-green-right-arrow-request")
    arrow.set("subtype", "1")
    arrow.set("t", "-4.0")
    return ET.tostring(tree, encoding="unicode") + "\n"


def requested_rows(movement, speed, dwell):
    rows = []
    approach_s = 45.0 / speed
    yield_s = 3.0
    for frame in range(FRAMES):
        t = frame / RATE
        moving_t = max(0.0, t - dwell)
        distance = min(45.0, speed * moving_t)
        if distance < 45.0:
            x, y, heading, phase = -1.75, -50.0 + distance, math.pi / 2, "approach"
        elif moving_t < approach_s + yield_s:
            x, y, heading, phase = -1.75, -5.0, math.pi / 2, "yield_hold"
        else:
            path = speed * (moving_t - approach_s - yield_s)
            if movement == "right_arrow_turn":
                u = min(math.pi / 2, path / 7.0)
                x, y, heading = 5.25 - 7 * math.cos(u), -5 + 7 * math.sin(u), math.pi / 2 - u
                if u == math.pi / 2:
                    x += max(0.0, path - 7 * math.pi / 2)
            else:
                x, y, heading = -1.75, -5 + path, math.pi / 2
            phase = "intersection_movement"
        other_x = min(40.0, -30.0 + 4.0 * t)
        rows.append({
            "frame": frame, "time_s": t,
            "requested_ego_xyz_m": [round(x, 6), round(y, 6), 0.0],
            "requested_heading_rad": round(heading, 9),
            "requested_other_vehicle_xyz_m": [round(other_x, 6), 2.0, 0.0],
            "requested_phase": phase,
            "requested_signal": {"circular_red": True, "green_arrow": "right", "governs_ego": True},
            "requested_movement": movement,
            "requested_other_traffic_lawful": True,
            "requested_yield_to_other_traffic": phase == "yield_hold",
            "original_native_observed": False, "legal_verdict": None})
    return rows


def build():
    text = source_text()
    xml = road()
    entries = []
    for suffix, movement in CASES.items():
        for candidate, (speed, camera, dwell) in POLICIES.items():
            bundle = HERE / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / "assignment-source.json").write_bytes(SOURCE.read_bytes())
            (bundle / "arrow-intersection.xodr").write_text(xml)
            rows_path = bundle / "requested-tracks.jsonl"
            rows_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                         for row in requested_rows(movement, speed, dwell)))
            cfg = {
                "format": "c111603-3079a-native-request-v1", "assignment_id": CASE.name,
                "assignment_sha256": SOURCE_SHA, "case_id": CASE.name + "__" + suffix,
                "candidate_id": candidate, "source_text": text,
                "road_sha256": digest(bundle / "arrow-intersection.xodr"),
                "tracks_sha256": digest(rows_path), "frames": FRAMES, "rate_hz": RATE,
                "ego_blueprint": "vehicle.tesla.model3", "other_blueprint": "vehicle.audi.tt",
                "requested_movement": movement, "approach_speed_mps": speed,
                "camera_policy": camera, "pre_approach_dwell_s": dwell,
                "yield_hold_s": 3.0, "signal_state_requested_only": True,
                "status": "unselected_native_request", "original_native_observed": False,
                "legal_verdict": None, "delivery_ready": False}
            write(bundle / "config.json", cfg)
            entries.append({"case_id": cfg["case_id"], "candidate_id": candidate,
                            "config_sha256": digest(bundle / "config.json")})
    manifest = {"format": "c111603-3079a-native-manifest-v1", "assignment_id": CASE.name,
                "assignment_sha256": SOURCE_SHA, "entries": entries,
                "status": "draft_not_selected", "original_native_observed": False,
                "delivery_ready": False}
    write(HERE / "manifest.json", manifest)
    return manifest


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    candidate = cfg["candidate_id"]
    if suffix not in CASES or candidate not in POLICIES:
        raise ValueError("Unknown C111603 candidate")
    speed, camera, dwell = POLICIES[candidate]
    if (digest(SOURCE) != SOURCE_SHA or
            (bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or
            cfg["assignment_id"] != CASE.name or cfg["assignment_sha256"] != SOURCE_SHA or
            cfg["source_text"] != source_text() or cfg["requested_movement"] != CASES[suffix] or
            cfg["approach_speed_mps"] != speed or cfg["camera_policy"] != camera or
            cfg["pre_approach_dwell_s"] != dwell or cfg["yield_hold_s"] != 3.0 or
            cfg["frames"] != FRAMES or cfg["rate_hz"] != RATE or
            cfg["status"] != "unselected_native_request" or
            cfg["signal_state_requested_only"] is not True or
            cfg["original_native_observed"] is not False or
            cfg["delivery_ready"] is not False or cfg["legal_verdict"] is not None):
        raise ValueError("Source-bound C111603 config changed")
    path = bundle / "arrow-intersection.xodr"
    if path.read_text() != road() or cfg["road_sha256"] != digest(path):
        raise ValueError("Arrow intersection request changed")
    tree = ET.parse(path).getroot()
    names = {s.attrib["name"] for s in tree.findall("./road[@id='1']/signals/signal")}
    if not {"south-approach-steady-red-request", "south-approach-green-right-arrow-request"} <= names:
        raise ValueError("Requested signal pair missing")
    rows_path = bundle / "requested-tracks.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    if digest(rows_path) != cfg["tracks_sha256"] or rows != requested_rows(CASES[suffix], speed, dwell):
        raise ValueError("Requested actor or signal tracks changed")
    return {"case_id": cfg["case_id"], "candidate_id": candidate,
            "frames": len(rows), "original_native_observed": False, "delivery_ready": False}


if __name__ == "__main__":
    print(json.dumps({"constructed": len(build()["entries"])}))
