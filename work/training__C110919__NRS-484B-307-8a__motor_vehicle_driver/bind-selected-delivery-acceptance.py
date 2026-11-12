"""Run positive/negative CPU acceptance audits and bind all selected cases."""
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
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    if len(manifest["cases"]) != 20:
        raise ValueError("Twenty selected cases required")
    script = HERE / "selected_delivery_acceptance.py"
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        folder = HERE / "update061-selected-delivery-acceptance" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        commands = {}
        for negative in (False, True):
            key = "negative" if negative else "positive"
            command = [sys.executable, str(script), "--case", case]
            if negative:
                command.append("--negative")
            run = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
            log = folder / (key + ".log")
            log.write_text(run.stdout)
            commands[key] = (command, run.returncode, log)
        positive = json.loads(commands["positive"][2].read_text())
        negative = commands["negative"][2].read_text()
        if (commands["positive"][1] != 0 or commands["negative"][1] == 0 or
                positive["case_id"] != case or positive["construction_sha256"] != entry["construction_sha256"] or
                positive["source_shape_passed"] is not True or positive["delivery_accepted"] is not False or
                "Delivery construction differs from selected manifest" not in negative):
            raise ValueError("Selected acceptance CPU audit failed: " + case)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": sorted(CHECKS),
            "script": script.name, "script_sha256": sha(script),
            "command": " ".join(commands["positive"][0]), "test_exit_code": 0,
            "test_log": str(commands["positive"][2].relative_to(HERE)),
            "test_log_sha256": sha(commands["positive"][2]),
            "negative_command": " ".join(commands["negative"][0]),
            "negative_exit_code": commands["negative"][1],
            "negative_expected_error": "Delivery construction differs from selected manifest",
            "negative_log": str(commands["negative"][2].relative_to(HERE)),
            "negative_log_sha256": sha(commands["negative"][2]),
            "scope": "source-shaped CPU diagnostic audit; original Native and pixel acceptance unverified"}
        validate_case(HERE, entry, ["full-train"])
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_cases": 20, "positive_cpu_audits": 20,
                      "negative_cpu_rejections": 20, "manifest_sha256": sha(path),
                      "accepted_recordings": 0}))


if __name__ == "__main__":
    main()
