"""Independent receipt and source audit for the absent-reference pair."""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-absent-reference-execution-manifest.json"
INDEX = HERE / "update025-absent-matrix-index.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(index):
    manifest = read(MANIFEST)
    require(index["manifest_sha256"] == sha(MANIFEST) and index["candidates"] ==
            len(index["results"]) == 8, "Absent-reference matrix incomplete")
    rows = {(row["case_id"], row["candidate_id"]): row for row in index["results"]}
    require(len(rows) == 8, "Duplicate absent-reference candidate")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        require(suffix in ("absent_reference", "absent_reference_contrast"),
                "Unexpected absent-reference case")
        for ident, candidate in [("primary", entry)] + [(c["id"], c) for c in entry["candidates"]]:
            row = rows[(entry["case_id"], ident)]
            proof_path = HERE / row["proof"]
            proof = read(proof_path)
            require(sha(proof_path) == row["sha256"] and
                    proof["manifest_sha256"] == sha(MANIFEST) and
                    proof["construction_sha256"] == candidate["construction_sha256"] ==
                    sha(HERE / candidate["construction"]),
                    "Absent-reference exact candidate proof changed")
            run = ROOT / ".runtime-work/c110919-update025-absent-matrix" / suffix / ident
            attempt = run / "compatibility"
            compat = read(attempt / "compatibility.json")
            saved_path = run / "saved/v0001/processing.json"
            saved = read(saved_path)
            require(sha(attempt / "compatibility.json") == proof["compatibility_receipt_sha256"] and
                    sha(saved_path) == proof["saved_receipt_sha256"] and
                    compat["passed"] is True and compat["negative_removed"] == "road_geometry.json" and
                    compat["negative_log_sha256"] == sha(attempt / "negative-analysis.log"),
                    "Absent-reference compatibility positive/negative changed")
            road_path = attempt / "road_geometry.json"
            road = read(road_path)
            require(road.get("stopping_reference_kind") == "intersection_boundary" and
                    road.get("stopping_reference_y_m") == -7.0 and
                    road.get("stop_line_y_m") is None and
                    road.get("nearest_crosswalk_y_m") is None and
                    road.get("synthetic_diagnostic") is True and
                    road.get("native_absence_observed") is False,
                    "Absent-reference road source changed or claimed Native absence")
            xml = ET.fromstring((attempt / "road.xodr").read_text())
            approach = next(x for x in xml.findall("road") if x.attrib["id"] == "1")
            require(not approach.findall("objects/object") and
                    len(xml.findall(".//signal[@id='601']")) == 1,
                    "Authored approach has a stop object or no signal")
            measurement = compat["measurement_examples"]["right_turn_stop"]["value"]
            expected = suffix == "absent_reference"
            require(measurement["stopping_reference_y_m"] == -7.0 and
                    measurement["stationary_pre_crossing_frames"] == (30 if expected else 0) and
                    measurement["halt_before_nearest_boundary"] is expected,
                    "Absent-reference saved measurement differs")
            required = ("road_geometry.json", "road.xodr", "native_samples.jsonl",
                        "video_frames.jsonl", "overview.mkv", "approach.mkv",
                        "reference_corner.mkv", "driver_reference.mkv")
            require(saved["passed"] is True and saved["originals_preserved"] is True and
                    all(saved["original_source_hashes"].get(name) == sha(attempt / name)
                        for name in required) and
                    saved["physical_acceptance_claimed"] is False and
                    saved["legal_acceptance_claimed"] is False,
                    "Saved original source or acceptance status differs")
    return {"format": "c110919-absent-reference-independent-cpu-audit-v1",
            "manifest_sha256": sha(MANIFEST), "candidates_checked": 8,
            "reference_stopped_frames": 30, "contrast_stopped_frames": 0,
            "authored_absence_verified": True, "original_native_absence_verified": False,
            "original_recordings_accepted": 0}


def main():
    index = read(INDEX)
    result = audit(index)
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
            raise AssertionError("Damaged absent-reference receipt was accepted")
    result["damaged_receipts_rejected"] = 2
    path = HERE / "update025-absent-matrix-audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"candidates_checked": 8, "damaged_receipts_rejected": 2,
                      "audit_sha256": sha(path)}))


if __name__ == "__main__":
    main()
