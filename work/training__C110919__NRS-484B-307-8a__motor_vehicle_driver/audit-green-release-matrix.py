"""Independent source and receipt audit for red-to-green/right-on-red drafts."""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-green-release-execution-manifest.json"
INDEX = HERE / "update026-absent-matrix-index.json"
RUNS = ROOT / ".runtime-work/c110919-update026-absent-matrix"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(index):
    manifest = read(MANIFEST)
    require(index["manifest_sha256"] == sha(MANIFEST) and
            len(index["results"]) == index["candidates"] == 8,
            "Green-release draft matrix incomplete")
    rows = {(row["case_id"], row["candidate_id"]): row for row in index["results"]}
    require(len(rows) == 8, "Duplicate green-release candidate")
    fixed = {}
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        require(suffix in ("green_release_wait", "green_release_red_turn"),
                "Unexpected green-release case")
        wait = suffix == "green_release_wait"
        for ident, candidate in [("primary", entry)] + [(x["id"], x) for x in entry["candidates"]]:
            row = rows[(case_id, ident)]
            proof_path = HERE / row["proof"]
            proof = read(proof_path)
            require(sha(proof_path) == row["sha256"] and
                    proof["manifest_sha256"] == sha(MANIFEST) and
                    proof["construction_sha256"] == candidate["construction_sha256"] ==
                    sha(HERE / candidate["construction"]),
                    "Green-release candidate proof or source changed")
            run = RUNS / suffix / ident
            attempt = run / "compatibility"
            compat = read(attempt / "compatibility.json")
            report_path = attempt / "analysis-report.json"
            report = read(report_path)
            saved_path = run / "saved/v0001/processing.json"
            saved = read(saved_path)
            require(sha(attempt / "compatibility.json") == proof["compatibility_receipt_sha256"] and
                    sha(saved_path) == proof["saved_receipt_sha256"] and
                    compat["passed"] is True and
                    compat["negative_removed"] == "road_geometry.json" and
                    compat["negative_log_sha256"] == sha(attempt / "negative-analysis.log") and
                    compat["analysis_report_sha256"] == sha(report_path),
                    "Green-release positive or negative receipt differs")
            road = read(attempt / "road_geometry.json")
            require(road["stopping_reference_kind"] == "marked_stop_line" and
                    road["stopping_reference_y_m"] == road["stop_line_y_m"] == -14.0 and
                    road["nearest_crosswalk_y_m"] == -11.0 and
                    road["synthetic_diagnostic"] is True and
                    road["native_signal_transition_verified"] is False,
                    "Green-release road or provenance differs")
            xml = ET.fromstring((attempt / "road.xodr").read_text())
            approach = next(x for x in xml.findall("road") if x.attrib["id"] == "1")
            names = {x.attrib.get("name") for x in approach.findall("objects/object")}
            require({"stop-line", "nearest-side-crosswalk"} <= names and
                    len(xml.findall(".//signal[@id='601']")) == 1,
                    "Marked stop reference or governing signal absent")
            samples = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
            require(len(samples) == 480 and
                    all(x["signal_state_observed"] == "Red" for x in samples[:160]) and
                    all(x["signal_state_observed"] == "Green" for x in samples[160:]) and
                    all(x.get("synthetic_diagnostic") is True for x in samples),
                    "Source red-to-green schedule or provenance differs")
            signal = report["measurements"]["steady_red_activation"]["value"]
            stop = report["measurements"]["right_turn_stop"]["value"]
            release = report["measurements"]["green_release"]["value"]
            require(signal["first_green_frame"] == 160 and
                    signal["steady_red_frames"] == 160 and
                    release["first_front_crossing_frame"] == stop["first_front_crossing_frame"] and
                    release["remain_stopped_until_green"] is wait and
                    stop["stationary_pre_crossing_frames"] == (61 if wait else 30) and
                    stop["halt_before_nearest_boundary"] is True,
                    "Saved full-body release comparison differs")
            controls = [(x["walker_center_xy_m"], x["walker_conflict_occupied"])
                        for x in samples]
            signature = (sha(attempt / "road.xodr"), json.dumps(controls),
                         signal["first_green_frame"])
            if ident in fixed:
                require(fixed[ident] == signature,
                        "Comparison changed road, pedestrian schedule or signal timing")
            else:
                fixed[ident] = signature
            required = ("road_geometry.json", "road.xodr", "native_samples.jsonl",
                        "video_frames.jsonl", "overview.mkv", "approach.mkv",
                        "reference_corner.mkv", "driver_reference.mkv")
            require(saved["passed"] is True and saved["originals_preserved"] is True and
                    all(saved["original_source_hashes"].get(name) == sha(attempt / name)
                        for name in required) and
                    saved["physical_acceptance_claimed"] is False and
                    saved["legal_acceptance_claimed"] is False,
                    "Saved source or acceptance status differs")
    return {"format": "c110919-green-release-independent-cpu-audit-v1",
            "manifest_sha256": sha(MANIFEST), "candidates_checked": 8,
            "wait_stopped_frames": 61, "right_on_red_stopped_frames": 30,
            "authored_transition_checked": True, "original_native_transition_verified": False,
            "original_recordings_accepted": 0}


def main():
    index = read(INDEX)
    outcome = audit(index)
    for damage in ("missing", "wrong_sha"):
        changed = copy.deepcopy(index)
        if damage == "missing":
            changed["results"].pop()
        else:
            changed["results"][0]["sha256"] = "0" * 64
        try:
            audit(changed)
        except ValueError:
            pass
        else:
            raise AssertionError("Damaged green-release receipt was accepted")
    outcome["damaged_receipts_rejected"] = 2
    path = HERE / "update026-green-matrix-audit.json"
    path.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"candidates_checked": 8, "damaged_receipts_rejected": 2,
                      "audit_sha256": sha(path)}))


if __name__ == "__main__":
    main()
