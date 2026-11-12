"""CPU proof of exact local audit staging, with no local state modification."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("local_audit_import", HERE / "prepare-local-audit-import.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def rejects(action):
    try:
        action()
    except ValueError:
        return True
    raise AssertionError("Changed local audit source accepted")


def main():
    plan = MODULE.plan()
    retained = json.loads((HERE / "update032-local-audit-import-plan.json").read_text())
    if retained != plan:
        raise ValueError("Retained local import plan differs")
    rejected = []
    with tempfile.TemporaryDirectory(prefix="c110454-local-audit-") as folder:
        target_root = Path(folder)
        (target_root / "batch.json").symlink_to(ROOT / "batch.json")
        (target_root / "work").mkdir()
        (target_root / "work" / HERE.name).symlink_to(HERE, target_is_directory=True)
        first = MODULE.install(target_root)
        second = MODULE.install(target_root)
        if first["copied"] is not True or second["copied"] is not False:
            raise AssertionError("Local import should copy once and verify on retry")
        staged = target_root / MODULE.DESTINATION
        if MODULE.sha(staged) != plan["auditor_sha256"]:
            raise AssertionError("Local auditor bytes differ")
        help_run = subprocess.run([sys.executable, str(staged), "--help"],
                                  cwd=ROOT, capture_output=True, text=True)
        if help_run.returncode or "--decode-receipt" not in help_run.stdout:
            raise AssertionError("Staged local auditor cannot import or expose required CLI")
        staged.write_text(staged.read_text() + "\n# changed\n")
        rejects(lambda: MODULE.install(target_root))
        rejected.append("changed_existing_local_auditor")
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["cases"][0]["delivery_acceptance"]["script_sha256"] = "0" * 64
    rejects(lambda: MODULE.plan(manifest=bad_manifest))
    rejected.append("manifest_auditor_hash")
    queue = json.loads((HERE / "update020-selected-queue-fragment.json").read_text())
    bad_queue = copy.deepcopy(queue)
    bad_queue["cases"][0]["additional_source_audit_command"] = "echo wrong"
    rejects(lambda: MODULE.plan(fragment=bad_queue))
    rejected.append("queue_local_auditor_path")
    proof = {"format": "c110454-local-audit-import-cpu-proof-v1",
             "manifest_sha256": plan["manifest_sha256"],
             "queue_sha256": plan["queue_sha256"],
             "plan_sha256": hashlib.sha256((HERE / "update032-local-audit-import-plan.json").read_bytes()).hexdigest(),
             "auditor_sha256": plan["auditor_sha256"],
             "staged_cli_import_passed": True, "idempotent_install_passed": True,
             "rejected_mutations": rejected,
             "local_operations_modified": False,
             "original_or_physical_acceptance_claimed": False}
    output = HERE / "update032-local-audit-import-proof.json"
    output.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof))


if __name__ == "__main__":
    main()
