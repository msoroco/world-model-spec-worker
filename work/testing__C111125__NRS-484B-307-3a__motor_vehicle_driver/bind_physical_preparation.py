"""Bind the selected CPU fixture receipts to each exact delivery case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main() -> None:
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest_path = folder / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(folder.name + "__")
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            log = f"physical-{suffix}-{kind}.log"
            result = f"physical-{suffix}-{kind}.json"
            command = (f".venv-cpu/bin/python work/{folder.name}/prove_physical.py "
                       f"--case {case} --kind {kind} "
                       f"--scratch .runtime-work/c111125-3a-owner/physical "
                       f"--result work/{folder.name}/{result}")
            fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                             "log": log, "log_sha256": sha(folder / log),
                             "result": result, "result_sha256": sha(folder / result)})
        lifecycle_log = f"lifecycle-{suffix}.log"
        lifecycle = {"events": ["capture_finished", "encoders_closed",
                                "restoration_verified", "native_exit",
                                "owner_released", "saved_processing_started"],
                     "command": (f".venv-cpu/bin/python work/{folder.name}/prove_lifecycle.py "
                                 f"--case {case} --scratch .runtime-work/c111125-3a-owner/physical"),
                     "exit_code": 0, "log": lifecycle_log,
                     "log_sha256": sha(folder / lifecycle_log)}
        receipt = {"format": "worker-physical-preparation-proof",
                   "case_id": case, "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures, "lifecycle": lifecycle,
                   "synthetic_fixture_only": True, "physical_acceptance_claimed": False}
        receipt_name = f"physical-preparation-{suffix}.json"
        write(folder / receipt_name, receipt)
        entry["physical_preparation"] = {"receipt": receipt_name,
                                         "sha256": sha(folder / receipt_name)}
        entry["kind"] = "delivery"
        offline_log = f"cpu-source-handoff-offline-{suffix}.log"
        entry["offline"] = {
            "construction_sha256": entry["construction_sha256"],
            "command": (f".venv-cpu/bin/python runtime.py offline --manifest "
                        f"work/{folder.name}/execution-manifest.draft.json "
                        f"--case {case} --output "
                        f".runtime-work/c111125-3a-owner/offline-v14-{suffix}"),
            "exit_code": 0, "log": offline_log,
            "log_sha256": sha(folder / offline_log)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
    write(manifest_path, manifest)
    write(folder / "execution-manifest.json", manifest)
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": sha(folder / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
