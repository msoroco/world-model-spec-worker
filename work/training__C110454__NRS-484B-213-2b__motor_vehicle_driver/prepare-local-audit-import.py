"""Prepare the exact C110454 auditor for a later local operations import.

Default mode writes only a textual plan in this assignment.  --install requires
an explicit target root; the worker proof uses a temporary root, not local state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "batch.json").is_file())
AID = HERE.name
DESTINATION = Path("state/operations/worker_exchange/full-train-delivery/delivery_audit.py")
DEPENDENCIES = ("camera_lifecycle_audit.py", "physical_motion_audit.py",
                "source_join_audit.py")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def plan(manifest: dict | None = None, fragment: dict | None = None) -> dict:
    manifest_path = HERE / "execution-manifest.json"
    queue_path = HERE / "update020-selected-queue-fragment.json"
    manifest = read(manifest_path) if manifest is None else manifest
    fragment = read(queue_path) if fragment is None else fragment
    auditor = HERE / "delivery_audit.py"
    digest = sha(auditor)
    cases = manifest.get("cases", [])
    rows = fragment.get("cases", [])
    require(manifest.get("assignment_id") == fragment.get("assignment_id") == AID and
            len(cases) == len(rows) == 6 and
            fragment.get("manifest_sha256") == sha(manifest_path),
            "Local import selection or queue source differs")
    for case, row in zip(cases, rows):
        acceptance = case.get("delivery_acceptance", {})
        require(row.get("case_id") == case.get("case_id") and
                acceptance.get("case_id") == case.get("case_id") and
                acceptance.get("script") == auditor.name and
                acceptance.get("script_sha256") == digest and
                str(DESTINATION) in shlex.split(row.get("additional_source_audit_command", "")),
                "Local auditor path or hash differs for " + str(case.get("case_id")))
    return {"format": "c110454-local-audit-import-plan-v1",
            "assignment_id": AID, "destination": str(DESTINATION),
            "auditor_source": str(auditor.relative_to(ROOT)),
            "auditor_sha256": digest,
            "dependency_sha256": {name: sha(HERE / name) for name in DEPENDENCIES},
            "manifest_sha256": sha(manifest_path), "queue_sha256": sha(queue_path),
            "case_count": len(cases), "installed_in_local_operations": False,
            "original_or_physical_acceptance_claimed": False}


def install(target_root: Path) -> dict:
    spec = plan()
    target_root = target_root.resolve()
    target = target_root / DESTINATION
    source = HERE / "delivery_audit.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        require(target.is_file() and sha(target) == spec["auditor_sha256"],
                "Existing local auditor differs; preserve it for review")
        changed = False
    else:
        target.write_bytes(source.read_bytes())
        changed = True
    require(sha(target) == spec["auditor_sha256"], "Imported local auditor hash differs")
    return {"destination": str(target), "auditor_sha256": spec["auditor_sha256"],
            "copied": changed, "source_binding_verified": True,
            "original_or_physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--target-root", type=Path)
    args = parser.parse_args()
    if args.install:
        require(args.target_root is not None, "Explicit local target root required")
        print(json.dumps(install(args.target_root)))
    else:
        require(args.target_root is None, "Target root requires --install")
        receipt = plan()
        (HERE / "update032-local-audit-import-plan.json").write_text(
            json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt))
