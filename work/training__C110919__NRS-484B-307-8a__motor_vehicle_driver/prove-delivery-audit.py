"""Replay positive source-shape and wrong-construction rejection for both cases."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "update017-selected-pair-probe-manifest.json").read_text())
    proof_dir = HERE / "update020-delivery-audit"
    proof_dir.mkdir(exist_ok=True)
    cases = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        attempt = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / suffix / "primary/compatibility"
        processing = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / suffix / "primary/saved/v0001/processing.json"
        output = proof_dir / (suffix + ".json")
        if output.exists():
            output.unlink()
        base = [".venv-cpu/bin/python", str((HERE / "delivery_audit.py").relative_to(ROOT)),
                "--case", entry["case_id"], "--attempt", str(attempt.relative_to(ROOT)),
                "--processing", str(processing.relative_to(ROOT)),
                "--output", str(output.relative_to(ROOT)), "--diagnostic"]
        positive = subprocess.run(base + ["--construction-sha256", entry["construction_sha256"]],
                                  cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, check=False)
        positive_log = proof_dir / (suffix + "-positive.log")
        positive_log.write_text(positive.stdout)
        if positive.returncode or not output.is_file():
            raise ValueError("Delivery positive diagnostic failed: " + positive.stdout)
        receipt = json.loads(output.read_text())
        if receipt.get("passed") is not False or receipt.get("source_shape_passed") is not True or \
           any(receipt["checks"].values()) or receipt.get("physical_or_legal_acceptance_claimed") is not False:
            raise ValueError("Diagnostic delivery audit claimed acceptance")
        bad_output = proof_dir / (suffix + "-negative.json")
        if bad_output.exists():
            bad_output.unlink()
        negative = subprocess.run(base[:-2] + [str(bad_output.relative_to(ROOT)), "--diagnostic",
                                           "--construction-sha256", "0" * 64],
                                  cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, check=False)
        negative_log = proof_dir / (suffix + "-negative.log")
        negative_log.write_text(negative.stdout)
        if negative.returncode == 0 or "Delivery construction differs from selected manifest" not in negative.stdout or bad_output.exists():
            raise ValueError("Wrong-construction delivery negative failed")
        cases.append({"case_id": entry["case_id"], "positive_receipt": str(output.relative_to(HERE)),
                      "positive_receipt_sha256": sha(output),
                      "positive_log": str(positive_log.relative_to(HERE)),
                      "positive_log_sha256": sha(positive_log),
                      "negative_log": str(negative_log.relative_to(HERE)),
                      "negative_log_sha256": sha(negative_log),
                      "negative_exit_code": negative.returncode,
                      "delivery_accepted": False})
    proof = {"format": "c110919-selected-pair-independent-delivery-cpu-v1",
             "manifest_sha256": sha(HERE / "update017-selected-pair-probe-manifest.json"),
             "auditor_sha256": sha(HERE / "delivery_audit.py"),
             "cases": cases, "original_native_accepted": False}
    path = HERE / "update020-delivery-audit-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(cases), "positive_diagnostics": len(cases),
                      "negative_rejections": len(cases), "proof_sha256": sha(path),
                      "original_native_accepted": False}))


if __name__ == "__main__":
    main()
