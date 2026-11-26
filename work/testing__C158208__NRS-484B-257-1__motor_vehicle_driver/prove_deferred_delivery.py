"""Independently audit all selected source-gated CPU compatibility stages."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from selected_delivery_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c158208-owner-nov26b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    index = json.loads((HERE / "deferred-source-compatibility-index.json").read_text())
    rows = []
    for row in index["cases"]:
        case_id = row["case_id"]
        kind = case_id.split("__")[-1]
        stage = SCRATCH / "deferred-compat-v3" / kind / "primary"
        checked = audit(stage, case_id=case_id, diagnostic_fixture=True)
        if checked["source_frames"] != 3 or checked["physical_acceptance_claimed"]:
            raise ValueError("synthetic selected audit scope differs: " + kind)
        with tempfile.TemporaryDirectory(prefix=kind + "-negative-", dir=SCRATCH / "tmp") as tmp:
            negative = Path(tmp)
            for path in stage.iterdir():
                if path.is_file() and path.name != "overview.mkv":
                    (negative / path.name).symlink_to(path)
            try:
                audit(negative, case_id=case_id, diagnostic_fixture=True)
            except (FileNotFoundError, ValueError, KeyError):
                pass
            else:
                raise ValueError("missing overview camera accepted: " + kind)
        output = HERE / "cases" / kind / "primary" / "delivery-audit.json"
        output.write_text(json.dumps(checked, indent=2, sort_keys=True) + "\n")
        rows.append({"case_id": case_id,
                     "construction_sha256": row["candidates"][0]["construction_sha256"],
                     "receipt": str(output.relative_to(HERE)), "sha256": sha(output),
                     "missing_overview_camera_rejected": True})
    result = {"format": "c158208-source-gated-delivery-cpu-index-v1",
              "assignment_id": HERE.name, "scope": "synthetic_fixture_cpu_only",
              "compatibility_index_sha256": sha(HERE / "deferred-source-compatibility-index.json"),
              "cases": rows, "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    target = HERE / "deferred-source-delivery-index.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return {"cases": len(rows), "index_sha256": sha(target)}


if __name__ == "__main__":
    print(json.dumps(prove(), indent=2))
