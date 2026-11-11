"""Bind the selected alley pair to a draft canonical cases proposal.

The physical access judgment remains unresolved. The separate judgment sweep
is explicitly incomplete until a source-backed access geometry and a measured
physical range can support a fixed sampling plan.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from batch_pipeline import stages


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def build() -> dict:
    proposals = ROOT / "proposals"
    binding = read(proposals / "bindings.json")
    template = read(proposals / "template.json")
    template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = read(
        proposals / "judgment_observables_blocking.json")["observable_requirements"]
    manifest = read(ROOT / "execution-manifest.json")
    assignment = read(REPO / "inputs" / ROOT.name / "assignment.json")
    phrase = template["structure"]["judgment_calls_needed"][0]
    reference = next(c for c in manifest["cases"] if c["case_id"].endswith("__reference"))
    selected = read(ROOT / reference["construction"])
    recording = selected["recording_description"]
    common = {
        "alley_geometry": {"kind": "world_setup", "value": "authored alley with Native survey pending"},
        "abutting_property_access": {"kind": "world_setup", "value": "authored entrance; property access pending verification"},
        "ego_trajectory": {"kind": "subject_behavior", "value": None},
        "commanded_stop_station_m": {"kind": "controller", "value": -12.0},
        "commanded_approach_speed_mps": {"kind": "controller", "value": 5.0},
        "camera_policy": {"kind": "controller", "value": "four_view_nominal"},
    }
    cases = [{
        "case_id": ROOT.name + "__baseline",
        "target_law_id": None,
        "target_type": "baseline",
        "rationale": "Neutral reference setup definition; no baseline recording is selected.",
        "variable_assignments": common,
        "recording_description": recording,
        "unresolved_judgment_calls": [],
    }]
    for suffix, station, overlap in (("reference", -12.0, 0.0), ("contrast", 0.0, 5.2)):
        assignments = json.loads(json.dumps(common))
        assignments["commanded_stop_station_m"]["value"] = station
        cases.append({
            "case_id": ROOT.name + "__" + suffix,
            "target_law_id": assignment["law_id"],
            "target_type": "boundary_probe",
            "rationale": "Selected descriptive entrance-footprint comparison; no legal blocking label or numeric cutoff is inferred.",
            "variable_assignments": assignments,
            "recording_description": recording,
            "unresolved_judgment_calls": [phrase["phrase"]],
            "paired_probe_id": "alley_entrance_position_pair",
            "deliberate_differences": ["commanded_stop_station_m"],
            "probe": {
                "primary_variable": "commanded_stop_station_m",
                "comparison_or_standard": "paired observed footprint at the same authored entrance",
                "target_value_or_branch": station,
                "descriptive_overlap_target_m": overlap,
            },
        })
    output = {
        "cell_id": assignment["cell_id"],
        "actor": assignment["actor"],
        "status": "draft",
        "cases": cases,
        "sweep_specs": [{
            "sweep_id": "alley_access_obstruction_judgment",
            "target_law_id": assignment["law_id"],
            "judgment_refs": [phrase],
            "status": "incomplete",
            "rationale": "The selected pair samples footprint position only; legal access obstruction needs a source-backed physical range and separate judgment review.",
            "missing_inputs": [
                "Source-backed Native abutting-property access boundary and usable passage geometry",
                "Measured feasible stop-station range and resolution for an independent fixed physical sweep",
            ],
        }],
    }
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(output, templates=[template], bindings=binding)
    rules = read(stages.ROOT / "data/canonical_parameter_aliases.json")
    stages.validate("cases", output, {
        "request": {"cell": assignment["cell"], "actor": assignment["actor"]},
        "dependencies": [binding], "templates": [template],
        "canonical_parameter_rules": rules, "judgment_completion_policy": {},
    })
    path = proposals / "cases.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    foundation = read(proposals / "semantic-foundation-proof.json")
    index = {
        "format": "worker-semantic-delivery",
        "assignment_id": ROOT.name,
        "stages": {**foundation["references"],
                   "cases": {"path": "proposals/cases.json", "sha256": sha(path)}},
    }
    index_path = proposals / "semantic-index.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    # The standalone frozen assignment exports this object as law_record;
    # the current semantic validator expects the local adopter's law key.
    # Test the exact stage chain with a read-only adapter, leaving inputs and
    # runtime untouched and retaining the mismatch for the strict gate.
    from worker_exchange.semantic_delivery import validate as validate_delivery
    normalized = {**assignment, "law": assignment["law_record"]}
    stage_proof = validate_delivery(ROOT, normalized, manifest)
    proof_path = proposals / "semantic-cases-proof.json"
    proof_path.write_text(json.dumps({
        "format": "c10014-semantic-cases-proof-v1",
        "cases_sha256": sha(path), "index_sha256": sha(index_path),
        "read_only_law_record_adapter": True,
        "stage_validation": stage_proof,
        "judgment_sweep_complete": False,
        "original_native_observed": False,
    }, indent=2) + "\n")
    return {"cases_stage_validated": True, "selected_cases": 2,
            "judgment_sweep_complete": False, "cases_sha256": sha(path),
            "index_sha256": sha(index_path), "proof_sha256": sha(proof_path)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
