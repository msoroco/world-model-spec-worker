"""Bind exact diagnostic CPU receipts without claiming original delivery."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ("cycle_lane_through_intersection", "cycle_lane_before_intersection_only",
            "ordinary_lane_through_intersection", "cycle_lane_exception_unresolved")
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copied(source, destination):
    if not source.is_file():
        raise ValueError("Missing selected diagnostic proof: " + str(source))
    shutil.copyfile(source, destination)
    return sha(destination)


def bind():
    diagnostic = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = []
    for suffix, entry in zip(SUFFIXES, diagnostic["cases"]):
        case_id = plan["assignment_id"] + "__" + suffix
        if entry["case_id"] != case_id:
            raise ValueError("Diagnostic case ordering changed")
        folder = ROOT / "cases" / suffix
        construction = ROOT / entry["construction"]
        if sha(construction) != entry["construction_sha256"]:
            raise ValueError("Selected construction changed")
        offline_source = REPO / ".runtime-work" / ("c230223-offline-" + suffix + "-v5/offline.log")
        offline_log = folder / "offline.log"
        offline_hash = copied(offline_source, offline_log)
        compat = REPO / ".runtime-work" / ("c230223-compat-" + suffix + "-v5")
        compat_receipt = folder / "compatibility.json"
        compat_hash = copied(compat / "compatibility.json", compat_receipt)
        compat_log = folder / "cpu-compat-analysis.log"
        copied(compat / "compatibility-analysis.log", compat_log)
        negative_log = folder / "negative-analysis.log"
        copied(compat / "negative-analysis.log", negative_log)
        receipt = json.loads(compat_receipt.read_text())
        if (receipt["construction_sha256"] != entry["construction_sha256"] or
                receipt["log_sha256"] != sha(compat_log) or
                receipt["negative_log_sha256"] != sha(negative_log)):
            raise ValueError("Compatibility receipt differs from selected inputs")
        saved = REPO / ".runtime-work" / ("c230223-saved-" + suffix + "-v5/v0001/processing.json")
        saved_log = folder / "process-saved.json"
        saved_hash = copied(saved, saved_log)
        saved_receipt = json.loads(saved_log.read_text())
        if (saved_receipt.get("case_id") != case_id or
                saved_receipt.get("passed") is not True or
                saved_receipt.get("recorded_only") is not True or
                saved_receipt.get("originals_preserved") is not True):
            raise ValueError("Recorded-only selected saved receipt incomplete")
        fixtures = []
        for kind in KINDS:
            result = folder / ("physical-" + kind + ".json")
            log = folder / ("physical-" + kind + ".log")
            value = json.loads(result.read_text())
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if (value["physical_checks"]["maneuver"]["status"] != expected or
                    value.get("diagnostic_fixture") is not True):
                raise ValueError("Physical fixture outcome differs")
            fixtures.append({"kind": kind, "command": ".venv-cpu/bin/python " +
                str((ROOT / "prove_physical.py").relative_to(REPO)) + " --case " + case_id +
                " --kind " + kind + " --attempt $DIAGNOSTIC_ATTEMPT --output $RESULT",
                "exit_code": 0, "log": str(log.relative_to(ROOT)), "log_sha256": sha(log),
                "result": str(result.relative_to(ROOT)), "result_sha256": sha(result)})
        life_log = folder / "lifecycle.log"
        life = {"case_id": case_id,
                "events": ["capture_finished", "encoders_closed", "restoration_verified",
                           "native_exit", "owner_released", "saved_processing_started"],
                "exit_code": 0, "original_owner_release_claimed": False,
                "scope": "synthetic lifecycle protocol only",
                "command": ".venv-cpu/bin/python " + str((ROOT / "prove_lifecycle.py").relative_to(REPO)) +
                           " --case " + case_id + " --attempt $DIAGNOSTIC_ATTEMPT --saved-receipt $SAVED_RECEIPT",
                "log": str(life_log.relative_to(ROOT)), "log_sha256": sha(life_log)}
        physical = {"format": "c230223-diagnostic-physical-preparation-v1",
                    "case_id": case_id, "construction_sha256": entry["construction_sha256"],
                    "fixtures": fixtures, "lifecycle": life,
                    "source_kind": "synthetic_software_fixture", "physical_acceptance_claimed": False}
        physical_path = folder / "physical-preparation.json"
        write(physical_path, physical)
        delivery_script = ROOT / "prove_delivery_contract.py"
        delivery_positive = folder / "delivery-positive.log"
        delivery_negative = folder / "delivery-negative.log"
        if ("original Native cycle-lane attempt required" not in delivery_negative.read_text() or
                json.loads(delivery_positive.read_text()).get("original_delivery_claimed") is not False):
            raise ValueError("Diagnostic delivery positive/negative protocol incomplete")
        delivery = {"case_id": case_id, "sets": ["full-test"],
                    "checks": ["native_source", "all_participants", "time_join",
                               "full_video_decode", "actual_pixels", "physical_completion"],
                    "scope": "synthetic protocol CPU proof; original delivery pending",
                    "diagnostic_fixture": True,
                    "command": ".venv-cpu/bin/python " + str(delivery_script.relative_to(REPO)) +
                               " --case " + case_id +
                               " --mode diagnostic-positive --attempt $DIAGNOSTIC_ATTEMPT",
                    "negative_command": ".venv-cpu/bin/python " + str(delivery_script.relative_to(REPO)) +
                                        " --case " + case_id +
                                        " --mode delivery-negative --attempt $DIAGNOSTIC_ATTEMPT",
                    "test_exit_code": 0, "negative_exit_code": 1,
                    "negative_expected_error": "original Native cycle-lane attempt required",
                    "script": str(delivery_script.relative_to(ROOT)),
                    "script_sha256": sha(delivery_script),
                    "test_log": str(delivery_positive.relative_to(ROOT)),
                    "test_log_sha256": sha(delivery_positive),
                    "negative_log": str(delivery_negative.relative_to(ROOT)),
                    "negative_log_sha256": sha(delivery_negative)}
        entry.update({"kind": "delivery", "status": "source_gated_cpu_preparation",
            "offline": {"command": ".venv-cpu/bin/python runtime.py offline --manifest " +
                        str((ROOT / "diagnostic-execution-manifest.json").relative_to(REPO)) +
                        " --case " + case_id + " --output $OFFLINE_OUTPUT",
                        "exit_code": 0, "construction_sha256": entry["construction_sha256"],
                        "log": str(offline_log.relative_to(ROOT)), "log_sha256": offline_hash},
            "compatibility": {"receipt": str(compat_receipt.relative_to(ROOT)),
                              "sha256": compat_hash, "log": str(compat_log.relative_to(ROOT)),
                              "negative_log": str(negative_log.relative_to(ROOT))},
            "negative": {"log": str(negative_log.relative_to(ROOT))},
            "post_capture": {"recorded_only": True, "test_exit_code": 0,
                             "test_log": str(saved_log.relative_to(ROOT)), "test_log_sha256": saved_hash,
                             "command": ".venv-cpu/bin/python runtime.py process-saved --manifest " +
                                        str((ROOT / "execution-manifest.json").relative_to(REPO)) +
                                        " --case " + case_id + " --attempt $ATTEMPT --output $DERIVED" +
                                        " --library runtime/library --validator $VALIDATOR"},
            "physical_preparation": {"receipt": str(physical_path.relative_to(ROOT)),
                                     "sha256": sha(physical_path)},
            "delivery_acceptance": delivery,
            "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "acquisition": {name: {"entrypoint": "native_adapter.py", "method": "capture",
                                   "evidence": "source-gated original Native frame/body/camera readback"}
                            for name in ("ego_body_polygon", "intersection_cycle_lane_overlap",
                                         "reviewed_site_and_subsection_3")}})
        cases.append(entry)
    selected = {"format": "worker-execution-manifest", "assignment_id": plan["assignment_id"],
                "runtime_manifest_sha256": diagnostic["runtime_manifest_sha256"],
                "cases": cases, "comparisons": plan["comparisons"],
                "status": "source_gated_cpu_preparation", "original_delivery_claimed": False}
    write(ROOT / "execution-manifest.json", selected)
    proposals = json.loads((ROOT / "proposals/cases.json").read_text())
    by_id = {case["case_id"]: case for case in proposals["cases"]}
    for entry in cases:
        by_id[entry["case_id"]]["recording_description"] = json.loads(
            (ROOT / entry["construction"]).read_text())["recording_description"]
    write(ROOT / "proposals/cases.json", proposals)
    index_path = ROOT / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = sha(ROOT / "proposals/cases.json")
    write(index_path, index)
    return sha(ROOT / "execution-manifest.json")


if __name__ == "__main__":
    print(bind())
