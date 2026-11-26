"""Reopen every exact diagnostic saved stage independently.

These three-frame synthetic stages test the CPU audit path. They do not prove
original Native capture, site review, physical acceptance, or legal judgment.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from selected_delivery_audit import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work" / "c158208-nov25b"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    manifest = json.loads((HERE / "execution-manifest.diagnostic.json").read_text())
    index = json.loads((HERE / "diagnostic-compatibility-index-all.json").read_text())
    if index["manifest_sha256"] != sha(HERE / "execution-manifest.diagnostic.json"):
        raise ValueError("diagnostic manifest changed since compatibility proofs")
    if {entry["case_id"] for entry in manifest["cases"]} != {
            entry["case_id"] for entry in index["case_proofs"]}:
        raise ValueError("case inventory differs from compatible stages")
    scratch_root = ROOT / ".runtime-work" / "c158208-all-delivery-audit"
    scratch_root.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        stage = SCRATCH / ("all-compat-" + kind)
        checked = audit(stage, case_id=case_id, diagnostic_fixture=True)
        if checked["source_frames"] != 3 or checked["physical_acceptance_claimed"]:
            raise ValueError("diagnostic audit changed source/acceptance scope")
        receipt_path = HERE / ("diagnostic-delivery-" + kind + ".json")
        receipt_path.write_text(json.dumps(checked, indent=2, sort_keys=True) + "\n")
        with tempfile.TemporaryDirectory(prefix="negative-", dir=scratch_root) as temp:
            missing_media = Path(temp)
            for source in stage.iterdir():
                if source.is_file() and source.name != "overview.mkv":
                    (missing_media / source.name).symlink_to(source)
            try:
                audit(missing_media, case_id=case_id, diagnostic_fixture=True)
            except (FileNotFoundError, ValueError, KeyError):
                pass
            else:
                raise ValueError("missing overview camera was accepted: " + kind)
        results.append({"case_id": case_id,
                        "construction_sha256": entry["construction_sha256"],
                        "receipt": receipt_path.name,
                        "receipt_sha256": sha(receipt_path),
                        "missing_overview_camera_rejected": True,
                        "source_kind": "synthetic_fixture"})
    output = {"format": "c158208-diagnostic-delivery-index-v1",
              "assignment_id": HERE.name,
              "manifest_sha256": sha(HERE / "execution-manifest.diagnostic.json"),
              "compatibility_index_sha256": sha(HERE / "diagnostic-compatibility-index-all.json"),
              "diagnostic_only": True,
              "case_proofs": results,
              "original_source_acceptance_claimed": False,
              "physical_acceptance_claimed": False,
              "legal_acceptance_claimed": False}
    path = HERE / "diagnostic-delivery-index-all.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"{len(results)} exact synthetic saved stages decoded and missing media rejected")
    return output


if __name__ == "__main__":
    prove()
