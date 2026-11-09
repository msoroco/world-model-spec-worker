"""Independent curvature, source, policy, and controlled-pair audit."""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = CASE / "case-plan.json"
R = 300.0


def road_arc(station):
    def primitive(u):
        return u * math.sqrt(1 + u * u) + math.asinh(u)
    return 12500 * (primitive(.008) - primitive((200 - station) / 25000))


def independent_ray(subject, eye_station):
    if eye_station is None:
        return None
    eye_angle = eye_station / R
    ox = (R - 1.75) * math.sin(eye_angle)
    oy = R - (R - 1.75) * math.cos(eye_angle)
    oz = .8 * (1 - ((eye_station - 200) / 200) ** 2) + 1.4
    margins = []
    for i in range(101):
        fraction = i / 100
        x = ox + fraction * (subject[0] - ox)
        y = oy + fraction * (subject[1] - oy)
        angle = math.atan2(x, R - y)
        station = R * angle
        offset = R - math.hypot(x, R - y)
        if 0 <= station <= 450 and abs(offset) <= 4.5:
            surface = .8 * (1 - ((station - 200) / 200) ** 2)
            ray_z = oz + fraction * (subject[2] + 1.4 - oz)
            margins.append(surface - ray_z)
    return round(max(margins), 6) if margins else None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan = json.loads(PLAN.read_text())
    source = json.loads(SOURCE.read_text())
    assert plan["source_law_text"] == source["law_record"]["text"]
    assert len([c for c in plan["cases"] if c["case_id"].endswith("__probe_03")]) == 1
    result = json.loads((CASE / "result.json").read_text())
    assert result["status"] == "blocked" and result["candidate_count"] == 12
    entries = json.loads((HERE / "manifest.json").read_text())["entries"]
    assert len(entries) == 4
    checked = saved_checked = 0
    policies = set()
    for entry in entries:
        name = entry["candidate_id"]
        policies.add(name)
        bundle = HERE / "drafts" / "probe_03" / name
        control = CASE / "native" / "crest" / "drafts" / "probe_01" / name
        cfg = json.loads((bundle / "config.json").read_text())
        straight_cfg = json.loads((control / "config.json").read_text())
        assert digest(bundle / "config.json") == entry["config_sha256"]
        assert (bundle / "assignment-source.json").read_bytes() == SOURCE.read_bytes()
        assert (bundle / "case-plan.json").read_bytes() == PLAN.read_bytes()
        assert cfg["source_text"] == source["law_record"]["text"]
        assert cfg["grade_height_m"] == straight_cfg["grade_height_m"] == 0.8
        for key in ("requested_speed_mps", "camera_policy", "stop_before_crest", "rate_hz", "frames"):
            assert cfg[key] == straight_cfg[key]
        curved = ET.parse(bundle / "curve.xodr").getroot()
        straight = ET.parse(control / "crest.xodr").getroot()
        curve_geometry = curved.find(".//planView/geometry")
        assert abs(float(curve_geometry.find("arc").attrib["curvature"]) - 1 / R) < 1e-12
        assert straight.find(".//planView/geometry/line") is not None
        assert ET.tostring(curved.find(".//elevationProfile")) == ET.tostring(straight.find(".//elevationProfile"))
        assert ET.tostring(curved.find(".//lanes")) == ET.tostring(straight.find(".//lanes"))
        curved_rows = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
        straight_rows = [json.loads(line) for line in (control / "requested-tracks.jsonl").read_text().splitlines()]
        raw_path = HERE / "synthetic" / "probe_03" / name / "raw.json"
        saved_path = raw_path.parent / "saved.json"
        raw = json.loads(raw_path.read_text())
        saved = json.loads(saved_path.read_text())
        assert len(curved_rows) == len(straight_rows) == 700
        assert len(raw["rows"]) == 700 and saved["raw_sha256"] == digest(raw_path)
        assert raw["config_sha256"] == digest(bundle / "config.json")
        assert raw["tracks_sha256"] == digest(bundle / "requested-tracks.jsonl")
        assert raw["synthetic"] is True and saved["synthetic"] is True
        assert saved["delivery_ready"] is False and saved["legal_verdict"] is None
        for a, b, measurement in zip(curved_rows, straight_rows, raw["rows"]):
            assert a["frame"] == b["frame"] and a["requested_motion_phase"] == b["requested_motion_phase"]
            s, d, z = b["requested_ego_xyz_m"]
            angle = s / R
            expected = (R * math.sin(angle) - d * math.sin(angle),
                        R * (1 - math.cos(angle)) + d * math.cos(angle))
            assert math.dist(a["requested_ego_xyz_m"][:2], expected) < 1.5e-6
            assert a["requested_ego_xyz_m"][2] == z
            assert abs(a["requested_heading_rad"] - (b["requested_heading_rad"] + angle)) < 1.5e-6
            s, d, z = b["requested_other_vehicle_xyz_m"]
            angle = s / R
            expected = (R * math.sin(angle) - d * math.sin(angle),
                        R * (1 - math.cos(angle)) + d * math.cos(angle))
            assert math.dist(a["requested_other_vehicle_xyz_m"][:2], expected) < 1.5e-6
            assert a["requested_other_vehicle_xyz_m"][2] == z
            checked += 1
            assert measurement["frame"] == a["frame"]
            assert measurement["requested_ego_xyz_m"] == a["requested_ego_xyz_m"]
            assert abs(measurement["subject_road_station_m"] - b["requested_ego_xyz_m"][0]) < 1.5e-6
            for eye, distance, margin in zip(measurement["observer_road_stations_m"],
                                             measurement["observer_road_distances_m"],
                                             measurement["analytic_road_above_ray_m"]):
                if eye is None:
                    assert distance is None and margin is None
                else:
                    subject_s = b["requested_ego_xyz_m"][0]
                    assert abs(abs(road_arc(eye) - road_arc(subject_s)) - 152.4) < .0001
                    assert abs(distance - 152.4) < .0001
                    assert margin == independent_ray(a["requested_ego_xyz_m"], eye)
            saved_checked += 1
    assert policies == {"primary", "fallback1", "fallback2", "fallback3"}
    output = {"format": "c104496-curve-independent-audit-v1", "candidates": len(entries),
              "controlled_straight_pairs": len(entries), "joined_rows": checked,
              "saved_rows_audited": saved_checked,
              "authored_curvature_per_m": 1 / R, "original_native_observed": False,
              "delivery_ready": False}
    (HERE / "independent-audit.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    return output


if __name__ == "__main__":
    print(json.dumps(audit()))
