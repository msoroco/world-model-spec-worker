"""Bind final-manifest selected diagnostic source chains without acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / "selected_delivery_chain_current.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    matrix = json.loads((HERE / "update027-final-manifest-matrix.json").read_text())
    assert matrix["manifest_sha256"] == sha(manifest_path)
    rows = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        folder = HERE / "update027-final-selected-delivery" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        logs = {}
        for negative in (False, True):
            name = "negative" if negative else "positive"
            command = [sys.executable, str(SCRIPT), "--case", case]
            if negative:
                command.append("--negative")
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = folder / (name + ".log")
            log.write_text(run.stdout)
            logs[name] = {"exit_code": run.returncode, "log": str(log.relative_to(HERE)),
                          "log_sha256": sha(log)}
        positive = json.loads((folder / "positive.log").read_text())
        negative = (folder / "negative.log").read_text()
        if (logs["positive"]["exit_code"] != 0 or logs["negative"]["exit_code"] == 0
                or positive["case_id"] != case
                or positive["construction_sha256"] != entry["construction_sha256"]
                or positive["source_shape_passed"] is not True
                or positive["joined_frames"] != 480
                or len(positive["joined_directions"]) != 2
                or len(positive["four_camera_sources"]) != 4
                or positive["delivery_accepted"] is not False
                or positive["original_native_motion_verified"] is not False
                or "Delivery construction differs from selected manifest" not in negative):
            raise AssertionError("Final selected delivery CPU chain failed: " + case)
        rows.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                     "source_sha256": positive["source_sha256"], "checks": logs,
                     "diagnostic_only": True, "original_accepted": False})
    proof = {"format": "c104538-final-selected-delivery-cpu-proof-v1",
             "manifest_sha256": sha(manifest_path),
             "matrix_sha256": sha(HERE / "update027-final-manifest-matrix.json"),
             "auditor_sha256": sha(SCRIPT), "selected_cases": rows,
             "positive_diagnostic_source_chains": len(rows),
             "negative_construction_rejections": len(rows),
             "original_native_or_pixel_acceptance": False}
    path = HERE / "update027-final-selected-delivery.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(rows), "negative_rejections": len(rows),
                      "original_accepted": False, "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
