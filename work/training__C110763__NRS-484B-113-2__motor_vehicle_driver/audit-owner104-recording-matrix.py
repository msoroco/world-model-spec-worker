"""Independent eight-path selected construction/source/processing matrix audit."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    source = HERE / "owner104-recording-matrix-proof.json"
    proof = read(source)
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    runtime_sha = sha(ROOT / "runtime/SOURCE-MANIFEST.json")
    if manifest["runtime_manifest_sha256"] != runtime_sha:
        raise ValueError("Final selected manifest does not bind current runtime")
    if len(proof["paths"]) != 8:
        raise ValueError("Selected eight-path matrix source changed")
    outputs = {}
    configs = {}
    for entry, label in zip(manifest["cases"], ("a", "b")):
        for ref in [entry] + entry["candidates"]:
            candidate = ref["id"]
            key = f"{label}-{candidate}"
            item = proof["paths"][key]
            attempt = ROOT / item["attempt"]
            saved = ROOT / item["saved"] / "v0001"
            construction = HERE / ref["construction"]
            receipt = read(attempt / "compatibility.json")
            processing = read(saved / "processing.json")
            if (sha(construction) != ref["construction_sha256"]
                    or receipt["construction_sha256"] != ref["construction_sha256"]
                    or receipt["case_id"] != entry["case_id"]
                    or receipt["candidate_id"] != candidate
                    or sha(attempt / "compatibility.json") != item["receipt_sha256"]
                    or sha(attempt / "compatibility-analysis.log") != item["analysis_sha256"]
                    or sha(attempt / "negative-analysis.log") != item["negative_sha256"]
                    or receipt["negative_removed"] != "native_samples.jsonl"
                    or receipt["negative_error_contains"] not in
                    (attempt / "negative-analysis.log").read_text()):
                raise ValueError("Public source-negative construction binding differs: " + key)
            selected = ref["compatibility"]
            if (receipt["runtime_manifest_sha256"] != runtime_sha
                    or sha(HERE / selected["receipt"]) != selected["sha256"]
                    or sha(HERE / selected["receipt"]) != item["receipt_sha256"]
                    or sha(HERE / selected["log"]) != item["analysis_sha256"]
                    or sha(HERE / selected["negative_log"]) != item["negative_sha256"]
                    or ref["offline"]["log_sha256"] != item["offline"]["log_sha256"]
                    or ref["saved_cpu_proof"]["log_sha256"] != item["saved_proof"]["log_sha256"]):
                raise ValueError("Final-manifest receipt binding differs: " + key)
            if (processing.get("passed") is not True or processing.get("recorded_only") is not True
                    or processing.get("originals_preserved") is not True
                    or processing.get("timestamp_joins", {}).get("frames") != 600
                    or processing.get("analysis_revision", {}).get("construction_sha256")
                    != ref["construction_sha256"]
                    or read(saved / "final-decode.json").get("frames") != 600):
                raise ValueError("Recorded-only saved processing differs: " + key)
            config = read(attempt / "config.json")
            if candidate == "primary":
                configs[label] = config
            measured = receipt["measurement_examples"]["backing_intersection_relation"]["value"]
            relation = "backing_clear_of_intersection" if label == "a" else "backing_into_intersection"
            if measured["relation"] != relation or measured["backing_frames"] != 200:
                raise ValueError("Source-derived reverse/intersection relation differs: " + key)
            outputs[key] = measured["max_backing_intersection_overlap_m2"]
    for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz", "required_atoms",
                "source_packets", "mandatory_channels", "recording_description", "cameras",
                "engineering_knobs"):
        if configs["a"][key] != configs["b"][key]:
            raise ValueError("Controlled fixed configuration differs: " + key)
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        if outputs["a-" + candidate] != 0 or outputs["b-" + candidate] <= 3:
            raise ValueError("Controlled full-body overlap contrast absent: " + candidate)
    return {"format": "c110763-owner104-recording-matrix-audit-v1", "passed": True,
            "proof_sha256": sha(source), "prebind_manifest_sha256": proof["manifest_sha256"],
            "final_manifest_sha256": sha(manifest_path), "runtime_manifest_sha256": runtime_sha,
            "construction_paths": 8,
            "fixed_conditions_checked": True, "source_negative_paths": 8,
            "recorded_only_saved_paths": 8, "overlap_m2": outputs,
            "original_native_or_legal_claimed": False}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
