"""Independently verify selected sweep identity and all pinned CPU receipts."""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update057-qualified-sweep-manifest.json"
INDEX = HERE / "update057-qualified-sweep-matrix-index.json"
STAGE = HERE / "proposals/cases.json"
RUNS = ROOT / ".runtime-work/c110919-update057-qualified-matrix"
LOGS = HERE / "qualified_sweep_cases/receipts"
sys.path.insert(0, str(HERE / "native"))
from extreme_right_sweep import measure_approach


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def audit(index, manifest):
    stage = read(STAGE)
    plan = read(HERE / "case-plan.json")
    exact = {c["case_id"]: c for c in stage["cases"] if c.get("sweep_id")}
    require(index["manifest_sha256"] == sha(MANIFEST) and
            index["stage_sha256"] == sha(STAGE) and
            index["candidate_count"] == 40 and len(index["results"]) == 40,
            "Qualified matrix identity differs")
    require(len(exact) == 10 and len(manifest["cases"]) == 10 and
            set(exact) <= {c["case_id"] for c in plan["cases"]},
            "Qualified sweep cases missing from plan")
    refs = {}
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        require(cid in exact and cid.startswith(HERE.name + "__"),
                "Unqualified or undefined selected sweep case")
        case = exact[cid]
        axis = next(iter(case["sweep_point"]))
        if axis == "traffic_launch_frame":
            require(entry["authored_traffic_launch_frame"] == case["sweep_point"][axis],
                    "Authored timing setpoint differs")
        else:
            require(entry["authored_lateral_right_offset_m"] == case["sweep_point"][axis],
                    "Authored lateral setpoint differs")
        candidates = [("primary", entry)] + [(x["id"], x) for x in entry["candidates"]]
        require([name for name, _ in candidates] ==
                ["primary", "fallback1", "fallback2", "fallback3"],
                "Candidate set differs")
        require(len({tuple(x["changed_knobs"]) for x in entry["candidates"]}) == 3 and
                len({x["trigger"]["metric"] for x in entry["candidates"]}) == 3,
                "Physical-risk fallback triggers are not distinct")
        for name, ref in candidates:
            require(sha(HERE / ref["construction"]) == ref["construction_sha256"],
                    "Candidate construction changed")
            refs[cid, name] = (ref, case)
    seen = set()
    primaries = {"traffic_launch_frame": [], "lateral_right_offset_m": []}
    for item in index["results"]:
        cid, name = item["case_id"], item["candidate_id"]
        require((cid, name) in refs and (cid, name) not in seen,
                "Missing or duplicate exact candidate receipt")
        seen.add((cid, name))
        ref, case = refs[cid, name]
        run = RUNS / sha(MANIFEST)[:12] / cid / name
        log = LOGS / cid / name
        comp = run / "compatibility"
        compatible = read(comp / "compatibility.json")
        saved = read(run / "saved/v0001/processing.json")
        result = read(comp / "result.json")
        report = read(comp / "analysis-report.json")
        require(item["construction_sha256"] == ref["construction_sha256"] and
                item["offline_log_sha256"] == sha(log / "offline.log") and
                item["compatibility_receipt_sha256"] == sha(comp / "compatibility.json") and
                item["compatibility_log_sha256"] == sha(log / "compatibility.log") and
                item["saved_receipt_sha256"] == sha(run / "saved/v0001/processing.json") and
                item["saved_log_sha256"] == sha(log / "process-saved.log"),
                "Pinned CPU source hash differs")
        require(compatible["passed"] is True and
                compatible["negative_removed"] == "road_geometry.json" and
                compatible["case_id"] == cid and compatible["candidate_id"] == name and
                compatible["construction_sha256"] == ref["construction_sha256"] and
                saved["passed"] is True and saved["case_id"] == cid and
                saved["candidate_id"] == name and saved["originals_preserved"] is True and
                saved["timestamp_joins"]["passed"] is True and
                saved["physical_acceptance_claimed"] is False and
                saved["legal_acceptance_claimed"] is False and
                result["provenance_kind"] == "synthetic_local_diagnostic" and
                result["diagnostic_fixture"] is True and result["accepted"] is False and
                result["legal_verdict_claimed"] is False,
                "Compatibility, saved processing or provenance differs")
        raw = comp / "native_samples.jsonl"
        rows = [json.loads(line) for line in raw.read_text().splitlines()]
        require(len(rows) == 480 and all(row.get("synthetic_diagnostic") is True and
                row.get("speed_provenance") == "synthetic_native_sample" for row in rows) and
                saved["original_source_hashes"]["native_samples.jsonl"] == sha(raw),
                "Native source or synthetic provenance differs")
        for camera in ("overview", "approach", "reference_corner", "driver_reference"):
            path = comp / (camera + ".mkv")
            require(sha(path) == compatible["fixture_manifest"][camera + ".mkv"],
                    "Four source cameras changed")
        axis, point = next(iter(case["sweep_point"].items()))
        require(all(row[axis] == point for row in rows),
                "Native authored sweep setpoint differs")
        if axis == "lateral_right_offset_m":
            measured = measure_approach(rows, read(comp / "road_geometry.json"))
            observation = report["measurements"]["extreme_right_lateral_sweep"]
            require(observation["value"] == measured and
                    observation["sources"]["native_samples.jsonl"] == sha(raw) and
                    measured["legal_extreme_right_verdict"] is None,
                    "Full-body lateral measurement differs")
            value = measured["minimum_right_edge_clearance_m"]
        else:
            observation = report["measurements"]["traffic_timing_sweep"]
            require(observation["value"]["authored_launch_frame"] == point and
                    observation["sources"]["native_samples.jsonl"] == sha(raw) and
                    observation["value"]["legal_right_of_way_verdict"] is None,
                    "Traffic timing measurement differs")
            value = observation["value"]["ego_minus_traffic_entry_s"]
        if name == "primary":
            primaries[axis].append((point, value))
    require(seen == set(refs), "Incomplete qualified forty-candidate matrix")
    lateral = sorted(primaries["lateral_right_offset_m"])
    timing = sorted(primaries["traffic_launch_frame"])
    require([round(value, 3) for _, value in lateral] == [.65, .5, .35, .2, .05] and
            len({value for _, value in timing}) == 5,
            "Physical sweep comparison does not vary as planned")
    return {"cases": 10, "candidate_bundles": 40,
            "primary_timing_measurements": timing,
            "primary_lateral_measurements": lateral,
            "original_native_accepted": False}


def main():
    manifest, index = read(MANIFEST), read(INDEX)
    positive = audit(index, manifest)
    negatives = {}
    for label, change in (
        ("wrong_manifest", lambda x: x.__setitem__("manifest_sha256", "0" * 64)),
        ("missing_candidate", lambda x: x["results"].pop()),
        ("wrong_saved_hash", lambda x: x["results"][0].__setitem__("saved_receipt_sha256", "0" * 64))):
        damaged = copy.deepcopy(index)
        change(damaged)
        try:
            audit(damaged, manifest)
        except ValueError as error:
            negatives[label] = str(error)
        else:
            raise AssertionError("Damaged exact matrix accepted: " + label)
    proof = {"format": "c110919-qualified-sweep-independent-audit-v1",
             "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
             "positive": positive, "negative_rejections": negatives}
    path = HERE / "update057-qualified-sweep-audit.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": 10, "candidates": 40,
                      "negative_rejections": len(negatives), "audit_sha256": sha(path)}))


if __name__ == "__main__":
    main()
