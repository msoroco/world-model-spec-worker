"""Build exact CPU-only constructions from the tested synthetic site fixture.

These constructions exercise the portable bundle and offline path. Their site
sources are explicitly diagnostic and the Native runner rejects their capture.
"""
import hashlib
import copy
import argparse
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build():
    fixture_path = HERE / "tests/test_runner.py"
    spec = importlib.util.spec_from_file_location("c125751_runner_fixture", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    files = sorted(p for p in HERE.glob("*.py") if p.name not in
                   {"build_diagnostic_constructions.py", "saved_source_proof.py"})
    files += sorted((HERE / "tests").glob("test*.py"))
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": "a4626c89ca4e80fb42351a8fdd4f6aa2601a670a9df51707d306bb45732cdaf3",
                "cases": []}
    for case in fixture.TARGETS:
        suffix = case.rsplit("__", 1)[-1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = fixture.config(case)
            fixture.write_packet(root, config)
            fixture.validate_config(config, root)
            _dump(root / "config.json", config)
            entries = [{"path": p.name, "content": p.read_text()} for p in sorted(root.iterdir())]
            entries += [{"path": str(p.relative_to(HERE)), "content": p.read_text(),
                         "source": str(p.relative_to(HERE.parent.parent))} for p in files]
            construction = {
                "case_id": case, "law_id": "NRS-484B-250-2", "cell_id": "C125751",
                "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
                "recording_description": config["recording_description"], "files": entries,
                "status": "synthetic_diagnostic_only",
                "measurement_plan": {"source": "crossing_history.jsonl", "saved_finalizer": "finalizer.py"}}
            path = HERE / ("diagnostic-construction-" + suffix + ".json")
            _dump(path, construction)
            manifest["cases"].append({"case_id": case, "kind": "delivery",
                                      "construction": path.name, "construction_sha256": _sha(path),
                                      "measurement_procedure": {"entrypoint": "finalizer.py"},
                                      "measurement_contract": "measurement-contract.json",
                                      "fixture_recipe": f"work/{ASSIGNMENT}/diagnostic{'-off' if suffix == 'signal_off' else ''}-recipe.json"})
    _dump(HERE / "diagnostic-execution-manifest.json", manifest)
    return manifest


def build_release_sweep(output_root, vary_role="ego"):
    """Stage four Off-signal controller variants without adding case identities.

    These variants prove bundled CPU execution of release policies. Their
    synthetic site and media cannot establish realized Native entry timing.
    """
    if vary_role not in ("ego", "other"):
        raise ValueError("Release sweep role must be ego or other")
    output_root = Path(output_root)
    if output_root.exists():
        raise ValueError("Retain earlier sweep; choose a new output directory")
    output_root.mkdir(parents=True)
    for name in ("case-plan.json", "measurement-contract.json"):
        (output_root / name).write_bytes((HERE / name).read_bytes())
    (output_root / "proposals").mkdir()
    (output_root / "proposals/cases.json").write_bytes(
        (HERE / "proposals/cases.json").read_bytes())
    case = next(case for case in json.loads(
        (HERE / "candidate-proof-manifest-v2.json").read_text())["cases"]
        if case["case_id"].endswith("__signal_off"))
    base = json.loads((HERE / case["construction"]).read_text())
    variants = []
    for release in (8, 9, 10, 11):
        variant = copy.deepcopy(base)
        config_entry = next(item for item in variant["files"] if item["path"] == "config.json")
        config = json.loads(config_entry["content"])
        config["ego_release_frame"] = release if vary_role == "ego" else 10
        config["other_release_frame"] = release if vary_role == "other" else 10
        config_entry["content"] = json.dumps(config, indent=2) + "\n"
        construction_path = output_root / f"construction-{vary_role}-{release}.json"
        _dump(construction_path, variant)
        manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                    "runtime_manifest_sha256": json.loads(
                        (HERE / "candidate-proof-manifest-v2.json").read_text())[
                            "runtime_manifest_sha256"],
                    "cases": [{"case_id": case["case_id"], "kind": "delivery",
                               "construction": construction_path.name,
                               "construction_sha256": _sha(construction_path),
                               "fixture_recipe": case["fixture_recipe"],
                               "measurement_procedure": case["measurement_procedure"],
                               "measurement_contract": case["measurement_contract"]}]}
        manifest_path = output_root / f"manifest-{vary_role}-{release}.json"
        _dump(manifest_path, manifest)
        variants.append({"ego_release_frame": config["ego_release_frame"],
                         "other_release_frame": config["other_release_frame"],
                         "varied_release_role": vary_role,
                         "case_id": case["case_id"],
                         "construction": str(construction_path),
                         "construction_sha256": _sha(construction_path),
                         "manifest": str(manifest_path)})
    return variants


def audit_release_sweep(output_root, vary_role="other"):
    """Check one declared release axis against four complete staged bundles."""
    if vary_role not in ("ego", "other"):
        raise ValueError("Release sweep role must be ego or other")
    root = Path(output_root)
    releases = (8, 9, 10, 11)
    bundles = [json.loads((root / f"construction-{vary_role}-{n}.json").read_text())
               for n in releases]
    def normalized(bundle, release):
        files = {item["path"]: item["content"] for item in bundle["files"]}
        config = json.loads(files["config.json"])
        expected = {"ego_release_frame": release if vary_role == "ego" else 10,
                    "other_release_frame": release if vary_role == "other" else 10}
        if any(config.get(key) != value for key, value in expected.items()):
            raise ValueError("Declared release schedule differs")
        config.pop(vary_role + "_release_frame")
        files["config.json"] = json.dumps(config, sort_keys=True)
        return {"case_id": bundle["case_id"],
                "recording_description": bundle["recording_description"],
                "files": files}
    fixed = [normalized(bundle, release) for bundle, release in zip(bundles, releases)]
    if any(item != fixed[0] for item in fixed[1:]):
        raise ValueError("Sweep changed a fixed construction condition")
    altered = copy.deepcopy(bundles[0])
    config_entry = next(item for item in altered["files"] if item["path"] == "config.json")
    config = json.loads(config_entry["content"])
    config["other_release_frame" if vary_role == "ego" else "ego_release_frame"] += 1
    config_entry["content"] = json.dumps(config)
    try:
        normalized(altered, releases[0])
    except ValueError as error:
        if "Declared release schedule differs" not in str(error):
            raise
    else:
        raise ValueError("Changed fixed release was accepted")
    return {"format": "worker-fixed-release-axis-diagnostic",
            "varied_role": vary_role, "releases": list(releases),
            "fixed_construction_conditions": True,
            "changed_fixed_release_rejected": True,
            "physical_acceptance_claimed": False,
            "legal_verdict_asserted": False,
            "construction_sha256": [_sha(root / f"construction-{vary_role}-{n}.json")
                                    for n in releases]}


def audit_cross_release_sweeps(ego_root, other_root):
    """Prove both one-axis sweeps share the exact frame-10 baseline bundle."""
    ego = audit_release_sweep(ego_root, "ego")
    other = audit_release_sweep(other_root, "other")
    baseline_ego = Path(ego_root) / "construction-ego-10.json"
    baseline_other = Path(other_root) / "construction-other-10.json"
    if baseline_ego.read_bytes() != baseline_other.read_bytes():
        raise ValueError("Release axes do not share the fixed baseline construction")
    return {"format": "worker-cross-release-axis-diagnostic",
            "ego_axis": ego, "other_axis": other,
            "shared_baseline_construction_sha256": _sha(baseline_ego),
            "physical_acceptance_claimed": False,
            "legal_verdict_asserted": False}


def audit_release_attempt(root):
    """Join an actual controller trace to original-frame body-entry measurements.

    This reports engineering timing only. A diagnostic fixture cannot establish
    that a requested release schedule is feasible at the selected Native site.
    """
    from entry_measurements import analyze

    root = Path(root)
    config_path = root / "config.json"
    controller_path = root / "controller_history.jsonl"
    crossing_path = root / "crossing_history.jsonl"
    for path in (config_path, controller_path, crossing_path):
        if not path.is_file():
            raise ValueError("Missing original release source: " + path.name)
    config = json.loads(config_path.read_text())
    for role in ("ego", "other"):
        value = config.get(role + "_release_frame")
        if type(value) is not int or value < 0:
            raise ValueError("Explicit nonnegative release index required: " + role)
    measured = analyze(root)
    controls = [json.loads(line) for line in controller_path.read_text().splitlines() if line.strip()]
    crossings = [json.loads(line) for line in crossing_path.read_text().splitlines() if line.strip()]
    if len(controls) != len(crossings):
        raise ValueError("Controller/crossing history length differs")
    releases = {}
    for index, (control, crossing) in enumerate(zip(controls, crossings)):
        if (control.get("frame"), control.get("time_s")) != (crossing.get("frame"), crossing.get("time_s")):
            raise ValueError("Controller/original-frame join failed")
        permissions = control.get("release_permissions")
        if not isinstance(permissions, dict) or any(type(permissions.get(role)) is not bool for role in ("ego", "other")):
            raise ValueError("Missing Boolean controller release permissions")
        for role in ("ego", "other"):
            expected = index >= config[role + "_release_frame"]
            if permissions[role] != expected:
                raise ValueError("Controller release schedule differs: " + role)
            if expected and role not in releases:
                releases[role] = {"index": index, "frame": crossing["frame"],
                                  "time_s": crossing["time_s"]}
    delays = {}
    for role in ("ego", "other"):
        entry = measured["first_body_entry"][role]
        if entry is None or role not in releases:
            raise ValueError("Release and body entry both required: " + role)
        release = releases[role]
        if entry["frame"] < release["frame"] or entry["time_s"] < release["time_s"]:
            raise ValueError("Body entered before controller release: " + role)
        delays[role] = entry["time_s"] - release["time_s"]
    return {"format": "worker-release-entry-audit", "sources": {
        "config.json": _sha(config_path), "controller_history.jsonl": _sha(controller_path),
        **measured["sources"]}, "releases": releases,
        "first_body_entry": measured["first_body_entry"],
        "release_to_entry_delay_s": delays,
        "ego_minus_other_entry_time_s": measured["ego_minus_other_entry_time_s"],
        "approximately_same_time_judgment": measured["approximately_same_time_judgment"],
        "physical_acceptance_claimed": False, "legal_priority_claimed": False}


def replay_controller_commands(config, frames=14, observed_other_entry_frame=None):
    """Run both production release/stop/speed controllers on a fixed CPU pose.

    A stationary front at each stop reference tests control commands, not vehicle
    motion. The resulting trace is never an original Native controller history.
    """
    from runner import release_permissions
    from stop_control import StopApproach
    from yield_controller import apply_speed_control

    if frames < 12:
        raise ValueError("Controller replay must extend past the release sweep")
    if observed_other_entry_frame is not None and (
            type(observed_other_entry_frame) is not int or
            not 2 <= observed_other_entry_frame < frames or
            config.get("ego_release_frame") is not None):
        raise ValueError("Measured-entry replay requires default subject release")
    carla = SimpleNamespace(VehicleControl=lambda: SimpleNamespace(
        steer=0.0, throttle=0.0, brake=0.0))
    actors = {role: SimpleNamespace(
        get_velocity=lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0),
        apply_control=lambda control: None) for role in ("ego", "other")}
    stops = {}
    fronts = {}
    for role in ("ego", "other"):
        segment = config["site"]["selected_stop_references"][role]["segment_xy_m"]
        stops[role] = StopApproach(segment)
        fronts[role] = [(segment[0][axis] + segment[1][axis]) / 2 for axis in (0, 1)]
    trace = []
    for index in range(frames):
        permissions = release_permissions(
            config, index,
            other_entered=observed_other_entry_frame is not None and
            index >= observed_other_entry_frame)
        row = {"index": index, "permissions": permissions, "roles": {}}
        for role in ("ego", "other"):
            decision = stops[role].step(fronts[role], 0.0, [1.0, 0.0], permissions[role])
            command = apply_speed_control(carla, actors[role],
                                          config[role + "_target_speed_mps"],
                                          decision["hold"])
            row["roles"][role] = {"stop_phase": decision["phase"],
                                   "zero_speed_frames": decision["recorded_zero_speed_frames_near_reference"],
                                   "command": command}
        trace.append(row)
    return trace


def prove_controller_command_sweep(ego_root, other_root, output_path):
    """Bind eight staged schedules to actual CPU controller command transitions."""
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError("Retain previous controller proof; choose a new output")
    traces, receipts = {}, []
    for axis, root in (("ego", Path(ego_root)), ("other", Path(other_root))):
        for release in (8, 9, 10, 11):
            construction = root / f"construction-{axis}-{release}.json"
            document = json.loads(construction.read_text())
            config = json.loads(next(item["content"] for item in document["files"]
                                     if item["path"] == "config.json"))
            if config.get(axis + "_release_frame") != release or config.get(
                    ("other" if axis == "ego" else "ego") + "_release_frame") != 10:
                raise ValueError("Staged release schedule differs from declared axis")
            trace = replay_controller_commands(config)
            first = {}
            for role in ("ego", "other"):
                enabled = [row["index"] for row in trace
                           if row["roles"][role]["command"]["throttle"] > 0]
                expected = config[role + "_release_frame"]
                if not enabled or enabled[0] != expected:
                    raise ValueError("Production controller command did not follow release: " + role)
                if any(row["roles"][role]["command"]["brake"] != 1.0
                       for row in trace[:expected]):
                    raise ValueError("Production controller did not hold before release: " + role)
                first[role] = enabled[0]
            traces[(axis, release)] = trace
            receipts.append({"axis": axis, "release_frame": release,
                             "construction_sha256": _sha(construction),
                             "first_positive_throttle_index": first,
                             "pre_release_full_brake": True})
    for axis, fixed in (("ego", "other"), ("other", "ego")):
        baseline = [row["roles"][fixed] for row in traces[(axis, 10)]]
        if any([row["roles"][fixed] for row in traces[(axis, release)]] != baseline
               for release in (8, 9, 11)):
            raise ValueError("Fixed-role production commands changed across release axis")
    if traces[("ego", 10)] != traces[("other", 10)]:
        raise ValueError("Cross-axis production controller baseline differs")
    proof = {"format": "worker-c125751-controller-command-sweep",
             "builder_sha256": _sha(HERE / "build_diagnostic_constructions.py"),
             "replay_kind": "stationary CPU pose at source-selected stop references",
             "receipts": receipts, "fixed_role_commands_identical": True,
             "cross_axis_baseline_identical": True,
             "native_motion_or_entry_proven": False,
             "physical_acceptance_claimed": False, "legal_priority_claimed": False}
    _dump(output_path, proof)
    return proof


def prove_measured_yield_sweep(output_path):
    """Exercise default subject release against four supplied body-entry frames."""
    output_path = Path(output_path)
    if output_path.exists():
        raise ValueError("Retain previous yield proof; choose a new output")
    case = next(case for case in json.loads(
        (HERE / "candidate-proof-manifest-v2.json").read_text())["cases"]
        if case["case_id"].endswith("__signal_off"))
    construction = HERE / case["construction"]
    document = json.loads(construction.read_text())
    config = json.loads(next(item["content"] for item in document["files"]
                             if item["path"] == "config.json"))
    config.pop("ego_release_frame", None)
    config["other_release_frame"] = 10
    receipts, fixed_commands = [], None
    for observed_entry in (8, 9, 10, 11):
        trace = replay_controller_commands(
            config, observed_other_entry_frame=observed_entry)
        ego = [row["roles"]["ego"]["command"] for row in trace]
        other = [row["roles"]["other"]["command"] for row in trace]
        first = next((index for index, command in enumerate(ego)
                      if command["throttle"] > 0), None)
        if first != observed_entry or any(command["brake"] != 1.0
                                          for command in ego[:observed_entry]):
            raise ValueError("Default measured-entry yield control differs")
        if fixed_commands is not None and other != fixed_commands:
            raise ValueError("Opposing command changed across measured-entry sweep")
        fixed_commands = other
        receipts.append({"observed_other_entry_index": observed_entry,
                         "first_subject_positive_throttle_index": first,
                         "pre_entry_full_brake": True})
    proof = {"format": "worker-c125751-measured-yield-controller-sweep",
             "builder_sha256": _sha(HERE / "build_diagnostic_constructions.py"),
             "selected_off_construction_sha256": _sha(construction),
             "replay_kind": "stationary CPU pose with supplied opposing body-entry observation",
             "receipts": receipts, "opposing_commands_identical": True,
             "native_entry_feedback_proven": False,
             "physical_acceptance_claimed": False, "legal_yield_claimed": False}
    _dump(output_path, proof)
    return proof


def prove_fixture_release_join(ego_root, other_root, output_root):
    """Show static diagnostic crossing tracks cannot prove release response."""
    output = Path(output_root)
    if output.exists():
        raise ValueError("Use a fresh fixture-join output root")
    output.mkdir(parents=True)
    receipts = []
    for role, source_root in (("ego", Path(ego_root)), ("other", Path(other_root))):
        for release in (8, 9, 10, 11):
            source = source_root / f"{role}-{release}-compat"
            if not (source / "compatibility.json").is_file():
                raise ValueError("Exact compatibility receipt missing")
            attempt = output / f"{role}-{release}"
            attempt.mkdir()
            for name in ("config.json", "crossing_history.jsonl", "road_geometry.json",
                         "video_frames.jsonl"):
                shutil.copy2(source / name, attempt / name)
            config = json.loads((attempt / "config.json").read_text())
            crossings = [json.loads(line) for line in
                         (attempt / "crossing_history.jsonl").read_text().splitlines() if line]
            original_crossing_sha256 = _sha(attempt / "crossing_history.jsonl")
            delayed = []
            for index, original in enumerate(crossings):
                row = copy.deepcopy(original)
                for party in ("ego", "other"):
                    row[party] = copy.deepcopy(crossings[max(0, index - 20)][party])
                delayed.append(row)
            crossings = delayed
            (attempt / "crossing_history.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in crossings))
            controls = [{"frame": row["frame"], "time_s": row["time_s"],
                         "release_permissions": {
                             party: index >= config[party + "_release_frame"]
                             for party in ("ego", "other")}}
                        for index, row in enumerate(crossings)]
            controller = attempt / "controller_history.jsonl"
            controller.write_text("".join(json.dumps(row) + "\n" for row in controls))
            (attempt / "provenance.json").write_text(json.dumps({
                "diagnostic_fixture": True,
                "controller_history_origin": "synthetically generated from authored release indices",
                "crossing_history_origin": "synthetic 20-frame body-track delay from static compatibility fixture; not Native response",
                "compatibility_crossing_sha256": original_crossing_sha256
            }, indent=2) + "\n")
            measured = audit_release_attempt(attempt)
            altered = copy.deepcopy(controls)
            altered[0]["release_permissions"]["ego"] = True
            controller.write_text("".join(json.dumps(row) + "\n" for row in altered))
            try:
                audit_release_attempt(attempt)
            except ValueError as error:
                if "Controller release schedule differs: ego" not in str(error):
                    raise
            else:
                raise ValueError("Tampered controller permission was accepted")
            controller.write_text("".join(json.dumps(row) + "\n" for row in controls))
            receipts.append({"role": role, "release_frame": release,
                             "compatibility_sha256": _sha(source / "compatibility.json"),
                             "measurement": measured,
                             "tampered_permission_rejected": True})
    deltas = {round(item["measurement"]["ego_minus_other_entry_time_s"], 9)
              for item in receipts}
    if len(deltas) != 1:
        raise ValueError("Static source fixture unexpectedly changed entry timing")
    proof = {"format": "worker-static-crossing-release-join-diagnostic",
             "cases": receipts, "static_entry_delta_s": next(iter(deltas)),
             "all_eight_source_joins_passed": True,
             "native_release_response_proven": False,
             "physical_acceptance_claimed": False,
             "legal_verdict_asserted": False}
    (output / "proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-sweep-output")
    parser.add_argument("--vary-role", choices=("ego", "other"), default="ego")
    parser.add_argument("--audit-release-sweep")
    parser.add_argument("--compare-release-sweeps", nargs=2)
    parser.add_argument("--prove-fixture-release-join", nargs=3)
    parser.add_argument("--prove-controller-command-sweep", nargs=3)
    parser.add_argument("--prove-measured-yield-sweep")
    parser.add_argument("--audit-release-attempt")
    args = parser.parse_args()
    if args.audit_release_attempt:
        output = audit_release_attempt(args.audit_release_attempt)
    elif args.prove_fixture_release_join:
        output = prove_fixture_release_join(*args.prove_fixture_release_join)
    elif args.prove_controller_command_sweep:
        output = prove_controller_command_sweep(*args.prove_controller_command_sweep)
    elif args.prove_measured_yield_sweep:
        output = prove_measured_yield_sweep(args.prove_measured_yield_sweep)
    elif args.compare_release_sweeps:
        output = audit_cross_release_sweeps(*args.compare_release_sweeps)
    elif args.audit_release_sweep:
        output = audit_release_sweep(args.audit_release_sweep, args.vary_role)
    elif args.release_sweep_output:
        output = build_release_sweep(args.release_sweep_output, args.vary_role)
    else:
        output = build()
    print(json.dumps(output, indent=2))
