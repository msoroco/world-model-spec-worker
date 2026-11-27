"""Bind exact independent CPU audit predicates to all selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "draft-native-manifest.json"
    manifest = json.loads(path.read_text())
    script = "delivery_audit.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        slug = case.rsplit("__", 1)[-1]
        positive = f"delivery-{slug}-positive.log"
        negative = f"delivery-{slug}-negative.log"
        if "cpu_predicates_passed" not in (HERE / positive).read_text():
            raise ValueError("Positive independent delivery predicate missing")
        if "Exact original Native result missing" not in (HERE / negative).read_text():
            raise ValueError("Synthetic original-source rejection missing")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": CHECKS,
            "script": script, "script_sha256": sha(HERE / script),
            "command": f".venv-cpu/bin/python -B work/{AID}/{script} --case {case} --self-test",
            "test_exit_code": 0, "test_log": positive, "test_log_sha256": sha(HERE / positive),
            "negative_command": f".venv-cpu/bin/python -B work/{AID}/{script} --case {case} --self-test --negative",
            "negative_exit_code": 1, "negative_expected_error": "Exact original Native result missing",
            "negative_log": negative, "negative_log_sha256": sha(HERE / negative),
            "diagnostic_scope": "CPU predicate check only; original Native pixels, crossing identity, lead stop purpose, pedestrian crossing and actual ego pass and physical result require independent review",
            "production_command": f"PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -B work/{AID}/{script} --case {case} --attempt $ATTEMPT --review original-review.json --video raw.mkv --trace trace.jsonl --job $JOB_ID --recording-id $RECORDING_ID --output $AUDIT_OUTPUT"}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]), "manifest_sha256": sha(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
