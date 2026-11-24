"""Bind all five exact branches to the selected compatibility path."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLICIES = {
    "probe_a": (True, False, True),
    "probe_b": (False, False, True),
    "pursuit": (False, True, True),
    "call_lamps_only": (True, False, False),
    "ordinary_lamps_only": (False, False, False),
    "sweep_0": (False, True, True),
    "sweep_1": (False, True, True),
    "sweep_2": (False, True, True),
    "sweep_3": (False, True, True),
}
SWEEP = {"sweep_0": (500, 10), "sweep_1": (500, 20),
         "sweep_2": (600, 10), "sweep_3": (600, 20)}
JUDGMENTS = [
    {"phrase": "under normal conditions", "note":
     "Equipment audibility at 500 feet requires a qualified original acoustic assessment."},
    {"phrase": "actual or suspected violator of the law", "note":
     "Pursuit purpose and the factual status of a suspected violator require original dispatch and incident sources."},
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    config = json.loads((HERE / "native/config.json").read_text())
    proposals, entries = [], []
    for suffix, (call, pursuit, siren) in POLICIES.items():
        observer_distance, approach_distance = SWEEP.get(suffix, (500, 10))
        case_id = HERE.name + "__" + suffix
        construction = HERE / "draft-candidates" / suffix / "primary/construction.json"
        selected = HERE / "selected-fixture" / suffix / "measurement-contract.json"
        contract = {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{
                "disposition_index": 0, "requirement": "NRS-484D-400-5",
                "source": "NRS 484D.400(5)", "output_key": "siren_source_measurement",
                "method": "siren_source_measurement", "value_type": "object",
                "kind": "measured", "inputs": [
                    "native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
                    "capture/evidence.jsonl", "microphone-pcm16.json",
                    "audio_observations.jsonl", "dispatch.jsonl",
                    "dispatch-source.json", "vehicle-authorization.json",
                    "acoustic-report.json"]}],
            "negative": {"remove": ["audio_observations.jsonl"],
                         "error_contains": "Missing required source: audio_observations.jsonl"}}
        write(selected, contract)
        target = ("compliant_attempt" if suffix == "probe_a" else
                  "violating_attempt" if suffix == "probe_b" else
                  "judgment_sweep" if suffix in SWEEP else "boundary_probe")
        proposal_case = {"case_id": case_id,
            "target_law_id": "NRS-484D-400-5",
            "target_type": target,
            "cell_id": "C109028", "actor": "emergency_vehicle_driver",
            "rationale": "Source-observed siren and dispatch branch diagnostic; legal outcome open.",
            "recording_description": config["recording_description"],
            "variable_assignments": {
                "documented_emergency_call": {"kind": "world_setup", "value": call},
                "documented_immediate_pursuit": {"kind": "world_setup", "value": pursuit},
                "siren_requested": {"kind": "controller", "value": siren},
                "observer_distance_ft": {"kind": "world_setup", "value": observer_distance},
                "other_approach_distance_m": {"kind": "world_setup", "value": approach_distance}},
            "unresolved_judgment_calls": [j["phrase"] for j in JUDGMENTS],
            "paired_probe_id": "C109028-call-siren" if suffix in ("probe_a", "probe_b") else
                               "C109028-joint-evidence" if suffix in SWEEP else "C109028-" + suffix,
            "deliberate_differences": (["documented_emergency_call"] if suffix in ("probe_a", "probe_b") else
                                     ["observer_distance_ft", "other_approach_distance_m"] if suffix in SWEEP else
                                     ["documented_emergency_call", "documented_immediate_pursuit", "siren_requested"]),
            "probe": {"primary_variable": "observer_distance_ft" if suffix in SWEEP else
                      "documented_emergency_call" if suffix in ("probe_a", "probe_b") else "siren_requested",
                      "comparison_or_standard": "source-observed physical evidence; legal judgment open",
                      "target_value_or_branch": suffix}}
        if suffix in ("probe_a", "probe_b"):
            proposal_case["deterministic_branch"] = {
                "source_clause": "the siren must not be used except when the vehicle is operated in response to an emergency call or in the immediate pursuit of an actual or suspected violator of the law",
                "judgment_context": [dict(j, status="not_exercised", reason=
                    "This pair isolates emergency-call siren permission; equipment and violator judgments remain open.")
                    for j in JUDGMENTS]}
        proposals.append(proposal_case)
        entries.append({
            "case_id": case_id, "kind": "delivery", "id": "primary",
            "construction": str(construction.relative_to(HERE)),
            "construction_sha256": sha(construction),
            "measurement_contract": str(selected.relative_to(HERE)),
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "c109028-saved-source-analysis-v1"},
            "fixture_recipe": str((selected.parent / "recipe.json").relative_to(HERE.parents[1])),
            "candidate_risk": {"status": "none", "reason":
                "A first original Native attempt is needed to measure route and lamp risk."},
            "candidates": []})
    proposal = {"format": "worker-canonical-cases-v1", "cell_id": "C109028",
                "law_id": "NRS-484D-400-5", "actor": "emergency_vehicle_driver",
                "status": "draft", "cases": proposals}
    write(HERE / "proposals/cases.json", proposal)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
                "status": "selected_cpu_proofs_in_progress", "cases": entries}
    write(HERE / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"selected_cases": len(build()["cases"])}, sort_keys=True))
