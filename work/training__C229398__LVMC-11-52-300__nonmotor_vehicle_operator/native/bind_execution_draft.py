"""Bind current exact request, proposal and measurement contracts, still partial."""

import hashlib
import json
from pathlib import Path

from duration_policy import TARGETS


ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT = ROOT.name


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(data):
    return json.dumps(data, indent=2) + "\n"


def bind():
    proof = json.loads((ROOT / "native/duration-offline-proof.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    original = json.loads((Path("inputs") / ASSIGNMENT / "assignment.json").read_text())
    if {case["case_id"] for case in plan["cases"]} != {
            ASSIGNMENT + "__" + suffix for suffix in TARGETS}:
        raise ValueError("Duration plan changed")
    proposals = []
    entries = []
    for suffix, target_s in TARGETS.items():
        case_id = ASSIGNMENT + "__" + suffix
        offline = proof["cases"][suffix]
        construction_path = ROOT / offline["construction"]
        if digest(construction_path) != offline["construction_sha256"]:
            raise ValueError("Exact offline proof became stale")
        construction = json.loads(construction_path.read_text())
        proposals.append({"case_id": case_id, "target_law_id": original["law_id"],
                          "target_type": "compliant_attempt" if suffix != "above_30" else
                          "violating_attempt",
                          "rationale": "Exact source-bound strictly longer than thirty minutes boundary probe; physical and legal status unresolved",
                          "paired_probe_id": "c229398_duration_boundary",
                          "deliberate_differences": ["parking stop frame and derived approach target speed"],
                          "variable_assignments": {
                              "night_parking_duration_s": {"kind": "controller", "value": target_s},
                              "on_street": {"kind": "world_setup", "value": True},
                              "qualifying_nonmotor_review": {"kind": "world_setup", "value": "requires original source review"}},
                          "recording_description": construction["recording_description"],
                          "unresolved_judgment_calls": ["vehicle classification, parking purpose, street jurisdiction and continuous original episode"]})
        contract_path = ROOT / ("measurement-" + suffix + ".json")
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
                    "requirements": [{"disposition_index": 0,
                                      "requirement": plan["requirement_dispositions"][0]["requirement"],
                                      "source": plan["requirement_dispositions"][0]["source"],
                                      "method": "finalize", "output_key": "night_parking_duration",
                                      "value_type": "number", "kind": "measured",
                                      "inputs": ["native-actor-frames.jsonl", "review-source.json",
                                                 "street-geometry.json", "video_frames.jsonl"]}],
                    "negative": {"remove": ["street-geometry.json"],
                                 "error_contains": "Missing required source: street-geometry.json"}}
        contract_path.write_text(encoded(contract))
        entries.append({"case_id": case_id, "kind": "delivery",
                        "construction": offline["construction"],
                        "construction_sha256": offline["construction_sha256"],
                        "candidate_risk": {"status": "none", "reason":
                            "No observed original Native failure trigger yet; retain current primary request"},
                        "candidates": [], "delivery_readiness": "incomplete",
                        "offline": {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                            ASSIGNMENT + "/duration-construction-draft.json --case " + case_id +
                            " --output .runtime-work/c229398-duration-offline-v10-" + suffix,
                            "exit_code": 0, "construction_sha256": offline["construction_sha256"],
                            "log": offline["offline_log"],
                            "log_sha256": offline["offline_log_sha256"]},
                        "measurement_contract": contract_path.name,
                        "measurement_procedure": {"entrypoint": "finalize.py",
                                                  "output_schema": "c229398-parking-analysis-v1"},
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/fixture-" + suffix + ".json"})
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    (folder / "cases.json").write_text(encoded({"cell_id": original["cell_id"],
        "actor": original["actor"], "status": "draft", "cases": proposals,
        "sweep_specs": [], "sweeps_expanded": True}))
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": digest(Path("runtime/SOURCE-MANIFEST.json")),
                "status": "partial", "cases": entries}
    (ROOT / "execution-manifest.json").write_text(encoded(manifest))
    print(encoded({"cases": len(entries), "manifest_sha256": digest(ROOT /
                                                                     "execution-manifest.json")} ), end="")


if __name__ == "__main__":
    bind()
