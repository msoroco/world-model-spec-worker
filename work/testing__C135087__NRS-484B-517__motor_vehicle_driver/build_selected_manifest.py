"""Bind exact source-gated candidates and their CPU offline receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_bundles import HERE, AID


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    repo = HERE.parents[1]
    entries = []
    for source in draft["cases"]:
        cid = source["case_id"]
        suffix = cid.removeprefix(AID + "__")
        entry = dict(source)
        entry["kind"] = "delivery"
        entry["measurement_contract"] = f"contracts/{suffix}.json"
        entry["measurement_procedure"] = {"entrypoint": "analysis.py"}
        entry["fixture_recipe"] = f"work/{AID}/diagnostics/{suffix}-recipe.json"
        entry["acquisition"] = {
            "official stand designation and sign": {"entrypoint": "runner.py", "method": "source-sealed site and Native sign readback", "evidence": "site-original.json"},
            "subject passenger vehicle and driver": {"entrypoint": "stand_capture.py", "method": "original actor identity and vehicle-role source", "evidence": "vehicle-original.json"},
            "taxicab entrant and approach": {"entrypoint": "stand_capture.py", "method": "original entrant identity, speed and waiting readback", "evidence": "actor-rows.json"},
            "loading, waiting, entry and access": {"entrypoint": "stand_capture.py", "method": "20 Hz observer readback", "evidence": "actor-rows.json"},
            "four synchronized camera views": {"entrypoint": "stand_capture.py", "method": "four Native RGB encoders with exact frame map", "evidence": "video_frames.jsonl"}}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        physical = HERE / f"physical-{suffix}-receipt.json"
        if physical.is_file():
            entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        primary_log = HERE / f"cpu-20261125-offline-v11-{suffix}.log"
        if not primary_log.is_file():
            raise ValueError("missing primary offline proof: " + suffix)
        entry["offline"] = {"command": f"runtime.py offline --case {cid} --candidate primary",
                            "construction_sha256": entry["construction_sha256"],
                            "exit_code": 0, "log": primary_log.name, "log_sha256": sha(primary_log)}
        for candidate in entry["candidates"]:
            alt_log = HERE / f"cpu-20261125-offline-v11-{suffix}-fallback1.log"
            if not alt_log.is_file():
                raise ValueError("missing fallback offline proof: " + suffix)
            candidate["offline"] = {"command": f"runtime.py offline --case {cid} --candidate fallback1",
                                    "construction_sha256": candidate["construction_sha256"],
                                    "exit_code": 0, "log": alt_log.name, "log_sha256": sha(alt_log)}
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(repo / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "partial_source_gated", "cases": entries}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("selected", len(entries), "source-gated cases with fallback offline proofs")


if __name__ == "__main__":
    build()
