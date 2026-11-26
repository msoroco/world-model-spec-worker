"""Select the four exact door constructions for current-runtime CPU exercises."""

import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
NATIVE = FOLDER / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    cases, entries = [], []
    for number in (1, 2, 3, 4):
        case_id = FOLDER.name + "__probe_" + str(number)
        construction_path = NATIVE / ("probe-" + str(number) + "-construction.json")
        construction = json.loads(construction_path.read_text())
        config = json.loads((NATIVE / ("config-probe-" + str(number) + ".json")).read_text())
        kind = "cargo" if number >= 3 else "passenger"
        close = 212 if number % 2 else 400
        cases.append({"case_id": case_id, "target_law_id": "NRS-484B-153-3",
            "target_type": "boundary_probe",
            "rationale": "Compare requested door close timing with same transfer kind; original pixels and legal necessity require separate review",
            "variable_assignments": {"transfer_kind": {"kind": "controlled_context",
                    "value": kind, "unit": "categorical", "source": "selected Native configuration"},
                "requested_close_frame": {"kind": "controller", "value": close,
                    "unit": "frame", "source": "selected Native actuation schedule"}},
            "unresolved_judgment_calls": ["actual door motion and passing side",
                "immediate loading or unloading activity", "necessary open interval"],
            "recording_description": construction["recording_description"],
            "paired_probe_id": FOLDER.name + "__probe_" + str(number + (1 if number % 2 else -1)),
            "deliberate_differences": ["requested close frame 212 versus 400"],
            "probe": {"primary_variable": "requested_close_frame"}})
        entries.append({"case_id": case_id, "kind": "delivery",
            "construction": "native/" + construction_path.name,
            "construction_sha256": sha(construction_path),
            "candidate_risk": {"status": "physical",
                "reason": "Door motion, passing side, and transfer visibility require original CARLA readback"},
            "candidates": [], "measurement_procedure": {"entrypoint": "finalize.py"},
            "delivery_readiness": "cpu_preparation_in_progress_original_capture_pending",
            "measurement_contract": "native/selected-measurement-contract.json",
            "fixture_recipe": "work/" + FOLDER.name + "/native/probe-" + str(number) + "-fixture-recipe.json",
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    write(FOLDER / "proposals/cases.json", {"cell_id": "C228817",
        "actor": "motor_vehicle_driver", "status": "draft",
        "sweep_specs": [], "sweeps_expanded": True, "cases": cases})
    write(FOLDER / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": FOLDER.name,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "status": "draft_cpu_preparation", "cases": entries})
    return {"cases": len(entries), "manifest_sha256": sha(FOLDER / "execution-manifest.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
