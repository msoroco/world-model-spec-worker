"""Bind the first exact case to the public selected compatibility path."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__probe_a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    construction = HERE / "draft-candidates/probe_a/primary/construction.json"
    config = json.loads((HERE / "native/config.json").read_text())
    contract = {
        "format": "worker-measurement-contract", "case_id": CASE,
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
    selected = HERE / "selected-fixture/probe_a/measurement-contract.json"
    write(selected, contract)
    proposal = {"format": "worker-canonical-cases-v1", "cell_id": "C109028",
                "law_id": "NRS-484D-400-5", "actor": "emergency_vehicle_driver",
                "status": "draft", "cases": [{"case_id": CASE,
                    "target_law_id": "NRS-484D-400-5", "target_type": "compliant_attempt",
                    "cell_id": "C109028", "actor": "emergency_vehicle_driver",
                    "rationale": "Documented call and source-observed siren diagnostic; legal outcome open.",
                    "recording_description": config["recording_description"],
                    "variable_assignments": {"documented_call": {
                        "kind": "sourced_context", "value": True}}}]}
    write(HERE / "proposals/cases.json", proposal)
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
                "status": "selected_cpu_proofs_in_progress", "cases": [{
                    "case_id": CASE, "kind": "delivery", "id": "primary",
                    "construction": str(construction.relative_to(HERE)),
                    "construction_sha256": sha(construction),
                    "measurement_contract": str(selected.relative_to(HERE)),
                    "measurement_procedure": {"entrypoint": "finalize.py",
                                              "output_schema": "c109028-saved-source-analysis-v1"},
                    "fixture_recipe": str((selected.parent / "recipe.json").relative_to(HERE.parents[1])),
                    "candidate_risk": {"status": "none", "reason":
                        "No measured physical failure yet; preserve the primary controller for first Native observation."},
                    "candidates": []}]}
    write(HERE / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"selected_cases": len(build()["cases"])}, sort_keys=True))
