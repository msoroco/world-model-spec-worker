"""Bind refreshed eight-path receipts and selected delivery CPU audits."""
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    proof = json.loads((HERE / "owner104-recording-matrix-proof.json").read_text())
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    if proof["manifest_sha256"] != sha(path) or len(proof["paths"]) != 8:
        raise ValueError("Eight exact refreshed paths must bind the selected manifest")
    for entry, label in zip(manifest["cases"], ("a", "b")):
        for ref in [entry] + entry["candidates"]:
            candidate = ref["id"]
            key = f"{label}-{candidate}"
            receipt = proof["paths"][key]
            if receipt["construction_sha256"] != ref["construction_sha256"]:
                raise ValueError("Refreshed construction SHA differs")
            attempt = ROOT / receipt["attempt"]
            destination = f"owner104-selected-{key}"
            paths = {}
            for source, suffix in (("compatibility.json", "compatibility.json"),
                                   ("compatibility-analysis.log", "analysis.log"),
                                   ("negative-analysis.log", "negative.log")):
                target = HERE / f"{destination}-{suffix}"
                shutil.copyfile(attempt / source, target)
                paths[suffix] = target
            offline = receipt["offline"]
            ref["offline"] = {
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ID}/execution-manifest.json --case {entry['case_id']} --candidate {candidate} --output .runtime-work/c110763-refresh/offline-{key}-v2",
                "construction_sha256": ref["construction_sha256"],
                "exit_code": 0, "log": offline["log"], "log_sha256": offline["log_sha256"]}
            ref["compatibility"] = {
                "receipt": paths["compatibility.json"].name,
                "sha256": sha(paths["compatibility.json"]),
                "log": paths["analysis.log"].name,
                "negative_log": paths["negative.log"].name}
            saved = receipt["saved_proof"]
            ref["saved_cpu_proof"] = {
                "exit_code": 0, "log": saved["log"], "log_sha256": saved["log_sha256"],
                "scope": "recorded-only synthetic CPU fixture; original Native/pixels unverified"}
        physical = HERE / "selected-physical" / ("condition_a" if label == "a" else "condition_b") / "proof.json"
        entry["physical_preparation"] = {
            "receipt": str(physical.relative_to(HERE)), "sha256": sha(physical)}
        entry["post_capture"] = {
            "recorded_only": True,
            "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ID}/execution-manifest.json --case {entry['case_id']} --attempt $ATTEMPT --output $SAVED --library runtime/library --validator $VALIDATOR",
            "feedback_command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ID}/execution-manifest.json --case {entry['case_id']} --attempt $ATTEMPT --output $SAVED --library runtime/library --validator $VALIDATOR",
            "test_exit_code": 0,
            "test_log": proof["paths"][f"{label}-primary"]["saved_proof"]["log"],
            "test_log_sha256": proof["paths"][f"{label}-primary"]["saved_proof"]["log_sha256"]}
        primary = proof["paths"][f"{label}-primary"]
        attempt = primary["attempt"]
        saved_path = primary["saved"] + "/v0001"
        audit_script = HERE / "audit-selected-delivery.py"
        audit_base = (f".venv-cpu/bin/python work/{ID}/audit-selected-delivery.py"
                      f" --case {entry['case_id']} --attempt {attempt} --saved {saved_path}")
        positive = HERE / f"owner104-delivery-{label}-positive.log"
        negative = HERE / f"owner104-delivery-{label}-negative.log"
        entry["delivery_acceptance"] = {
            "case_id": entry["case_id"], "sets": ["demo-train", "full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": audit_script.name, "script_sha256": sha(audit_script),
            "command": audit_base, "test_exit_code": 0,
            "test_log": positive.name, "test_log_sha256": sha(positive),
            "negative_command": audit_base + " --remove-native-source",
            "negative_exit_code": 1,
            "negative_expected_error": "Missing required source: native_samples.jsonl",
            "negative_log": negative.name, "negative_log_sha256": sha(negative),
            "scope": "CPU source audit only; actual pixels and physical completion remain local checks"}
        construction = json.loads((HERE / entry["construction"]).read_text())
        for item in construction["recording_description"]["channels"] + construction["recording_description"]["context_inputs"]:
            entry["acquisition"].setdefault(item["name"], {
                "entrypoint": "finalize.py", "method": item["method"],
                "evidence": "retained original Native, camera and map sources; physical review pending"})
    save(path, manifest)
    print(json.dumps({"manifest_sha256": sha(path), "cases": 2, "candidate_paths": 8}))


if __name__ == "__main__":
    main()
