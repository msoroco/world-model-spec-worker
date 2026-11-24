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
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    config = json.loads((HERE / "native/config.json").read_text())
    proposals, entries = [], []
    for suffix, (call, pursuit, siren) in POLICIES.items():
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
        proposals.append({"case_id": case_id,
            "target_law_id": "NRS-484D-400-5",
            "target_type": "compliant_attempt" if suffix == "probe_a" else
                "violating_attempt" if suffix == "probe_b" else "source_diagnostic",
            "cell_id": "C109028", "actor": "emergency_vehicle_driver",
            "rationale": "Source-observed siren and dispatch branch diagnostic; legal outcome open.",
            "recording_description": config["recording_description"],
            "variable_assignments": {
                "documented_emergency_call": {"kind": "sourced_context", "value": call},
                "documented_immediate_pursuit": {"kind": "sourced_context", "value": pursuit},
                "siren_requested": {"kind": "controller", "value": siren}}})
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
