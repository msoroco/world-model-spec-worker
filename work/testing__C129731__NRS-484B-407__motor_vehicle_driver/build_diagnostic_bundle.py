"""Bind the first C129731 source-shaped CPU construction for offline checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    config = json.loads((HERE / "config.json").read_text())
    case = config["selected_case_id"]
    files = [HERE / name for name in ("runner.py", "finalizer.py", "site_construction.py", "u_turn_control.py",
              "visibility_measure.py", "camera_encoder.py", "camera_setup.py",
              "config.json", "diagnostic-site.json")]
    files += sorted((HERE / "tests").glob("test*.py"))
    entries = [{"path": str(path.relative_to(HERE)), "content": path.read_text(),
                "source": str(path.relative_to(REPO))} for path in files]
    construction = {"case_id": case, "law_id": config["law_id"], "cell_id": config["cell_id"],
                    "actor": config["actor"], "entrypoint": "runner.py", "files": entries,
                    "status": "synthetic_diagnostic_only",
                    "recording_description": config["recording_description"],
                    "measurement_plan": {"sources": ["trace.jsonl", "capture/evidence.jsonl", "motion_history.jsonl",
                                                     "video_frames.jsonl", "overview.mkv", "approach.mkv",
                                                     "reference_corner.mkv", "driver_reference.mkv"],
                                         "saved_finalizer": "finalizer.py"},
                    "static_checks": ["runner --check", "nine package CPU tests"],
                    "termination_rules": ["1100 original frames or explicit failed capture"],
                    "mechanisms": ["reviewed curve/crest geometry required for Native capture",
                                   "spawned static prop with bounding-box verification",
                                   "measured-feedback U-turn and both-direction approach controllers"]}
    target = HERE / "construction.json"
    _dump(target, construction)
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    law_source = "NRS 484B.407; inputs/" + HERE.name + "/assignment.json"
    dispositions = [
        {"requirement": "At the U-turn site, retain both original incoming approach rays and their brackets against 500 feet (152.4 m), without a driver-eye or legal-visibility inference",
         "source": law_source, "status": "selected_required", "case_ids": [case],
         "evidence_or_gap": "Original capture/evidence.jsonl visibility, motion_history.jsonl and video_frames.jsonl; actual driver sight remains unverified."},
        {"requirement": "Retain original vehicle body and heading reversal at a sourced curve, together with the maneuver site and both approach lanes",
         "source": law_source, "status": "selected_required", "case_ids": [case],
         "evidence_or_gap": "Original turn_history.jsonl, curve_context.json and motion/frame join; physical location and motion await Native capture."}]
    plan["requirement_dispositions"] = dispositions
    _dump(plan_path, plan)
    contract = {"format": "worker-measurement-contract", "requirements": [
        {"disposition_index": 0, "requirement": dispositions[0]["requirement"],
         "source": law_source, "output_key": "visibility_at_turn", "method": "measure_visibility",
         "value_type": "object", "kind": "measured",
         "inputs": ["capture/evidence.jsonl", "motion_history.jsonl", "video_frames.jsonl"]},
        {"disposition_index": 1, "requirement": dispositions[1]["requirement"],
         "source": law_source, "output_key": "turn_and_site", "method": "measure_turn",
         "value_type": "object", "kind": "measured",
         "inputs": ["turn_history.jsonl", "curve_context.json", "motion_history.jsonl",
                    "video_frames.jsonl"]}],
        "negative": {"remove": ["turn_history.jsonl"],
                     "error_contains": "Missing required source: turn_history.jsonl"}}
    _dump(HERE / "measurement-contract.json", contract)
    proposal_dir = HERE / "proposals"
    proposal_dir.mkdir(exist_ok=True)
    proposal = {"case_id": case, "target_law_id": config["law_id"],
                "target_type": "delivery", "rationale": "Curve U-turn with both 500-foot approach sight lines",
                "variable_assignments": {"feature": {"kind": "world_setup", "value": "curve", "unit": "categorical"},
                                         "probe": {"kind": "world_setup", "value": "short_of_500ft", "unit": "categorical"}},
                "unresolved_judgment_calls": ["actual driver visibility", "legal turning circumstance"],
                "recording_description": config["recording_description"]}
    _dump(proposal_dir / "cases.json", {"cases": [proposal]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": "a4626c89ca4e80fb42351a8fdd4f6aa2601a670a9df51707d306bb45732cdaf3",
                "status": "diagnostic_incomplete", "cases": [{"case_id": case, "kind": "delivery",
                    "construction": target.name, "construction_sha256": _sha(target),
                    "fixture_recipe": str((HERE / "diagnostic-recipe.json").relative_to(REPO)),
                    "measurement_contract": "measurement-contract.json",
                    "measurement_procedure": {"entrypoint": "finalizer.py"},
                    "candidate_risk": {"status": "physical", "reason": "Native occlusion and approach motion need measured confirmation"},
                    "acquisition": {
                        "st.sight_distance": {"entrypoint": "runner.py", "method": "PipelineCapture original ray packet", "evidence": "capture/evidence.jsonl"},
                        "sight_distance": {"entrypoint": "finalizer.py", "method": "pinned ray summary", "evidence": "channels/sight_distance.jsonl"},
                        "u_turn_motion": {"entrypoint": "runner.py", "method": "original pose and velocity", "evidence": "motion_history.jsonl"},
                        "approaching_actors": {"entrypoint": "runner.py", "method": "original both approach actors", "evidence": "motion_history.jsonl"}}}]}
    _dump(HERE / "diagnostic-execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
