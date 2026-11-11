"""Freeze stopped drive-to 450 ft as the first stopped exact CPU bundle."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__stopped_drive_to_450ft"
DEST = HERE / "cases/stopped_drive_to_450ft"


def put(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":") if compact else None,
                               indent=None if compact else 2) + "\n")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def rows(value):
    return "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in value)


def box(center, half):
    return [[center-half, -1], [center+half, -1],
            [center+half, 1], [center-half, 1]]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    first = json.loads((HERE / "config.json").read_text())
    recording = {
        "channels": [{"name": "fire_centre_distance_ft", "unit": "ft",
                      "method": "original-frame world center distance from retained Native footprints",
                      "sampling_rate_hz": 20, "time_window": "all original frames",
                      "reference_frame": "world ground plane",
                      "uncertainty": "Native vertex precision and 20 Hz temporal sampling"}],
        "context_inputs": [],
        "limitations": ["Alarm purpose is an authored premise; actual stopped state, closing motion and camera visibility need Native review."],
    }
    config = deepcopy(first)
    config.update(selected_case_id=CASE, fire_branch="stopped_drive_to",
                  target_distance_ft=450, frames=160, duration_s=8)
    config["case"] = {"case_id": CASE, "recording_description": recording}
    config["fire_context"]["alarm_response_source"] = "authored stopped fire-alarm dispatch premise; verify against local Native scene record"
    config["fire_context"]["apparatus_answered_alarm"] = True
    put(DEST / "config.json", config)
    sources = ["stopped_runner.py", "fire_route.py", "fire_camera_capture.py",
               "fire_capture_session.py", "fire_source_capture.py",
               "stopped_controller.py", "fire_finalizer.py", "stopped_finalizer.py",
               "fire_branch.py", "fire_distance.py"]
    tests = ["tests/test_stopped_runner.py", "tests/test_stopped_controller.py",
             "tests/test_stopped_finalizer.py", "tests/test_fire_route.py",
             "tests/test_fire_capture_session.py"]
    files = [{"path": "runner.py", "content": (HERE / "stopped_runner.py").read_text()}]
    files += [{"path": name, "content": (HERE / name).read_text()} for name in sources]
    files += [{"path": name, "content": (HERE / name).read_text()} for name in tests]
    files.append({"path": "config.json", "content": (DEST / "config.json").read_text()})
    construction = {
        "format": "worker-inline-construction", "case_id": CASE,
        "law_id": "NRS-484B-710", "cell_id": "C102304",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": files, "recording_description": recording,
        "measurement_plan": {"finalizer": "stopped_finalizer.py",
                             "retained_sources": ["video_frames.jsonl", "trace.jsonl",
                                                  "participant_footprints.jsonl",
                                                  "participant_state.jsonl", "fire_context.json"],
                             "reported_boundary": "minimum active-frame world center distance in feet"},
        "static_checks": ["stopped runner --check", "materialized fake-world CPU tests"],
        "termination_rules": ["160 original 20 Hz frames", "reject missing synchronized source camera frame"],
        "mechanisms": ["stationary fire apparatus", "measured closing approach controller",
                       "four original RGB sources", "saved-only center distance finalization"],
    }
    put(DEST / "construction.json", construction)
    # Build a small synthetic fire source history while retaining only the
    # pinned graph/trace schema scaffolding for converter compatibility.
    spec = json.loads((HERE / "diagnostic-input.json").read_text())
    source = spec["files"]
    trace = [json.loads(line) for line in source["trace.jsonl"].splitlines()]
    mapping = [json.loads(line) for line in source["video_frames.jsonl"].splitlines()]
    if len(trace) != 9 or len(mapping) != 9:
        raise ValueError("Diagnostic schema seed changed")
    ego_centers = [row["position"]["x"] + index * .3
                   for index, row in enumerate(trace)]
    apparatus_center = ego_centers[-1] + 450 / 3.280839895013123
    footprints = []
    state = []
    for index, (point, frame) in enumerate(zip(trace, mapping)):
        footprints.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                           "ego_id": "ego", "apparatus_id": "apparatus",
                           "ego_corners": box(ego_centers[index], 2),
                           "apparatus_corners": box(apparatus_center, 3)})
        state.append({"frame": frame["carla_frame"], "time_s": frame["time_s"],
                      "apparatus_moving": False, "ego_moving": True,
                      "ego_following": False, "ego_parked": False,
                      "warning_lamp": True, "siren": None})
    source["participant_footprints.jsonl"] = rows(footprints)
    source["participant_state.jsonl"] = rows(state)
    source["fire_context.json"] = json.dumps(config["fire_context"], indent=2) + "\n"
    capture = json.loads(source["capture/manifest.json"])
    capture["case_id"] = CASE
    source["capture/manifest.json"] = json.dumps(capture, indent=2) + "\n"
    provenance = json.loads(source["fixture-provenance.json"])
    provenance["case_id"] = CASE
    provenance["scope"] = "Synthetic stopped-apparatus software diagnostic; not physical evidence"
    source["fixture-provenance.json"] = json.dumps(provenance, indent=2) + "\n"
    diagnostic = DEST / "diagnostic.json"
    put(diagnostic, spec, compact=True)
    relative = diagnostic.relative_to(ROOT).as_posix()
    put(DEST / "diagnostic-recipe.json",
        {"format": "worker-fixture-recipe",
         "sources": [{"path": "diagnostic-input.json", "source": relative,
                      "sha256": digest(diagnostic)}],
         "generator": {"source": relative, "sha256": digest(diagnostic)}})
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    requirement = "driving to a fire apparatus stopped in answer to an alarm within the 500 ft boundary"
    source_ref = "NRS 484B.710 full text in inputs/" + HERE.name + "/assignment.json"
    disposition = {"requirement": requirement, "source": source_ref,
                   "status": "selected_required", "case_ids": [CASE],
                   "evidence_or_gap": "Accepted traveling-follow originals do not establish stationary apparatus or measured drive-to closing."}
    matching = [index for index, item in enumerate(plan["requirement_dispositions"])
                if item["requirement"] == requirement]
    if matching:
        index = matching[0]
        if plan["requirement_dispositions"][index] != disposition:
            raise ValueError("Existing stopped drive-to disposition changed")
    else:
        index = len(plan["requirement_dispositions"])
        plan["requirement_dispositions"].append(disposition)
    next(item for item in plan["cases"] if item["case_id"] == CASE)["construction_status"] = "exact_bundle_pending_proofs"
    put(plan_path, plan)
    contract = deepcopy(json.loads((HERE / "first-measurement-contract.json").read_text()))
    contract["case_id"] = CASE
    contract["requirements"][0].update(disposition_index=index,
                                       requirement=requirement, source=source_ref)
    put(DEST / "measurement-contract.json", contract)
    proposal_path = HERE / "proposals/cases.json"
    proposal = json.loads(proposal_path.read_text())
    if not any(item["case_id"] == CASE for item in proposal["cases"]):
        proposal["cases"].append({"case_id": CASE, "target_law_id": "NRS-484B-710",
                                  "target_type": "boundary_probe", "rationale": requirement,
                                  "paired_probe_id": "stopped_drive_to_500_boundary",
                                  "variable_assignments": {"target_centre_ft": {"kind": "controller", "value": 450}},
                                  "unresolved_judgment_calls": [],
                                  "recording_description": recording})
        put(proposal_path, proposal)
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = {"case_id": CASE, "kind": "delivery",
             "construction": (DEST / "construction.json").relative_to(HERE).as_posix(),
             "construction_sha256": digest(DEST / "construction.json"),
             "measurement_contract": (DEST / "measurement-contract.json").relative_to(HERE).as_posix(),
             "measurement_procedure": {"entrypoint": "stopped_finalizer.py"},
             "fixture_recipe": (DEST / "diagnostic-recipe.json").relative_to(ROOT).as_posix(),
             "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
             "candidate_risk": {"status": "physical",
                                "reason": "Native stationary apparatus or closing approach may not settle at the measured 450 ft centre target"},
             "acquisition": {"fire_centre_distance_ft": {
                 "entrypoint": "stopped_finalizer.py",
                 "method": "recompute original-frame centers from retained Native footprints",
                 "evidence": "FireCaptureSession writes original footprints/state and synchronized frame identities; stopped finalizer derives the centre stream."}},
             "candidates": []}
    prior = next((item for item in manifest["cases"] if item["case_id"] == CASE), None)
    if prior and prior.get("construction_sha256") == entry["construction_sha256"]:
        for key in ("offline", "compatibility", "negative", "post_capture", "candidates"):
            if key in prior:
                entry[key] = prior[key]
    manifest["cases"] = [item for item in manifest["cases"] if item["case_id"] != CASE] + [entry]
    put(manifest_path, manifest)


if __name__ == "__main__":
    main()
