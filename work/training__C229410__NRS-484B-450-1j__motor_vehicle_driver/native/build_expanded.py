"""Build exact but still partial Native bundles for omitted statutory branches."""
import hashlib
import json
from pathlib import Path

from branch_variants import BRANCHES

HERE = Path(__file__).resolve().parent
ASSIGNMENT_ROOT = HERE.parent
ASSIGNMENT = ASSIGNMENT_ROOT.name
CAMERAS = ["overview", "approach", "reference_corner", "driver_reference"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for suffix, branch in BRANCHES.items():
        if suffix in ("controlled_1", "controlled_2"):
            continue
        case_id = ASSIGNMENT + "__" + suffix
        description = {"channels": [{"name": "parking_geometry", "unit": "mixed",
            "sampling_rate_hz": 20, "method": "original Native full-body corners and speed readback",
            "time_window": "600 frames", "reference_frame": "sourced highway and fire-station entrance",
            "uncertainty": "50 ms interval; statutory distance reference unresolved"}],
            "context_inputs": [],
            "limitations": ["Raw body-edge gap is not a legal distance verdict",
                "Actual station, entrance, direction and pixels require independent review"]}
        config = {"case_id": case_id, "case_suffix": suffix, "cell_id": "C229410",
            "law_id": "NRS-484B-450-1j", "actor": "motor_vehicle_driver",
            "duration_s": 30, "rate_hz": 20, "cameras": CAMERAS,
            "initial_activity": branch.activity, "exception_context": branch.exception,
            "selected_case_id": case_id, "supported_case_ids": [case_id],
            "candidate_id": "primary", "required_atoms": [], "source_packets": [],
            "case": {"case_id": case_id}, "recording_description": description,
            "target": "source-reviewed " + branch.activity + " at " + branch.side + " side"}
        files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
        for name in ("branch_variants.py", "expanded_layout.py", "expanded_controller.py",
                     "expanded_measurement.py", "measure_entrance.py", "source_context.py",
                     "expanded_finalize.py"):
            files.append({"path": name, "content": (HERE / name).read_text()})
        files.append({"path": "runner.py", "content": (HERE / "expanded_runner.py").read_text()})
        files.append({"path": "finalize.py", "content": (HERE / "expanded_finalize.py").read_text()})
        files.append({"path": "tests/test_expanded_bundle.py",
                      "content": (HERE / "tests/test_expanded_bundle.py").read_text()})
        for name in ("assignment.json", "witnesses.json"):
            source = Path("inputs") / ASSIGNMENT / name
            files.append({"path": name, "content": source.read_text()})
        proposal = {"case_id": case_id, "cell_id": "C229410", "law_id": "NRS-484B-450-1j",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
            "recording_description": description, "status": "partial_branch_construction",
            "physical_acceptance_claimed": False}
        target = HERE / "bundles" / suffix / "construction.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proposal, indent=2) + "\n")
        entry = {"case_id": case_id, "kind": "delivery",
                 "construction": str(target.relative_to(ASSIGNMENT_ROOT)),
                 "construction_sha256": sha(target), "candidates": [],
                 "delivery_readiness": "incomplete"}
        log = ASSIGNMENT_ROOT / "expanded-offline" / (suffix + ".log")
        if log.is_file() and '"offline_passed": true' in log.read_text():
            entry["offline"] = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                ASSIGNMENT + "/expanded-native-manifest.json --case " + case_id +
                " --output .runtime-work/c229410-expanded-" + suffix + "-v3",
                "exit_code": 0, "log": str(log.relative_to(ASSIGNMENT_ROOT)),
                "log_sha256": sha(log)}
        entries.append(entry)
    path = ASSIGNMENT_ROOT / "expanded-native-manifest.json"
    path.write_text(json.dumps({"format": "worker-partial-expanded-native-manifest",
        "assignment_id": ASSIGNMENT, "cases": entries,
        "physical_acceptance_claimed": False}, indent=2) + "\n")
    return {"case_count": len(entries), "manifest": str(path)}


if __name__ == "__main__":
    print(json.dumps(build()))
