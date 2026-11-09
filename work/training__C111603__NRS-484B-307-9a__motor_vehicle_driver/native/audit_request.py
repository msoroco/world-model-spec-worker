"""Independent read-only audit of C111603's authored Native requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = json.loads(SOURCE.read_text())
    plan = json.loads((CASE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "manifest.json").read_text())
    text = plan["source_law"]["text"]
    assert sha(SOURCE) == manifest["assignment_sha256"]
    assert source["cell"]["layout"] == "intersection"
    assert source["cell"]["maneuver"] == "turn"
    assert source["cell"]["control"] == "other_vehicle"
    assert len(manifest["entries"]) == 8
    assert manifest["status"] == "draft_not_selected" and not manifest["delivery_ready"]
    matrix = {}
    rows_checked = 0
    for entry in manifest["entries"]:
        suffix = entry["case_id"].split("__")[-1]
        candidate = entry["candidate_id"]
        path = HERE / "drafts" / suffix / candidate
        cfg = json.loads((path / "config.json").read_text())
        assert sha(path / "config.json") == entry["config_sha256"]
        assert (path / "assignment-source.json").read_bytes() == SOURCE.read_bytes()
        assert cfg["source_text"] == text and cfg["assignment_sha256"] == sha(SOURCE)
        assert cfg["case_id"] == entry["case_id"] and cfg["candidate_id"] == candidate
        assert cfg["status"] == "unselected_native_request"
        assert cfg["signal_state_requested_only"] and not cfg["original_native_observed"]
        assert cfg["legal_verdict"] is None and not cfg["delivery_ready"]
        tree = ET.parse(path / "arrow-intersection.xodr").getroot()
        assert sha(path / "arrow-intersection.xodr") == cfg["road_sha256"]
        signals = tree.findall("./road[@id='1']/signals/signal")
        names = {item.attrib["name"] for item in signals}
        assert "south-approach-steady-red-request" in names
        assert "south-approach-green-right-arrow-request" in names
        track = path / "requested-tracks.jsonl"
        assert sha(track) == cfg["tracks_sha256"]
        rows = [json.loads(line) for line in track.read_text().splitlines()]
        assert len(rows) == 480 and [row["frame"] for row in rows] == list(range(480))
        assert all(row["requested_signal"] == {"circular_red": True,
                    "green_arrow": "right", "governs_ego": True} for row in rows)
        assert all(row["original_native_observed"] is False and row["legal_verdict"] is None
                   for row in rows)
        assert sum(row["requested_phase"] == "yield_hold" for row in rows) >= 60
        assert cfg["requested_movement"] == ("right_arrow_turn" if suffix == "witness_1"
                                               else "straight_against_right_arrow")
        synthetic = HERE / "synthetic" / suffix / candidate
        raw = json.loads((synthetic / "raw.json").read_text())
        saved = json.loads((synthetic / "saved.json").read_text())
        assert raw["source_kind"] == "synthetic_cpu_fixture"
        assert raw["config_sha256"] == sha(path / "config.json")
        assert len(raw["rows"]) == len(rows)
        assert saved["row_count"] == 480 and saved["joined_video_frames"] == 480
        assert saved["observed_steady_red_with_green_right_arrow_frames"] == 480
        assert saved["requested_yield_hold_frames"] >= 60
        assert saved["synthetic_cpu_fixture"] and not saved["original_native_observed"]
        assert not saved["signal_state_originally_verified"]
        assert not saved["other_traffic_lawfulness_verified"]
        assert not saved["yield_legally_verified"]
        assert saved["legal_verdict"] is None and not saved["delivery_ready"]
        for index, (request, observed) in enumerate(zip(rows, raw["rows"])):
            assert observed["frame"] == index == observed["video_frame"] == observed["requested_frame"]
            assert observed["observed_signal"] == request["requested_signal"]
            assert observed["observed_ego_xyz_m"] == request["requested_ego_xyz_m"]
            assert observed["observed_other_vehicle_xyz_m"] == request["requested_other_vehicle_xyz_m"]
        matrix[(suffix, candidate)] = (cfg, rows)
        rows_checked += len(rows)
    assert len(matrix) == 8
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        a, ar = matrix[("witness_1", candidate)]
        b, br = matrix[("witness_2", candidate)]
        assert a["road_sha256"] == b["road_sha256"]
        assert a["approach_speed_mps"] == b["approach_speed_mps"]
        assert a["camera_policy"] == b["camera_policy"]
        assert a["pre_approach_dwell_s"] == b["pre_approach_dwell_s"]
        assert all(x["requested_signal"] == y["requested_signal"] and
                   x["requested_other_vehicle_xyz_m"] == y["requested_other_vehicle_xyz_m"]
                   for x, y in zip(ar, br))
        assert ar[-1]["requested_ego_xyz_m"] != br[-1]["requested_ego_xyz_m"]
    result = {"format": "c111603-3079a-independent-request-audit-v1",
              "assignment_id": CASE.name, "candidate_count": 8, "controlled_pairs": 4,
              "requested_rows_checked": rows_checked, "synthetic_saved_rows_checked": rows_checked,
              "source_law_exact": True,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "independent-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
