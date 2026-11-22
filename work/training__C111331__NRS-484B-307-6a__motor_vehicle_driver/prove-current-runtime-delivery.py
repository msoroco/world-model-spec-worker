"""Check both selected diagnostic signal handoffs and reject original promotion."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "delivery_audit.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for suffix in ("reference", "contrast"):
        case = HERE.name + "__" + suffix
        attempt = (ROOT / ".runtime-work/c111331-current-reference-primary-compat" if suffix == "reference"
                   else ROOT / ".runtime-work/c111331-current-matrix/contrast/primary/compat")
        saved = (ROOT / ".runtime-work/c111331-current-reference-primary-saved/v0001/processing.json"
                 if suffix == "reference" else ROOT / ".runtime-work/c111331-current-matrix/contrast/primary/saved/v0001/processing.json")
        folder = HERE / "current-runtime-selected-delivery" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        common = [sys.executable, str(SCRIPT), "--case", case, "--candidate", "primary",
                  "--attempt", str(attempt), "--processing", str(saved)]
        for kind, extra in (("positive", ["--diagnostic"]), ("negative", [])):
            command = [*common, "--output", str(folder / (kind + ".json")), *extra]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            (folder / (kind + ".log")).write_text(result.stdout + result.stderr)
            if (kind == "positive" and result.returncode != 0) or (kind == "negative" and result.returncode == 0):
                raise ValueError("Delivery branch failed: " + suffix + "/" + kind)
        diagnostic = json.loads((folder / "positive.json").read_text())
        if not (diagnostic["passed"] is True and diagnostic["diagnostic_only"] is True and
                diagnostic["physical_acceptance_claimed"] is False and
                "Original Native signal/body and pixel evidence required" in (folder / "negative.log").read_text()):
            raise ValueError("Diagnostic delivery scope differs: " + suffix)
        rows.append({"case_id": case, "positive_sha256": sha(folder / "positive.json"),
                     "positive_log_sha256": sha(folder / "positive.log"),
                     "negative_log_sha256": sha(folder / "negative.log")})
        print(suffix, "delivery diagnostic and original rejection passed", flush=True)
    output = HERE / "current-runtime-selected-delivery-proof.json"
    output.write_text(json.dumps({"format": "c111331-current-delivery-cpu-v1",
                                  "manifest_sha256": sha(HERE / "current-runtime-reproof-manifest.json"),
                                  "script_sha256": sha(SCRIPT), "rows": rows,
                                  "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"cases": len(rows), "proof_sha256": sha(output)}))


if __name__ == "__main__":
    main()
