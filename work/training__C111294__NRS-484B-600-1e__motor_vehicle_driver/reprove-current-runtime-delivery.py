"""Four current-runtime speed delivery source audits and original-source negatives."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "current_runtime_delivery_audit.py"
MANIFEST = HERE / "current-runtime-reproof-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        attempt = (ROOT / ".runtime-work/c111294-current-below-primary-compat" if suffix == "below_80_mph"
                   else ROOT / ".runtime-work/c111294-current-matrix" / suffix / "primary/compat")
        saved = (ROOT / ".runtime-work/c111294-current-below-primary-saved/v0001/processing.json"
                 if suffix == "below_80_mph" else ROOT / ".runtime-work/c111294-current-matrix" / suffix / "primary/saved/v0001/processing.json")
        folder = HERE / "current-runtime-selected-delivery" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        common = [sys.executable, str(SCRIPT), "--case", case, "--candidate", "primary",
                  "--attempt", str(attempt), "--processing", str(saved)]
        positive = [*common, "--output", str(folder / "diagnostic.json"), "--diagnostic"]
        negative = [*common, "--output", str(folder / "original.json")]
        for kind, command in (("positive", positive), ("negative", negative)):
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            (folder / (kind + ".log")).write_text(run.stdout + run.stderr)
            if (kind == "positive" and run.returncode != 0) or (kind == "negative" and run.returncode == 0):
                raise ValueError("Wrong diagnostic delivery result: " + suffix + "/" + kind)
        diagnostic = json.loads((folder / "diagnostic.json").read_text())
        if not (diagnostic["case_id"] == case and diagnostic["passed"] is False and
                diagnostic["source_shaped_unit_test"] is True and
                diagnostic["original_physical_acceptance_claimed"] is False and
                "Original Native speed source required" in (folder / "negative.log").read_text()):
            raise ValueError("Diagnostic delivery proof differs: " + suffix)
        rows.append({"case_id": case, "diagnostic_sha256": sha(folder / "diagnostic.json"),
                     "positive_log_sha256": sha(folder / "positive.log"),
                     "negative_log_sha256": sha(folder / "negative.log")})
        print(suffix, "delivery source shape and original rejection passed", flush=True)
    if len(rows) != 4:
        raise ValueError("Four selected delivery audits required")
    output = HERE / "current-runtime-selected-delivery-proof.json"
    output.write_text(json.dumps({"format": "c111294-current-delivery-cpu-v1",
                                  "manifest_sha256": sha(MANIFEST), "script_sha256": sha(SCRIPT),
                                  "rows": rows, "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"cases": len(rows), "proof_sha256": sha(output)}))


if __name__ == "__main__":
    main()
