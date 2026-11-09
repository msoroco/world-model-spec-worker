"""Independently recompute synthetic crest joins and controlled grade contrast."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from build import CASES, HERE, POLICIES, SOURCE_SHA, put


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / "manifest.json").read_text())
    if len(manifest["entries"]) != 8 or manifest["assignment_sha256"] != SOURCE_SHA or manifest["delivery_ready"]:
        raise ValueError("Construction manifest changed")
    joins = 0
    counts = {}
    for case in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / case / candidate
            raw_path = HERE / "synthetic" / case / candidate / "raw.json"
            saved_path = raw_path.parent / "saved.json"
            config = json.loads((bundle / "config.json").read_text())
            raw = json.loads(raw_path.read_text())
            saved = json.loads(saved_path.read_text())
            if (digest(bundle / "assignment-source.json") != SOURCE_SHA or
                    digest(bundle / "config.json") != raw["config_sha256"] or
                    digest(bundle / "requested-tracks.jsonl") != raw["tracks_sha256"] or
                    digest(raw_path) != saved["raw_sha256"] or
                    saved["original_native_observed"] or not saved["synthetic"] or
                    saved["legal_verdict"] is not None):
                raise ValueError("Source, saved or evidence status drift")
            road = ET.parse(bundle / "crest.xodr").getroot()
            e = road.find("./road/elevationProfile/elevation")
            b, c = float(e.get("b")), float(e.get("c"))
            if abs(b - CASES[case] / 100) > 1e-9 or abs(c + CASES[case] / 40000) > 1e-9:
                raise ValueError("Wrong controlled grade")
            requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
            if len(requests) != 700 or len(raw["rows"]) != 700:
                raise ValueError("Frame count drift")
            turn = clear = blocked = 0
            for request, row in zip(requests, raw["rows"]):
                if row["frame"] != request["frame"] or row["requested_ego_xyz_m"] != request["requested_ego_xyz_m"]:
                    raise ValueError("Request/raw actor join drift")
                x = request["requested_ego_xyz_m"][0]
                # For a quadratic grade, maximum surface-to-eye-ray bulge is
                # -c * D^2/4 - eye height when observer and body samples match.
                analytic_gap = round(-c * 152.4 ** 2 / 4 - 1.4, 6)
                if row["analytic_road_above_ray_m"] != [analytic_gap, analytic_gap]:
                    raise ValueError("Independent analytic ray mismatch")
                joins += 1
                if request["requested_motion_phase"] in ("forward_left", "reverse_right", "forward_left_finish"):
                    turn += 1
                    clear += analytic_gap <= 0
                    blocked += analytic_gap > 0
            if (turn != saved["turn_frames"] or clear != saved["analytic_both_clear_turn_frames"] or
                    blocked != saved["analytic_road_above_ray_turn_frames"]):
                raise ValueError("Independent saved totals mismatch")
            counts[case + "/" + candidate] = {"turn": turn, "clear": clear, "road_above_ray": blocked}
    if counts["probe_01/primary"]["clear"] != 100 or counts["probe_02/primary"]["road_above_ray"] != 100:
        raise ValueError("Controlled grade contrast absent")
    result = {"format": "c104496-independent-synthetic-audit-v1", "request_raw_joins": joins,
              "cases": counts, "controlled_variable": "quadratic_grade_height_at_s200_m",
              "fixed": ["plan_view", "lanes", "maneuver", "actor", "20_hz", "700_frames"],
              "synthetic_only": True, "original_native_observed": False, "delivery_ready": False}
    put(HERE / "independent-audit.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(audit()))
