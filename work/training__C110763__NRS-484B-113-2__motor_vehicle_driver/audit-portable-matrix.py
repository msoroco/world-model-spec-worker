"""Independent eight-receipt and controlled-case audit, using saved artifacts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    batch = json.loads((REPO / "batch.json").read_text())
    entries = {{"probe_1":"condition_a","probe_2":"condition_b"}[e["case_id"].split("__")[-1]]: e for e in manifest["cases"]}
    if set(entries) != {"condition_a", "condition_b"}:
        raise ValueError("Controlled case identities differ")
    outcomes = {}
    primary_configs = {}
    for suffix in ("condition_a", "condition_b"):
        entry = entries[suffix]
        refs = [{"id": entry["id"], "construction": entry["construction"],
                 "construction_sha256": entry["construction_sha256"]}] + entry["candidates"]
        for ref in refs:
            candidate = ref["id"]
            path = HERE / ("portable-proof-" + suffix + "-" + candidate + ".json")
            proof = json.loads(path.read_text())
            positive = proof["positive"]; negative = proof["negative"]
            if positive["format"] != "worker-package-compatibility-v1" or positive["passed"] is not True:
                raise ValueError("Pinned portable positive absent")
            if not {"actual_analysis", "native_validation", "mandatory_observations",
                    "lean_decoder", "render", "final_decode", "acquisition_unchanged"} <= set(positive["checks"]):
                raise ValueError("Portable checks incomplete")
            if positive["case_id"] != entry["case_id"] or positive["candidate_id"] != candidate or \
               positive["construction_sha256"] != ref["construction_sha256"] or \
               positive["runtime_manifest_sha256"] != batch["runtime"]["source_manifest_sha256"]:
                raise ValueError("Portable receipt does not bind exact construction or runtime")
            construction_path = HERE / ref["construction"]
            if sha(construction_path) != ref["construction_sha256"]:
                raise ValueError("Construction changed after portable proof")
            construction = json.loads(construction_path.read_text())
            config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
            if candidate == "primary": primary_configs[suffix] = config
            analysis_code = next(f["content"] for f in construction["files"] if f["path"] == "finalize.py")
            if hashlib.sha256(analysis_code.encode()).hexdigest() != positive["analysis_sha256"]:
                raise ValueError("Portable finalizer changed")
            log = HERE / ("portable-analysis-" + suffix + "-" + candidate + ".log")
            if sha(log) != positive["log_sha256"]:
                raise ValueError("Portable analysis log differs")
            nlog = HERE / ("portable-negative-" + suffix + "-" + candidate + ".log")
            if sha(nlog) != negative["log_sha256"] or negative["exit_code"] == 0 or \
               negative["error_contains"] not in nlog.read_text() or \
               negative["removed"] != "native_samples.jsonl":
                raise ValueError("Portable missing-source negative differs")
            scratch = Path(proof["scratch"])
            fixture = Path(proof["fixture"])
            receipt = json.loads((scratch / "output/compatibility.json").read_text())
            if {k: v for k, v in receipt.items() if k != "fixture_manifest"} != positive:
                raise ValueError("Saved runtime receipt differs from exported proof")
            report = json.loads((scratch / "output/analysis-report.json").read_text())
            if set(report["measurements"]) != {"reverse_motion_frames",
                                               "backing_intersection_relation",
                                               "intersection_witness_relation",
                                               "intersection_event_frames",
                                               "intersection_overlap_area_m2"}:
                raise ValueError("Source-topic measurement cardinality differs")
            measured = report["measurements"]["backing_intersection_relation"]
            expected = "backing_clear_of_intersection" if suffix == "condition_a" else "backing_into_intersection"
            if measured["value"]["relation"] != expected or \
               measured["value"]["backing_frames"] != 200 or \
               measured["sources"]["native_samples.jsonl"] != sha(fixture / "native_samples.jsonl"):
                raise ValueError("Exact source-bound saved relation differs")
            if report["measurements"]["reverse_motion_frames"]["value"] != 200 or \
               report["measurements"]["intersection_witness_relation"]["value"] is not \
               (suffix == "condition_b"):
                raise ValueError("Backing or witness measurement differs")
            for item in report["measurements"].values():
                if item["sources"] != {name: sha(fixture / name) for name in
                                       ("native_samples.jsonl", "road_geometry.json")}:
                    raise ValueError("Case-specific measurement source binding differs")
            outcomes[suffix + "/" + candidate] = {
                "relation": expected,
                "overlap_m2": measured["value"]["max_backing_intersection_overlap_m2"],
                "construction_sha256": positive["construction_sha256"]}
    a = primary_configs["condition_a"]; b = primary_configs["condition_b"]
    for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz", "required_atoms",
                "source_packets", "mandatory_channels", "recording_description", "cameras",
                "engineering_knobs"):
        if a[key] != b[key]: raise ValueError("Controlled pair fixed condition differs: " + key)
    if not all(outcomes["condition_a/" + c]["overlap_m2"] == 0 and
               outcomes["condition_b/" + c]["overlap_m2"] > 3
               for c in ("primary", "fallback1", "fallback2", "fallback3")):
        raise ValueError("Controlled backing-intersection contrast differs")
    print(json.dumps({"passed": True, "scope": "independent exact portable v1 synthetic audit",
                      "ready": False, "packages": len(outcomes),
                      "controlled_variable": "reverse_path_intersection_occupancy",
                      "fixed_conditions_checked": True, "cases": outcomes}, indent=2))


if __name__ == "__main__": main()
