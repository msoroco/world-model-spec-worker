"""Add pinned engineering CPU proofs to the ten-case selected delivery manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engineering_sweep_station import engineering_station
from reviewed_scene import ASSIGNMENT

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    diagnostic = json.loads((HERE / "engineering-diagnostic-manifest.json").read_text())
    old = [entry for entry in manifest["cases"] if engineering_station(entry["case_id"]) is None]
    if len(old) != 4:
        raise ValueError("four sealed selected anchors required")
    entries = list(old)
    for source in diagnostic["cases"]:
        case = source["case_id"]
        if engineering_station(case) is None:
            raise ValueError("unlisted engineering case")
        suffix = case.removeprefix(ASSIGNMENT + "__")
        folder = HERE / "cases" / suffix
        construction = json.loads((HERE / source["construction"]).read_text())
        channels = {channel["name"] for channel in construction["recording_description"]["channels"]}
        base = f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_engineering_delivery.py --case {case}"
        entry = dict(source)
        entry.update(
            kind="delivery", status="source_gated_cpu_preparation",
            candidate_risk=source["candidate_risk"],
            offline={"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/engineering-diagnostic-manifest.json --case {case} --output .runtime-work/c147344-owner-nov26/offline-final-{suffix}",
                     "exit_code": 0, "log": f"cases/{suffix}/offline.log",
                     "log_sha256": sha(folder / "offline.log"),
                     "construction_sha256": source["construction_sha256"]},
            physical_preparation={"receipt": f"cases/{suffix}/physical-preparation.json",
                                  "sha256": sha(folder / "physical-preparation.json")},
            compatibility={"receipt": f"cases/{suffix}/compatibility.json",
                           "sha256": sha(folder / "compatibility.json"),
                           "log": f"cases/{suffix}/cpu-compat-analysis.log"},
            negative={"log": f"cases/{suffix}/negative-analysis.log"},
            acquisition={name: {"entrypoint": "sweep_native_adapter.py", "method": "capture",
                                "evidence": "source-gated original Native actor/map/camera and speed readback"}
                         for name in sorted(channels)},
            native_handoff={"python_env_var": "CARLA_PYTHON",
                            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            pending_original_sources=["reviewed original highway site and OpenDRIVE",
                                      "original speed, lane, follower and camera readbacks",
                                      "reviewed legal assessment of impediment and pass necessity"],
            delivery_acceptance={
                "case_id": case, "sets": ["full-test"],
                "checks": ["native_source", "all_participants", "time_join",
                           "full_video_decode", "actual_pixels", "physical_completion"],
                "scope": "synthetic protocol CPU proof; original delivery pending",
                "diagnostic_fixture": True,
                "command": base + " --mode diagnostic-positive", "test_exit_code": 0,
                "test_log": f"cases/{suffix}/delivery-positive.log",
                "test_log_sha256": sha(folder / "delivery-positive.log"),
                "negative_command": base + " --mode delivery-negative",
                "negative_exit_code": 1, "negative_expected_error": "released original",
                "negative_log": f"cases/{suffix}/delivery-negative.log",
                "negative_log_sha256": sha(folder / "delivery-negative.log"),
                "script": "prove_engineering_delivery.py",
                "script_sha256": sha(HERE / "prove_engineering_delivery.py"),
            },
            post_capture={
                "recorded_only": True,
                "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR",
                "feedback_command": f".venv-cpu/bin/python work/{ASSIGNMENT}/engineering_delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT",
                "test_log": f"cpu-pinned-saved-{suffix}.json",
                "test_log_sha256": sha(HERE / f"cpu-pinned-saved-{suffix}.json"),
                "test_exit_code": 0,
            },
        )
        entries.append(entry)
    manifest["cases"] = entries
    write(HERE / "execution-manifest.json", manifest)
    index_path = HERE / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = sha(HERE / "proposals/cases.json")
    write(index_path, index)
    print("Bound", len(entries), "selected exact cases")


if __name__ == "__main__":
    main()
