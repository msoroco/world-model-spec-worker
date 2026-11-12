"""Run and bind selected alley diagnostic positive/negative audit receipts."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange.delivery_handoff import CHECKS, validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 2:
        raise ValueError("Two selected alley cases required")
    script = HERE / "selected_delivery_chain_cpu.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        folder = HERE / "update035-selected-delivery-cpu" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        runs = {}
        for negative in (False, True):
            kind = "negative" if negative else "positive"
            command = [sys.executable, str(script), "--case", case]
            if negative:
                command.append("--negative")
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, check=False)
            log = folder / (kind + ".log")
            log.write_text(result.stdout)
            runs[kind] = (command, result.returncode, log)
        positive = json.loads(runs["positive"][2].read_text())
        negative_text = runs["negative"][2].read_text()
        if (runs["positive"][1] != 0 or runs["negative"][1] == 0 or
                positive["case_id"] != case or positive["construction_sha256"] != entry["construction_sha256"] or
                positive["source_shape_passed"] is not True or positive["delivery_accepted"] is not False or
                "Delivery construction differs from selected manifest" not in negative_text):
            raise ValueError("Selected alley diagnostic delivery audit failed: " + case)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": sorted(CHECKS),
            "script": script.name, "script_sha256": sha(script),
            "command": " ".join(runs["positive"][0]), "test_exit_code": 0,
            "test_log": str(runs["positive"][2].relative_to(HERE)),
            "test_log_sha256": sha(runs["positive"][2]),
            "negative_command": " ".join(runs["negative"][0]),
            "negative_exit_code": runs["negative"][1],
            "negative_expected_error": "Delivery construction differs from selected manifest",
            "negative_log": str(runs["negative"][2].relative_to(HERE)),
            "negative_log_sha256": sha(runs["negative"][2]),
            "scope": "CPU diagnostic source chain only; original Native property and pixel acceptance unverified"}
        validate_case(HERE, entry, ["full-train"])
        for field in ("script_sha256", "test_log_sha256", "negative_log_sha256"):
            bad = copy.deepcopy(entry)
            bad["delivery_acceptance"][field] = "0" * 64
            try:
                validate_case(HERE, bad, ["full-train"])
            except ValueError:
                pass
            else:
                raise AssertionError("Corrupt alley delivery receipt accepted: " + field)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    proof = {"format": "c10014-selected-delivery-cpu-proof-v1",
             "manifest_sha256": sha(manifest_path), "selected_cases": 2,
             "positive_diagnostic_audits": 2, "negative_construction_rejections": 2,
             "validator_corruptions_rejected": 6,
             "original_native_or_legal_acceptance_claimed": False}
    target = HERE / "update035-selected-delivery-cpu-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"manifest_sha256": sha(manifest_path),
                      "proof_sha256": sha(target), "selected_cases": 2,
                      "accepted_recordings": 0}))


if __name__ == "__main__":
    main()
