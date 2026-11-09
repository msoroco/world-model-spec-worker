"""Rebuild exact, source-bound C101303 constructions and semantic proposals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-484B-127-1"
SWEEP_ID = AID + "__crest_follow"
IDS = [SWEEP_ID + "-0000", SWEEP_ID + "-0001"]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def description():
    specs = [("ego.body", "m"), ("lead.body", "m"), ("ego.speed", "m/s"),
             ("lead.speed", "m/s"), ("following.separation", "m"),
             ("ego.lane", "Native lane id"), ("lead.lane", "Native lane id"),
             ("road.weather", "Native attributes")]
    return {"channels": [{"name": name, "unit": unit, "sampling_rate_hz": 20,
                           "method": "Native actor/body/road readback at original frame",
                           "time_window": "all 900 original frames", "reference_frame": "CARLA world",
                           "uncertainty": "20 Hz sampling and Native sensor/render limits"}
                          for name, unit in specs],
            "context_inputs": [],
            "limitations": ["Reasonable and prudent remains a legal judgment",
                            "Public-highway status requires sourced local review; Native map alone does not establish it",
                            "CPU fixtures cannot establish actual visibility or physical completion"]}


def cameras():
    return [{"name": name, "width": width, "height": height, "fov_deg": fov,
             "pose_strategy": pose} for name, width, height, fov, pose in
            [("overview", 1920, 1080, 90, "fixed overhead at measured crest"),
             ("approach", 1280, 720, 75, "fixed elevated initial approach"),
             ("reference_corner", 1280, 720, 75, "fixed oblique crest reference"),
             ("driver_reference", 1280, 720, 90, "attached ego reference")]]


def config(cid, gap, fallback, record):
    return {"cell_id": "C101303", "law_id": LAW, "actor": "motor_vehicle_driver",
            "selected_case_id": cid, "case": {"case_id": cid, "recording_description": record},
            "supported_case_ids": IDS,
            "required_atoms": ["ru.motor_vehicle", "kin.speed", "rel.centre_distance", "env.wet_road"],
            "source_packets": [],
            "rate_hz": 20, "duration_s": 45, "cameras": cameras(),
            "initial_gap_m": gap,
            "controller": {"target_speed_mps": 8.0, "lead_speed_mps": 8.0,
                           "lookahead_m": 9.0 if fallback else 6.0},
            "recording_description": record}


def construction(cid, cfg, record, fallback):
    files = [{"path": "runner.py", "source": f"work/{AID}/runner.py",
              "content": (ROOT / "runner.py").read_text()},
             {"path": "finalize.py", "source": f"work/{AID}/finalize.py",
              "content": (ROOT / "finalize.py").read_text()},
             {"path": "audit.py", "source": f"work/{AID}/audit.py",
              "content": (ROOT / "audit.py").read_text()},
             {"path": "config.json", "content": json.dumps(cfg, indent=2) + "\n"},
             {"path": "tests/test_bundle.py", "source": f"work/{AID}/tests/test_bundle.py",
              "content": (ROOT / "tests/test_bundle.py").read_text()},
             {"path": "tests/test_saved_feedback.py", "source": f"work/{AID}/tests/test_saved_feedback.py",
              "content": (ROOT / "tests/test_saved_feedback.py").read_text()},
             {"path": "tests/test_audit.py", "source": f"work/{AID}/tests/test_audit.py",
              "content": (ROOT / "tests/test_audit.py").read_text()}]
    return {"format": "worker-inline-construction", "case_id": cid,
            "cell_id": "C101303", "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
            "files": files, "measurement_plan": ["following separation and both measured speeds",
                                                   "Native lane transition and weather history"],
            "recording_description": record,
            "static_checks": ["measured elevation crest", "connected same-direction lane",
                              "two vehicles in same initial lane"],
            "termination_rules": ["900 synchronized 20 Hz frames", "stop on missing route or camera frame"],
            "mechanisms": ["Native waypoint-based crest search", "ego/lead PID speed control",
                           "lane change after 22 seconds", "four FFV1 original view recordings"],
            "candidate_kind": "fallback1" if fallback else "primary"}


def semantic_proposals(record):
    assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    law_text = assignment["law"]["text"]
    template_id = LAW + "@motor_vehicle_driver"
    relevance = {"cell_id": "C101303", "actor": "motor_vehicle_driver", "status": "draft",
                 "relevant_laws": [{"law_id": LAW,
                                    "quote": "The driver of a vehicle shall not follow another vehicle more closely than is reasonable and prudent",
                                    "applies_to": ["motor_vehicle_driver"], "confidence": "medium"}],
                 "borderline_excluded": []}
    template = {"template_id": template_id, "law_id": LAW, "actor": "motor_vehicle_driver",
                "quote": law_text,
                "structure": {"activation": {"source_clause": "The driver of a vehicle shall not follow another vehicle"},
                              "obligation": {"source_clause": "shall not follow another vehicle more closely than is reasonable and prudent"},
                              "exceptions": [], "timing": {"window": "during actual following"},
                              "judgment_calls_needed": [{"phrase": "reasonable and prudent", "note": ""}]},
                "parameter_refs": [{"name": "initial_gap_m", "kind": "world_setup", "range_or_domain": "16 to 26 m physical setup"},
                                   {"name": "following.separation", "kind": "subject_behavior", "range_or_domain": "measured nonnegative meters"}]}
    needs = [{"name": name, "unit": unit, "description": "Original Native 20 Hz evidence through following interval"}
             for name, unit in (("following.separation", "m"), ("ego.speed", "m/s"),
                                ("lead.speed", "m/s"), ("road.weather", "Native attributes"),
                                ("ego.lane", "Native lane id"), ("lead.lane", "Native lane id"))]
    judgment = {"template_id": template_id, "phrase": "reasonable and prudent", "note": "", "status": "draft",
                "observable_requirements": {"observables": needs,
                    "context_inputs": [],
                    "sweep_dimensions": [{"name": "following.separation", "unit": "m",
                                          "description": "Observed original body-center separation before lane change"}],
                    "landmarks": [], "recording_needs": needs,
                    "limitations": ["No legal minimum gap is supplied by the source text",
                                    "Public highway status needs local source review"]}}
    binding = {"cell_id": "C101303", "actor": "motor_vehicle_driver", "status": "draft",
               "law_refs": [{"template_id": template_id, "binding_kind": "general_duty"}],
               "context_refs": [], "established_contexts": [], "fixed_parameters": [],
               "variable_parameters": [{"name": "initial_gap_m", "kind": "world_setup", "unit": "m",
                                        "range_or_domain": "16 to 26 m", "used_by_laws": [LAW]},
                                       {"name": "following.separation", "kind": "subject_behavior", "unit": "m",
                                        "range_or_domain": "measured original body-center gap", "used_by_laws": [LAW]}]}
    assignments = {"initial_gap_m": {"kind": "world_setup", "value": 16.0, "unit": "m"},
                   "following.separation": {"kind": "subject_behavior", "value": None, "unit": "m"}}
    measurement = {"method": "first pre-change original body-center separation",
                   "time_window": "pre-change original frame interval", "statistic": "first"}
    sweep = {"sweep_id": SWEEP_ID, "target_law_id": LAW,
             "judgment_refs": [{"phrase": "reasonable and prudent", "note": ""}],
             "status": "complete", "mode": "one_dimensional",
             "axes": [{"variable": "initial_gap_m", "observable": "following.separation",
                       "unit": "m", "min": 16.0, "max": 26.0, "spacing": 10.0,
                       "measurement": measurement,
                       "range_rationale": "Two distinct starting separations fit within the planned 60 m approach; no statutory boundary is implied",
                       "spacing_rationale": "10 m separates visible vehicle placements beyond body-length and 20 Hz sampling noise",
                       "feasibility_evidence": "Existing C101303 review context records 45 s two-vehicle following cases; this hill-crest lane-change variant still needs Native confirmation"}],
             "landmarks": [], "rationale": "Measure following gap before lane change with legal judgment unresolved",
             "variable_assignments": assignments, "recording_description": record}
    baseline = {"case_id": AID + "__baseline", "target_law_id": None, "target_type": "baseline",
                "rationale": "Neutral unselected definition for the same physical cell",
                "variable_assignments": assignments, "unresolved_judgment_calls": [],
                "recording_description": record}
    proposals = {"cell_id": "C101303", "actor": "motor_vehicle_driver", "status": "draft",
                 "cases": [baseline], "sweep_specs": [sweep]}
    import sys
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(proposals, [template], binding)
    selected = [c for c in proposals["cases"] if c["target_type"] != "baseline"]
    if [c["case_id"] for c in selected] != IDS:
        raise ValueError("Canonical sweep expansion differs from exact case inventory")
    values = {"relevance_batch": relevance, "relevance": relevance, "template": template,
              "judgment_observables": judgment, "bindings": binding, "cases": proposals}
    for name, value in values.items():
        dump(ROOT / "proposals" / (name + ".json"), value)
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "stages": {name: {"path": f"proposals/{name}.json",
                               "sha256": sha(ROOT / "proposals" / (name + ".json"))}
                        for name in ("relevance_batch", "relevance", "template", "bindings", "cases")}}
    index["stages"]["judgment_observables"] = [{"path": "proposals/judgment_observables.json",
                                                   "sha256": sha(ROOT / "proposals/judgment_observables.json")}]
    dump(ROOT / "proposals/semantic-index.json", index)
    return selected


def main():
    record = description()
    source = f"inputs/{AID}/assignment.json"
    witness = f"inputs/{AID}/witnesses.json"
    cases = semantic_proposals(record)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": []}
    for cid, gap in zip(IDS, (16.0, 26.0)):
        suffix = cid.rsplit("__", 1)[-1]
        for fallback in (False, True):
            cfg = config(cid, gap, fallback, record)
            name = "fallback1" if fallback else "primary"
            path = ROOT / "cases" / suffix / name / "construction.json"
            dump(path, construction(cid, cfg, record, fallback))
            if not fallback:
                dump(ROOT / "cases" / suffix / "config.json", cfg)
            else:
                fallback_path = path
        primary_path = ROOT / "cases" / suffix / "primary" / "construction.json"
        entry = {"case_id": cid, "kind": "delivery",
                 "construction": str(primary_path.relative_to(ROOT)),
                 "construction_sha256": sha(primary_path),
                 "measurement_contract": f"cases/{suffix}/measurement-contract.json",
                 "measurement_procedure": {"entrypoint": "finalize.py"},
                 "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                    "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                 "acquisition": {name: {"entrypoint": "runner.py",
                                         "method": "PipelineCapture plus original Native actor/body readback",
                                         "evidence": "capture/evidence.jsonl and following_samples.jsonl"}
                                 for name in ["ru.motor_vehicle", "kin.speed", "rel.centre_distance",
                                              "env.wet_road", *[c["name"] for c in record["channels"]]]},
                 "candidate_risk": {"status": "physical",
                                    "reason": "Steering with a short lookahead can oscillate on the measured hill crest and prevent a completed Native lane transition"},
                 "candidates": [{"id": "fallback1",
                                 "construction": str(fallback_path.relative_to(ROOT)),
                                 "construction_sha256": sha(fallback_path),
                                 "trigger": {"source": "following_samples.jsonl and original camera frames",
                                             "metric": "ego lane ID after lane-change request and visible body path",
                                             "failure_condition": "No sustained target-lane occupancy or visible steering oscillation before completion"},
                                 "changed_knobs": ["controller.lookahead_m: 6.0 to 9.0"]}]}
        manifest["cases"].append(entry)
        dump(ROOT / "cases" / suffix / "measurement-contract.json",
             {"format": "worker-measurement-contract", "requirements": [
                 {"disposition_index": 0, "requirement": LAW,
                  "source": witness, "output_key": "following_before_lane_change",
                  "method": "following_measurement", "value_type": "object", "kind": "measured",
                  "inputs": ["following_samples.jsonl", "video_frames.jsonl", "surface_context.json"]}],
              "negative": {"remove": ["following_samples.jsonl"],
                           "error_contains": "Missing required source: following_samples.jsonl"}})
    dump(ROOT / "config.json", config(IDS[0], 16.0, False, record))
    dump(ROOT / "construction.json", json.loads((ROOT / "cases/crest_follow-0000/primary/construction.json").read_text()))
    plan = {"assignment_id": AID, "law_id": LAW, "cell_id": "C101303", "actor": "motor_vehicle_driver",
            "selected_branch": "Following before a lane change", "cases": cases,
            "comparisons": [{"comparison_id": "crest_follow_gap", "case_ids": IDS,
                             "fixed_conditions": ["C101303 hill crest", "two same-lane initial vehicles",
                                                  "ego and lead 8 m/s commands", "45 s", "four-camera 20 Hz profile",
                                                  "lane-change request at 22 s"],
                             "deliberate_differences": ["measured initial body-center following separation"]}],
            "observations": [{"name": c["name"], "mandatory": True} for c in record["channels"]],
            "sources": [{"path": source, "sha256": sha(REPO / source)},
                        {"path": witness, "sha256": sha(REPO / witness)},
                        {"path": f"inputs/{AID}/review-context/README.md",
                         "sha256": sha(REPO / f"inputs/{AID}/review-context/README.md")}],
            "existing_evidence": [{"case_ids": [AID + "__" + name for name in
                                    ("base", "closer", "faster_ego", "slower_lead", "lead_brakes",
                                     "wet_surface", "following_ends", "queued_traffic")],
                                   "status": "accepted in frozen local snapshot; no new recording claimed"}],
            "runtime_uncertainties": ["Native hill crest with connected lane unverified",
                                      "public highway status requires sourced review",
                                      "four-camera body visibility and lane-change completion unverified",
                                      "Lean validator and branch-sources input absent in clone"],
            "source_observation_mapping": {},
            "requirement_dispositions": [{"requirement": LAW, "source": witness,
                                          "status": "selected_required", "case_ids": IDS,
                                          "evidence_or_gap": "Native frame-joined body, speed, lane and weather history required"}],
            "camera_plan": {"profile": "overview1080-capability", "duration_s": 45,
                            "composition": "synchronized_four_view_primary", "coverage": [
                                {"view": c["name"], "subject": "ego, lead and crest",
                                 "interval": "0 through 45 s"} for c in cameras()]}}
    dump(ROOT / "case-plan.json", plan)
    dump(ROOT / "execution-manifest.json", manifest)


if __name__ == "__main__":
    main()
