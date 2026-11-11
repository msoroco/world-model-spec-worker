"""Independently bind current C111294 CPU receipts to the four speed probes."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = ROOT / ".runtime-work/c111294-update015-boundary"
CASES = {"below_80_mph": (75.0, "measured_not_above_80_mph"),
         "inside_80_mph": (79.5, "measured_not_above_80_mph"),
         "at_80_mph": (80.0, "unresolved_at_80_mph"),
         "above_80_mph": (85.0, "measured_above_80_mph")}
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def config(construction: dict) -> dict:
    return json.loads(next(row["content"] for row in construction["files"]
                           if row["path"] == "config.json"))


def audit() -> dict:
    manifest = read(HERE / "draft-execution-manifest.json")
    plan = read(HERE / "case-plan.json")
    require(len(manifest["cases"]) == len(plan["cases"]) == 4,
            "Four strict-boundary cases required")
    require(set(plan["comparisons"][0]["case_ids"]) ==
            {row["case_id"] for row in manifest["cases"]},
            "Controlled comparison omits a speed case")
    rows = []
    road_hash = None
    for suffix, (expected, relation) in CASES.items():
        case_id = HERE.name + "__" + suffix
        entry = next(row for row in manifest["cases"] if row["case_id"] == case_id)
        diagnostic = read(HERE / f"update015-{suffix}-diagnostic.json")
        source_hash = hashlib.sha256(diagnostic["files"]["native_samples.jsonl"].encode()).hexdigest()
        road = hashlib.sha256(diagnostic["files"]["road.xodr"].encode()).hexdigest()
        if road_hash is None:
            road_hash = road
        require(road == road_hash, "Controlled cases changed authored road")
        samples = [json.loads(line) for line in
                   diagnostic["files"]["native_samples.jsonl"].splitlines() if line.strip()]
        require(len(samples) == 480 and all(row["source_kind"] == "synthetic_cpu_fixture"
                                            for row in samples),
                "Diagnostic speed provenance or frame count differs")
        peak = max(math.sqrt(sum(v*v for v in row["ego_velocity_mps"])) / .44704
                   for row in samples)
        require(abs(peak - expected) < 1e-5,
                "Raw velocity does not support requested speed probe")
        baseline = None
        for candidate in CANDIDATES:
            selected = entry if candidate == "primary" else next(
                row for row in entry["candidates"] if row["id"] == candidate)
            construction_path = HERE / selected["construction"]
            construction = read(construction_path)
            require(sha(construction_path) == selected["construction_sha256"],
                    "Construction hash differs: " + suffix + "/" + candidate)
            current = config(construction)
            require(current["case_id"] == case_id and current["requested_setting_mph"] == expected,
                    "Case config or requested speed differs")
            if candidate == "primary":
                baseline = current
            else:
                require({k: v for k, v in current.items() if k not in ("candidate_id", "knobs")} ==
                        {k: v for k, v in baseline.items() if k not in ("candidate_id", "knobs")},
                        "Fallback changed case context")
                changed = {key for key in current["knobs"]
                           if current["knobs"][key] != baseline["knobs"][key]}
                require(changed == set(selected["changed_knobs"]) and len(changed) == 1,
                        "Fallback knob change differs")
            folder = RUNS / "exact" / suffix / candidate
            cp = folder / "compatibility/compatibility.json"
            pp = folder / "process-saved/v0001/processing.json"
            receipt = read(cp)
            processing = read(pp)
            require(receipt["passed"] and receipt["case_id"] == case_id and
                    receipt["candidate_id"] == candidate and
                    receipt["construction_sha256"] == selected["construction_sha256"] and
                    receipt["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"],
                    "Exact compatibility receipt binding differs")
            require({"selected_measurements", "negative_case_source", "four_camera_sources",
                     "lean_decoder", "final_decode"} <= set(receipt["checks"]) and
                    receipt["negative_removed"] == "native_samples.jsonl" and
                    receipt["negative_error_contains"] ==
                    "Missing required source: native_samples.jsonl",
                    "Compatibility checks or negative source differ")
            measured = receipt["measurement_examples"]["speed_relation"]
            require(measured["sources"]["native_samples.jsonl"] == source_hash and
                    measured["value"]["measured_relation"] == relation and
                    abs(measured["value"]["derived_peak_mph"] - peak) < 1e-4,
                    "Source-bound speed measurement differs")
            require(processing["passed"] and processing["originals_preserved"] and
                    processing["final_video_checks"]["passed"] and
                    processing["case_id"] == case_id and
                    processing["candidate_id"] == candidate and
                    not processing["physical_acceptance_claimed"] and
                    not processing["legal_acceptance_claimed"],
                    "Saved processing or acceptance scope differs")
            offline = RUNS / "offline" / suffix / candidate / "offline.log"
            require(offline.is_file() and offline.stat().st_size > 0,
                    "Exact offline proof absent")
            rows.append({"case_suffix": suffix, "candidate": candidate,
                         "requested_mph": expected, "measured_relation": relation,
                         "construction_sha256": sha(construction_path),
                         "offline_log_sha256": sha(offline),
                         "compatibility_receipt": str(cp.relative_to(ROOT)),
                         "compatibility_sha256": sha(cp),
                         "process_saved_receipt": str(pp.relative_to(ROOT)),
                         "process_saved_sha256": sha(pp),
                         "synthetic_only": True, "selected": False})
    return {"format": "c111294-update015-boundary-cpu-proof",
            "cases": len(CASES), "candidate_bundles": len(rows),
            "offline_passed": len(rows), "compatibility_passed": len(rows),
            "process_saved_passed": len(rows), "road_sha256": road_hash,
            "manifest_sha256": sha(HERE / "draft-execution-manifest.json"),
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "rows": rows}


if __name__ == "__main__":
    result = audit()
    (HERE / "update015-boundary-cpu-proof.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("cases", "candidate_bundles", "offline_passed",
                       "compatibility_passed", "process_saved_passed")}, sort_keys=True))
