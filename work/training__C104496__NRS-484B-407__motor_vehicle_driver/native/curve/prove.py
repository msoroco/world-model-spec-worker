"""Source-pinned curved-grade reversal requests and independent CPU geometry proof."""
import copy
import hashlib
import json
import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
spec = importlib.util.spec_from_file_location("c104496_crest_build", HERE.parent / "crest" / "build.py")
crest_build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crest_build)
POLICIES, RATE, FRAMES, SOURCE_SHA = (crest_build.POLICIES, crest_build.RATE,
                                     crest_build.FRAMES, crest_build.SOURCE_SHA)
elevation, put, rows = crest_build.elevation, crest_build.put, crest_build.rows

RADIUS = 300.0
CURVATURE = 1.0 / RADIUS
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = CASE / "case-plan.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def curve_point(station, offset):
    angle = station / RADIUS
    return (RADIUS * math.sin(angle) - offset * math.sin(angle),
            RADIUS * (1 - math.cos(angle)) + offset * math.cos(angle))


def inverse_point(x, y):
    angle = math.atan2(x, RADIUS - y)
    station = RADIUS * angle
    radial = math.hypot(x, RADIUS - y)
    offset = RADIUS - radial
    return station, offset


def road():
    # Same 0.8 m quadratic grade as the straight-road control; plan curvature varies.
    text = crest_build.road(0.8)
    text = text.replace('name="C104496 authored grade crest"', 'name="C104496 authored curved grade crest"')
    text = text.replace('<line/>', f'<arc curvature="{CURVATURE:.15f}"/>')
    return text


def transformed_rows(candidate):
    result = []
    for source_row in rows("probe_01", candidate):
        row = copy.deepcopy(source_row)
        station, offset, z = row["requested_ego_xyz_m"]
        x, y = curve_point(station, offset)
        row["requested_ego_xyz_m"] = [round(x, 6), round(y, 6), z]
        row["requested_heading_rad"] = round(row["requested_heading_rad"] + station / RADIUS, 6)
        station, offset, z = row["requested_other_vehicle_xyz_m"]
        x, y = curve_point(station, offset)
        row["requested_other_vehicle_xyz_m"] = [round(x, 6), round(y, 6), z]
        row.pop("other_approach_virtual_camera_x_m")
        row["other_approach_virtual_camera_road_station_m"] = 352.4
        result.append(row)
    return result


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen assignment changed")
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    law = source["law_record"]["text"]
    if (plan["source_law_text"] != law or source["actor"] != "motor_vehicle_driver" or
            {k: source["cell"][k] for k in ("layout", "maneuver", "control")} !=
            {"layout": "hill_crest", "maneuver": "u_turn", "control": "other_vehicle"}):
        raise ValueError("Source mismatch")
    entries = []
    for candidate, (speed, camera, stop) in POLICIES.items():
        bundle = HERE / "drafts" / "probe_03" / candidate
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "assignment-source.json").write_bytes(SOURCE.read_bytes())
        (bundle / "case-plan.json").write_bytes(PLAN.read_bytes())
        (bundle / "curve.xodr").write_text(road())
        track = bundle / "requested-tracks.jsonl"
        track.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in transformed_rows(candidate)))
        cfg = {"format": "c104496-curve-request-v1", "assignment_id": CASE.name,
               "case_id": CASE.name + "__probe_03", "candidate_id": candidate,
               "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
               "road_sha256": sha(bundle / "curve.xodr"), "tracks_sha256": sha(track),
               "source_text": law, "rate_hz": RATE, "frames": FRAMES,
               "curve_radius_m": RADIUS, "curve_station_m": 200,
               "grade_height_m": 0.8, "requested_speed_mps": speed,
               "camera_policy": camera, "stop_before_crest": stop,
               "other_vehicle_blueprint": "vehicle.audi.a2",
               "ego_blueprint": "vehicle.tesla.model3",
               "status": "unselected_native_request", "original_native_observed": False,
               "legal_verdict": None}
        put(bundle / "config.json", cfg)
        entries.append({"candidate_id": candidate, "config_sha256": sha(bundle / "config.json")})
    manifest = {"format": "c104496-curve-construction-v1", "assignment_id": CASE.name,
                "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
                "status": "draft_not_selected", "delivery_ready": False, "entries": entries}
    put(HERE / "manifest.json", manifest)
    return manifest


def check(bundle):
    cfg = json.loads((bundle / "config.json").read_text())
    candidate = cfg["candidate_id"]
    if candidate not in POLICIES or (bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or (bundle / "case-plan.json").read_bytes() != PLAN.read_bytes():
        raise ValueError("Source bytes mismatch")
    expected_road = road()
    if (bundle / "curve.xodr").read_text() != expected_road or cfg["road_sha256"] != sha(bundle / "curve.xodr"):
        raise ValueError("Authored curve geometry mismatch")
    geometry = ET.fromstring(expected_road).find(".//planView/geometry")
    if abs(float(geometry.find("arc").attrib["curvature"]) - CURVATURE) > 1e-12:
        raise ValueError("Curvature mismatch")
    if (cfg["assignment_sha256"] != SOURCE_SHA or cfg["case_plan_sha256"] != sha(PLAN) or
            cfg["source_text"] != json.loads(SOURCE.read_text())["law_record"]["text"] or
            cfg["status"] != "unselected_native_request" or cfg["original_native_observed"] is not False or
            cfg["legal_verdict"] is not None or cfg["curve_radius_m"] != RADIUS or
            cfg["grade_height_m"] != 0.8 or cfg["camera_policy"] != POLICIES[candidate][1] or
            cfg["requested_speed_mps"] != POLICIES[candidate][0] or
            cfg["stop_before_crest"] != POLICIES[candidate][2]):
        raise ValueError("Config mismatch")
    path = bundle / "requested-tracks.jsonl"
    if cfg["tracks_sha256"] != sha(path):
        raise ValueError("Track hash mismatch")
    actual = [json.loads(line) for line in path.read_text().splitlines()]
    expected = transformed_rows(candidate)
    if actual != expected or len(actual) != FRAMES:
        raise ValueError("Track geometry or source join mismatch")
    for row in actual:
        station, offset = inverse_point(*row["requested_ego_xyz_m"][:2])
        if abs(elevation(station, 0.8) - row["requested_ego_xyz_m"][2]) > 1e-4 or not -5 < offset < 5:
            raise ValueError("Curve station/elevation mismatch")
    return len(actual)


def prove():
    entries = build()["entries"]
    positives = negatives = 0
    for entry in entries:
        bundle = HERE / "drafts" / "probe_03" / entry["candidate_id"]
        check(bundle)
        positives += 1
        for name, mutated in (("curve.xodr", road().replace(f'{CURVATURE:.15f}', "0.004000000000000")),
                              ("assignment-source.json", "{}"),
                              ("requested-tracks.jsonl", "{}\n")):
            with tempfile.TemporaryDirectory() as temp:
                dst = Path(temp)
                for path in bundle.iterdir():
                    (dst / path.name).write_bytes(path.read_bytes())
                (dst / name).write_text(mutated)
                if name != "assignment-source.json":
                    cfg = json.loads((dst / "config.json").read_text())
                    cfg["road_sha256" if name == "curve.xodr" else "tracks_sha256"] = sha(dst / name)
                    put(dst / "config.json", cfg)
                try:
                    check(dst)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Rehashed mutation accepted: " + name)
    result = {"format": "c104496-curve-request-proof-v1", "positive_count": positives,
              "negative_count": negatives, "verified_rows": positives * FRAMES,
              "curve_radius_m": RADIUS, "controlled_grade_height_m": 0.8,
              "straight_control_case_id": CASE.name + "__probe_01",
              "original_native_observed": False, "delivery_ready": False}
    put(HERE / "request-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
