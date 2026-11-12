"""Independent source audit of the exact synthetic timing-sweep matrix."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update041-traffic-timing-sweep-manifest.json"
INDEX = HERE / "update047-traffic-timing-sweep-matrix-index.json"
STAGE = HERE / "proposals/right-of-way-sweep-candidate.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def occupied(body):
    require(isinstance(body, list) and len(body) == 4, "Missing full-body footprint")
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    return max(xs) >= 8 and min(xs) <= 12 and max(ys) >= -4 and min(ys) <= 4


def source_frames(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path)],
        text=True, capture_output=True, check=True)
    return int(result.stdout.strip())


def audit(index, manifest):
    require(index["manifest_sha256"] == sha(MANIFEST) and
            index["stage_sha256"] == sha(STAGE) and
            index["candidate_count"] == 20 and len(index["results"]) == 20,
            "Final timing matrix identity differs")
    stage = read(STAGE)
    exact = {c["case_id"]: c for c in stage["cases"]
             if c.get("sweep_id") == "C110919-right-of-way"}
    require(len(exact) == 5 and len(manifest["cases"]) == 5, "Exact timing cases missing")
    refs = {}
    for entry in manifest["cases"]:
        ident = entry["case_id"]
        require(ident in exact and entry["authored_traffic_launch_frame"] ==
                exact[ident]["sweep_point"]["traffic_launch_frame"],
                "Exact timing assignment differs")
        candidates = [("primary", entry)] + [(x["id"], x) for x in entry["candidates"]]
        require([name for name, _ in candidates] ==
                ["primary", "fallback1", "fallback2", "fallback3"],
                "Candidate set differs")
        require(len({tuple(x["changed_knobs"]) for x in entry["candidates"]}) == 3 and
                len({x["trigger"]["metric"] for x in entry["candidates"]}) == 3,
                "Fallback physical-risk triggers are not distinct")
        for name, ref in candidates:
            require(sha(HERE / ref["construction"]) == ref["construction_sha256"],
                    "Exact construction hash differs")
            refs[ident, name] = ref
    seen = set()
    source_hashes = []
    for item in index["results"]:
        ident, name = item["case_id"], item["candidate_id"]
        require((ident, name) in refs and (ident, name) not in seen,
                "Missing or duplicate candidate receipt")
        seen.add((ident, name))
        run = ROOT / ".runtime-work/c110919-update047-timing-matrix" / sha(MANIFEST)[:12] / ident / name
        comp = run / "compatibility"
        saved_dir = run / "saved/v0001"
        compatibility = read(comp / "compatibility.json")
        saved = read(saved_dir / "processing.json")
        result = read(comp / "result.json")
        report = read(comp / "analysis-report.json")
        require(item["construction_sha256"] == refs[ident, name]["construction_sha256"] and
                item["compatibility_receipt_sha256"] == sha(comp / "compatibility.json") and
                item["saved_receipt_sha256"] == sha(saved_dir / "processing.json"),
                "Candidate receipt source hash differs")
        require(compatibility["passed"] is True and
                compatibility["negative_removed"] == "road_geometry.json" and
                compatibility["case_id"] == ident and compatibility["candidate_id"] == name and
                compatibility["construction_sha256"] == item["construction_sha256"] and
                saved["passed"] is True and saved["case_id"] == ident and
                saved["candidate_id"] == name and saved["originals_preserved"] is True and
                saved["timestamp_joins"]["passed"] is True and
                saved["physical_acceptance_claimed"] is False and
                saved["legal_acceptance_claimed"] is False,
                "Pinned positive/negative/saved receipt differs")
        require(result["provenance_kind"] == "synthetic_local_diagnostic" and
                result["diagnostic_fixture"] is True and result["accepted"] is False and
                result["legal_verdict_claimed"] is False,
                "Synthetic diagnostic promoted as original")
        raw = comp / "native_samples.jsonl"
        rows = [json.loads(line) for line in raw.read_text().splitlines()]
        frame = entry_frame = int(exact[ident]["sweep_point"]["traffic_launch_frame"])
        require(len(rows) == 480 and
                all(row.get("traffic_launch_frame") == frame and
                    row.get("synthetic_diagnostic") is True and
                    row.get("speed_provenance") == "synthetic_native_sample" and
                    row.get("other_traffic_signal_state_observed") == "Green" and
                    row.get("signal_state_observed") == "Red"
                    for row in rows),
                "Selected launch, signals or synthetic provenance differ")
        traffic = [i for i, row in enumerate(rows) if occupied(row["other_traffic_body_xy_m"])]
        ego = [i for i, row in enumerate(rows) if occupied(row["native_body_xy_m"])]
        require(traffic and ego and
                all(row["traffic_conflict_occupied"] == (i in traffic)
                    for i, row in enumerate(rows)),
                "Native body conflict occupancy differs")
        timing = report["measurements"]["traffic_timing_sweep"]["value"]
        require(timing["authored_launch_frame"] == frame and
                timing["observed_traffic_first_frame"] == traffic[0] and
                timing["observed_traffic_last_frame"] == traffic[-1] and
                timing["observed_ego_first_frame"] == ego[0] and
                timing["ego_minus_traffic_entry_s"] == round((ego[0] - traffic[0]) / 20, 3) and
                timing["observed_overlap_frames"] == sorted(set(traffic) & set(ego)) and
                timing["legal_right_of_way_verdict"] is None and
                report["measurements"]["traffic_timing_sweep"]["sources"]["native_samples.jsonl"] == sha(raw) and
                saved["original_source_hashes"]["native_samples.jsonl"] == sha(raw),
                "Source-measured timing or saved source hash differs")
        require({x["name"] for x in result["recording_evidence"]} >=
                {"ego_entry_relative_to_signal_directed_traffic", "traffic_launch_frame",
                 "directed_traffic_signal_and_lane", "four_source_cameras",
                 "native_pedestrian_paths", "native_other_traffic_paths",
                 "signal_state_observed", "surveyed_C110919_intersection"} and
                result["realized_observables"]["ego_entry_relative_to_signal_directed_traffic"]["value"] ==
                timing["ego_minus_traffic_entry_s"],
                "Timing recording evidence missing")
        require(set(result["video_references"]) == {name + ".mkv" for name in CAMERAS},
                "Four source cameras missing")
        for camera in CAMERAS:
            path = comp / (camera + ".mkv")
            require(sha(path) == compatibility["fixture_manifest"][camera + ".mkv"] and
                    source_frames(path) == 480, "Source camera hash or frame count differs")
        source_hashes.append(sha(raw))
    require(seen == set(refs), "Incomplete twenty-candidate matrix")
    return {"cases": 5, "candidates": 20, "distinct_native_source_hashes": len(set(source_hashes)),
            "original_native_accepted": False}


def main():
    manifest, index = read(MANIFEST), read(INDEX)
    positive = audit(index, manifest)
    negatives = {}
    for name, change in (
        ("wrong_manifest_hash", lambda x: x.__setitem__("manifest_sha256", "0" * 64)),
        ("missing_candidate", lambda x: x["results"].pop()),
        ("wrong_source_hash", lambda x: x["results"][0].__setitem__("saved_receipt_sha256", "0" * 64)),
    ):
        damaged = copy.deepcopy(index)
        change(damaged)
        try:
            audit(damaged, manifest)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("Damaged matrix was accepted: " + name)
    output = {"format": "c110919-timing-sweep-independent-audit-v1",
              "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
              "positive": positive, "negative_rejections": negatives}
    path = HERE / "update047-traffic-timing-sweep-audit.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"candidates": 20, "negative_rejections": len(negatives),
                      "audit_sha256": sha(path), "original_native_accepted": False}))


if __name__ == "__main__":
    main()
