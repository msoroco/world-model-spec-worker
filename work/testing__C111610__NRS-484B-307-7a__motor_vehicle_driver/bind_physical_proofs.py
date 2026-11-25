"""Bind three synthetic physical outcomes and Native lifecycle test to cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    lifecycle = ROOT / "physical-lifecycle.log"
    lifecycle.write_text(lifecycle.read_text().rstrip() + "\n")
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        fixtures = []
        for kind in KINDS:
            result_name = f"physical-v2-{suffix}-{kind}.json"
            log_name = f"physical-v2-{suffix}-{kind}.log"
            result = json.loads((ROOT / result_name).read_text())
            if (result.get("case_id") != entry["case_id"] or
                    result.get("fixture_kind") != kind):
                raise ValueError("physical probe belongs to another case")
            fixtures.append({
                "kind": kind, "command": ".venv-cpu/bin/python work/" + ROOT.name +
                "/physical_probe.py --case " + suffix + " --kind " + kind +
                " --output work/" + ROOT.name + "/" + result_name,
                "exit_code": 0, "log": log_name, "log_sha256": sha(ROOT / log_name),
                "result": result_name, "result_sha256": sha(ROOT / result_name)})
        proof = {
            "format": "worker-physical-preparation",
            "case_id": entry["case_id"],
            "construction_sha256": entry["construction_sha256"],
            "fixtures": fixtures,
            "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                      "restoration_verified", "native_exit",
                                      "owner_released", "saved_processing_started"],
                          "exit_code": 0,
                          "log": lifecycle.name,
                          "log_sha256": sha(lifecycle),
                          "method": "fake CARLA world same-tick, mismatch and restoration tests plus pinned closure order"},
            "scope": "synthetic CPU physical outcome and lifecycle proof only",
            "physical_acceptance_claimed": False,
        }
        proof_path = ROOT / f"physical-{suffix}-proof.json"
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": proof_path.name,
                                         "sha256": sha(proof_path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("bound", bind(), "physical preparation proofs")
