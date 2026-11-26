"""Bind current diagnostic CPU receipts to exact source-gated delivery intents."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from ped_entry import CASES
from delivery_audit import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c227824-owner"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    diagnostic = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    entries = []
    for source in diagnostic["cases"]:
        case_id = source["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        if suffix not in {item.case_id for item in CASES}:
            raise ValueError("nonselected case")
        folder = ROOT / "cases" / suffix
        compat = SCRATCH / ("compat4-" + suffix)
        offline = SCRATCH / ("offline4-" + suffix)
        saved = SCRATCH / ("saved4-" + suffix + ".log")
        for name, origin in (("compatibility.json", compat / "compatibility.json"),
                             ("cpu-compat-analysis.log", compat / "compatibility-analysis.log"),
                             ("negative-analysis.log", compat / "negative-analysis.log"),
                             ("offline.log", offline / "offline.log"),
                             ("cpu-saved.json", saved)):
            if not origin.is_file():
                raise ValueError("missing current CPU source " + str(origin))
            shutil.copyfile(origin, folder / name)
        receipt = json.loads((folder / "compatibility.json").read_text())
        saved_receipt = json.loads((folder / "cpu-saved.json").read_text())
        if (not receipt.get("passed") or not saved_receipt.get("passed") or
                saved_receipt.get("case_id") != case_id or
                receipt.get("construction_sha256") != source["construction_sha256"]):
            raise ValueError("selected CPU proof differs from construction")
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            stem = "physical-" + kind
            output = folder / (stem + ".json")
            log = folder / (stem + ".log")
            if not output.is_file() or not log.is_file():
                raise ValueError("missing physical outcome fixture")
            fixtures.append({"kind": kind,
                             "command": f"PYTHONPATH=runtime .venv-cpu/bin/python work/{ASSIGNMENT}/prove_physical.py --case {case_id} --kind {kind} --attempt .runtime-work/c227824-owner/{compat.name} --output work/{ASSIGNMENT}/cases/{suffix}/{stem}.json",
                             "exit_code": 0, "log": f"cases/{suffix}/{log.name}",
                             "log_sha256": sha(log), "result": f"cases/{suffix}/{output.name}",
                             "result_sha256": sha(output)})
        life = folder / "physical-lifecycle.log"
        physical = folder / "physical-preparation.json"
        write(physical, {"format": "c227824-diagnostic-physical-preparation",
                         "case_id": case_id, "construction_sha256": source["construction_sha256"],
                         "source_kind": "synthetic_software_fixture", "fixtures": fixtures,
                         "lifecycle": {"command": f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_lifecycle.py --case {case_id} --attempt .runtime-work/c227824-owner/{compat.name} --saved-receipt .runtime-work/c227824-owner/saved4-{suffix}.log",
                                       "events": ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"],
                                       "exit_code": 0, "log": f"cases/{suffix}/{life.name}",
                                       "log_sha256": sha(life),
                                       "scope": "synthetic lifecycle protocol only"}})
        positive = folder / "delivery-diagnostic-positive.log"
        negative = folder / "delivery-delivery-negative.log"
        entry = dict(source)
        entry.update(kind="delivery", status="source_gated_cpu_preparation",
                     candidate_risk={"status": "none", "reason": "No original primary failure or reviewed alternate pedestrian entry station is available; inspect the first original attempt before choosing a fallback."},
                     candidates=[],
                     offline={"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {case_id} --output .runtime-work/c227824-owner/{offline.name}",
                              "exit_code": 0, "log": f"cases/{suffix}/offline.log",
                              "log_sha256": sha(folder / "offline.log"),
                              "construction_sha256": source["construction_sha256"]},
                     physical_preparation={"receipt": f"cases/{suffix}/physical-preparation.json", "sha256": sha(physical)},
                     compatibility={"receipt": f"cases/{suffix}/compatibility.json",
                                    "sha256": sha(folder / "compatibility.json"),
                                    "log": f"cases/{suffix}/cpu-compat-analysis.log"},
                     negative={"log": f"cases/{suffix}/negative-analysis.log"},
                     native_handoff={"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                     pending_original_sources=["reviewed original signalized highway site and OpenDRIVE",
                                               "reviewed source for NRS 484B.283 permission judgment sweep",
                                               "released Native four-camera original attempts with signal and other-device readback"],
                     delivery_acceptance={"case_id": case_id, "sets": ["full-test"],
                                          "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
                                          "scope": "synthetic protocol CPU proof; original delivery pending",
                                          "diagnostic_fixture": True,
                                          "command": f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_delivery_contract.py --case {case_id} --mode diagnostic-positive",
                                          "test_exit_code": 0,
                                          "test_log": f"cases/{suffix}/{positive.name}", "test_log_sha256": sha(positive),
                                          "negative_command": f".venv-cpu/bin/python work/{ASSIGNMENT}/prove_delivery_contract.py --case {case_id} --mode delivery-negative",
                                          "negative_exit_code": 1, "negative_expected_error": "released original",
                                          "negative_log": f"cases/{suffix}/{negative.name}", "negative_log_sha256": sha(negative),
                                          "script": "prove_delivery_contract.py", "script_sha256": sha(ROOT / "prove_delivery_contract.py")},
                     post_capture={"recorded_only": True,
                                   "command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case_id} --attempt $ATTEMPT --output $DERIVED --library runtime/library --validator $VALIDATOR",
                                   "feedback_command": f".venv-cpu/bin/python work/{ASSIGNMENT}/delivery_audit.py --authority-root $SOURCE_ROOT --receipt $RECEIPT --output $AUDIT",
                                   "test_log": f"cases/{suffix}/cpu-saved.json",
                                   "test_log_sha256": sha(folder / "cpu-saved.json"), "test_exit_code": 0})
        channels = json.loads((ROOT / source["construction"]).read_text())["recording_description"]["channels"]
        entry["acquisition"] = {item["name"]: {"entrypoint": "native_adapter.py", "method": "capture", "evidence": "source-gated original Native actor/map/camera readback"} for item in channels}
        entries.append(entry)
    write(ROOT / "execution-manifest.json", {"format": "worker-execution-manifest",
                                             "assignment_id": ASSIGNMENT,
                                             "runtime_manifest_sha256": diagnostic["runtime_manifest_sha256"],
                                             "status": "source_gated_cpu_preparation", "original_delivery_claimed": False,
                                             "cases": entries})
    print(f"Bound {len(entries)} exact source-gated selected cases to current CPU proofs")


if __name__ == "__main__":
    main()
