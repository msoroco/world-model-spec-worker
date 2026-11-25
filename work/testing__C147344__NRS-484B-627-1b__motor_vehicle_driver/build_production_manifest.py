"""Bind selected production intent to diagnostic CPU proofs without promotion.

The execution manifest remains source gated while original site and judgment
inputs are unavailable. Compatibility and physical receipts are diagnostic.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SCRATCH = REPO / ".runtime-work/c147344-owner"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    diagnostic = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
    entries = []
    for source in diagnostic["cases"]:
        case = source["case_id"]
        suffix = case.removeprefix(ASSIGNMENT + "__")
        if suffix not in VARIANTS:
            raise ValueError("nonselected diagnostic case")
        short = "middle" if suffix == "slow_middle_follower" else suffix
        folder = HERE / "cases" / suffix
        attempt = SCRATCH / f"pinned-compat-v7-{short}"
        for name, origin in (("compatibility.json", attempt / "compatibility.json"),
                             ("compatibility-analysis.log", attempt / "compatibility-analysis.log"),
                             ("negative-analysis.log", attempt / "negative-analysis.log"),
                             ("offline.log", SCRATCH / f"offline-v7-{suffix}" / "offline.log")):
            shutil.copyfile(origin, folder / name)
        if sha(folder / "compatibility.json") != sha(attempt / "compatibility.json"):
            raise ValueError("compatibility receipt changed")
        construction_sha = source["construction_sha256"]
        physics = folder / "physical-preparation.json"
        command_base = f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_delivery_contract.py --case {case}"
        entry = dict(source)
        entry.update(kind="delivery", status="source_gated_cpu_preparation",
                     offline={"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {case} --output .runtime-work/c147344-owner/offline-v7-{suffix}",
                              "exit_code": 0, "log": f"cases/{suffix}/offline.log",
                              "log_sha256": sha(folder / "offline.log"),
                              "construction_sha256": construction_sha},
                     physical_preparation={"receipt": f"cases/{suffix}/physical-preparation.json",
                                           "sha256": sha(physics)},
                     compatibility={"receipt": f"cases/{suffix}/compatibility.json",
                                    "sha256": sha(folder / "compatibility.json"),
                                    "log": f"cases/{suffix}/compatibility-analysis.log"},
                     negative={"log": f"cases/{suffix}/negative-analysis.log"},
                     native_handoff={"python_env_var": "CARLA_PYTHON",
                                     "host_env_var": "CARLA_HOST",
                                     "port_env_var": "CARLA_PORT"},
                     pending_original_sources=["reviewed original highway site and OpenDRIVE",
                                               "reviewed impediment and passing necessity sweep ranges",
                                               "released Native four-camera attempts"],
                     delivery_acceptance={"case_id": case, "sets": ["full-test"],
                                          "checks": ["native_source", "all_participants",
                                                     "time_join", "full_video_decode",
                                                     "actual_pixels", "physical_completion"],
                                          "scope": "synthetic protocol CPU proof; original delivery pending",
                                          "diagnostic_fixture": True,
                                          "command": command_base + " --mode diagnostic-positive",
                                          "test_exit_code": 0,
                                          "test_log": f"cases/{suffix}/delivery-positive.log",
                                          "test_log_sha256": sha(folder / "delivery-positive.log"),
                                          "negative_command": command_base + " --mode delivery-negative",
                                          "negative_exit_code": 1,
                                          "negative_expected_error": "released original",
                                          "negative_log": f"cases/{suffix}/delivery-negative.log",
                                          "negative_log_sha256": sha(folder / "delivery-negative.log"),
                                          "script": "prove_delivery_contract.py",
                                          "script_sha256": sha(HERE / "prove_delivery_contract.py")},
                     post_capture={"recorded_only": True,
                                   "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR",
                                   "feedback_command": f".venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT",
                                   "test_log": f"cpu-pinned-saved-{suffix}.json",
                                   "test_log_sha256": sha(HERE / f"cpu-pinned-saved-{suffix}.json"),
                                   "test_exit_code": 0})
        required = {ch["name"] for ch in json.loads((HERE / source["construction"]).read_text())["recording_description"]["channels"]}
        entry["acquisition"] = {name: {"entrypoint": "native_adapter.py",
                                         "method": "capture",
                                         "evidence": "source-gated original Native actor/map/camera readback"}
                                for name in sorted(required)}
        entries.append(entry)
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": diagnostic["runtime_manifest_sha256"],
        "status": "source_gated_cpu_preparation", "original_delivery_claimed": False,
        "cases": entries})
    print("Bound four selected production intents to diagnostic CPU proofs")


if __name__ == "__main__":
    main()
