"""Independent hash/source audit of ten selected ordinary CPU packages."""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update058-selected-ordinary-manifest.json"
INDEX = HERE / "update058-selected-ordinary-matrix-index.json"
RUNS = ROOT / ".runtime-work/c110919-update058-selected-ordinary-matrix"
PROOFS = HERE / "selected_ordinary_cases/receipts"
ORDER = ("reference", "contrast", "absent_reference", "absent_reference_contrast",
         "green_release_wait", "green_release_red_turn", "yield_wait",
         "yield_conflict_entry", "traffic_yield_wait",
         "traffic_conflict_entry")
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
           "trace.jsonl", "road_geometry.json", "road.xodr", "overview.mkv",
           "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(index):
    manifest = read(MANIFEST)
    digest = sha(MANIFEST)
    require(manifest["stage_sha256"] == sha(HERE / "proposals/cases.json"),
            "Selected ordinary semantic stage changed")
    require(index["manifest_sha256"] == digest and index["cases"] == 10 and
            index["candidates"] == len(index["results"]) == 40 and
            index["stage_sha256"] == manifest["stage_sha256"] and
            index["original_native_accepted"] is False,
            "Ten-case probe index incomplete or claimed acceptance")
    rows = {(row["case_id"], row["candidate_id"]): row for row in index["results"]}
    require(len(rows) == 40, "Duplicate exact candidate")
    require([row["case_id"].removeprefix(HERE.name + "__") for row in manifest["cases"]]
            == list(ORDER), "Ten-case manifest order changed")
    checked = 0
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        for ident, candidate in [("primary", entry)] + [(item["id"], item)
                                                      for item in entry["candidates"]]:
            row = rows.get((case_id, ident))
            require(row is not None, "Exact candidate receipt absent")
            proof_path = HERE / row["proof"]
            proof = read(proof_path)
            require(sha(proof_path) == row["sha256"] and
                    proof["case_id"] == case_id and proof["candidate_id"] == ident and
                    proof["manifest_sha256"] == digest and
                    proof["construction_sha256"] == candidate["construction_sha256"] ==
                    sha(HERE / candidate["construction"]) and
                    proof["original_native_accepted"] is False,
                    "Final-hash candidate proof changed")
            run = RUNS / digest[:12] / suffix / ident
            attempt = run / "compatibility"
            compat_path = attempt / "compatibility.json"
            compat = read(compat_path)
            report_path = attempt / "analysis-report.json"
            saved_path = run / "saved/v0001/processing.json"
            saved = read(saved_path)
            require(sha(compat_path) == proof["compatibility_receipt_sha256"] and
                    sha(saved_path) == proof["saved_receipt_sha256"] and
                    all(sha(PROOFS / suffix / ident / name) == proof[key] for name, key in
                        (("offline.log", "offline_log_sha256"),
                         ("compatibility.log", "compatibility_log_sha256"),
                         ("process-saved.log", "process_saved_log_sha256"))) and
                    compat["passed"] is True and compat["case_id"] == case_id and
                    compat["candidate_id"] == ident and
                    compat["construction_sha256"] == candidate["construction_sha256"] and
                    compat["negative_removed"] == "road_geometry.json" and
                    compat["negative_log_sha256"] == sha(attempt / "negative-analysis.log") and
                    compat["analysis_report_sha256"] == sha(report_path) and
                    saved["passed"] is True and saved["case_id"] == case_id and
                    saved["candidate_id"] == ident and
                    saved["originals_preserved"] is True and
                    saved["timestamp_joins"]["passed"] is True and
                    saved["physical_acceptance_claimed"] is False and
                    saved["legal_acceptance_claimed"] is False,
                    "Pinned compatibility or saved-processing receipt changed")
            require(all(saved["original_source_hashes"].get(name) == sha(attempt / name)
                        for name in SOURCES), "Retained original-shaped source changed")
            road = read(attempt / "road_geometry.json")
            result = read(attempt / "result.json")
            evidence = {item["name"]: item for item in result["recording_evidence"]}
            for name in ("four_source_cameras", "surveyed_C110919_intersection"):
                require(name in evidence and evidence[name]["unit"] ==
                        ("video" if name == "four_source_cameras" else "structured"),
                        "Selected Native/camera context evidence missing")
            camera_context = read(attempt / evidence["four_source_cameras"]["reference"])
            road_context = read(attempt / evidence["surveyed_C110919_intersection"]["reference"])
            require(set(camera_context["four_source_cameras"]) ==
                    {name + ".mkv" for name in
                     ("overview", "approach", "reference_corner", "driver_reference")} and
                    set(camera_context["four_source_cameras"].values()) == {480} and
                    road_context["surveyed_C110919_intersection"]["native_map_sha256"] ==
                    road["native_map_sha256"],
                    "Selected camera or surveyed intersection source context differs")
            xml = ET.fromstring((attempt / "road.xodr").read_text())
            approach = next(x for x in xml.findall("road") if x.attrib["id"] == "1")
            require(len(xml.findall(".//signal[@id='601']")) == 1,
                    "Authored governing signal missing")
            if suffix.startswith("absent_reference"):
                require(road["stopping_reference_kind"] == "intersection_boundary" and
                        road["stopping_reference_y_m"] == -7.0 and
                        road.get("stop_line_y_m") is None and
                        road.get("nearest_crosswalk_y_m") is None and
                        not approach.findall("objects/object") and
                        road["native_absence_observed"] is False,
                        "Absent-reference authored road or provenance changed")
            else:
                names = {x.attrib.get("name") for x in approach.findall("objects/object")}
                require(road["stop_line_y_m"] == -14.0 and
                        road["nearest_crosswalk_y_m"] == -11.0 and
                        {"stop-line", "nearest-side-crosswalk"} <= names,
                        "Marked stopping reference changed")
                if suffix.startswith("green_release"):
                    require(road["stopping_reference_kind"] == "marked_stop_line" and
                            road["stopping_reference_y_m"] == -14.0 and
                            road["native_signal_transition_verified"] is False,
                            "Authored green-release road claimed original transition")
            samples = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
            require(len(samples) == 480 and all(row.get("synthetic_diagnostic") is True and
                    row.get("speed_provenance") == "synthetic_native_sample"
                    for row in samples), "Synthetic provenance or frame count changed")
            expected = ["Red"] * 160 + ["Green"] * 320 if suffix.startswith("green_release") else ["Red"] * 480
            require([row["signal_state_observed"] for row in samples] == expected,
                    "Authored signal schedule changed")
            if suffix.startswith("yield_"):
                occupied = [i for i, sample in enumerate(samples)
                            if sample["walker_conflict_occupied"]]
                require(occupied == list(range(220, 261)),
                        "Authored pedestrian conflict window changed")
            if suffix.startswith("traffic_"):
                require({item.attrib["id"] for item in xml.findall(".//signal")} ==
                        {"601", "602"} and
                        road.get("cross_traffic_signal_actor_id") == 602 and
                        road.get("lanes", {}).get("west_traffic_right", {}).get("lane_id") == -1,
                        "Separate directed cross-traffic signal or lane missing")
                occupied = [i for i, sample in enumerate(samples)
                            if sample.get("traffic_conflict_occupied")]
                require(occupied == list(range(220, 261)) and
                        all(sample.get("other_traffic_signal_state_observed") == "Green"
                            for sample in samples),
                        "Directed green traffic conflict window changed")
            checked += 1
    return {"format": "c110919-selected-ordinary-independent-cpu-audit-v1",
            "manifest_sha256": digest, "candidates_checked": checked,
            "authored_road_and_signal_checked": True,
            "original_native_or_pixel_acceptance": False}


def main():
    index = read(INDEX)
    outcome = audit(index)
    negatives = {}
    for name in ("missing", "wrong_sha", "wrong_manifest", "promoted_original"):
        changed = copy.deepcopy(index)
        if name == "missing":
            changed["results"].pop()
        elif name == "wrong_sha":
            changed["results"][0]["sha256"] = "0" * 64
        elif name == "wrong_manifest":
            changed["manifest_sha256"] = "0" * 64
        else:
            changed["original_native_accepted"] = True
        try:
            audit(changed)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("Damaged ten-case index was accepted: " + name)
    outcome["negative_rejections"] = negatives
    path = HERE / "update058-selected-ordinary-matrix-audit.json"
    path.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps({"candidates_checked": 40, "negative_rejections": len(negatives),
                      "audit_sha256": sha(path), "canonical_selected": True}))


if __name__ == "__main__":
    main()
