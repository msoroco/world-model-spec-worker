"""Rerun selected diagnostic delivery audit positive and negative branches."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    output = HERE / "update045-delivery-case-proofs"
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        case_dir = output / suffix
        case_dir.mkdir(parents=True, exist_ok=True)
        logs = {}
        for negative in (False, True):
            command = [sys.executable, str(HERE / "prove-nine-case-delivery-update045.py"),
                       "--case", case]
            if negative:
                command.append("--negative")
            run = subprocess.run(command, capture_output=True, text=True,
                                 cwd=HERE.parents[1])
            log = case_dir / ("negative.log" if negative else "positive.log")
            log.write_text(run.stdout + run.stderr)
            if negative:
                assert run.returncode == 1 and "Delivery construction differs from selected manifest" in log.read_text()
            else:
                assert run.returncode == 0 and '"delivery_accepted": false' in log.read_text()
            logs["negative" if negative else "positive"] = {"log": str(log.relative_to(HERE)),
                                                                 "sha256": sha(log), "exit_code": run.returncode}
        rows.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                     "branches": logs})
    proof = {"format": "c110454-current-selected-delivery-diagnostic-v1",
             "manifest_sha256": sha(manifest_path), "cases": rows,
             "source_shaped_diagnostic_only": True,
             "original_native_accepted": False, "recordings_accepted": 0}
    path = HERE / "update045-selected-delivery-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(rows), "positive_and_negative_passed": True,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
