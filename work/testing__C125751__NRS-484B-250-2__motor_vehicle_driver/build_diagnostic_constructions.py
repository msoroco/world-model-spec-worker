"""Build exact CPU-only constructions from the tested synthetic site fixture.

These constructions exercise the portable bundle and offline path. Their site
sources are explicitly diagnostic and the Native runner rejects their capture.
"""
import hashlib
import copy
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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


OPPOSITE_ENTRYPOINT = '''"""Portable opposite-turn candidate entrypoint; diagnostic sites cannot capture."""
import argparse
import hashlib
import json
from pathlib import Path

from opposite_site_probe import verify_opposite_site_packet
from opposite_turn_construction import validate_opposite_fallbacks
from opposite_turn_runner import (_camera_pose, _validate_candidate_construction,
                                  capture_candidate_media, finalize_candidate_opposite_turn)


def check(root):
    config = json.loads((root / "config.json").read_text())
    proposal = json.loads((root / "construction.json").read_text())
    metadata = proposal["candidate_construction"]
    plan = config["candidate_plan"]
    validated = validate_opposite_fallbacks(plan["primary"], plan["fallbacks"],
                                            config["turning_role"])
    variant = metadata["candidate_variant"]
    chosen = validated["primary"] if variant == "primary" else validated["fallbacks"][variant]
    _validate_candidate_construction(root, config, chosen["site"],
        config["turning_role"], chosen["release_frames"],
        chosen["target_speeds_mps"], chosen["frames"], chosen["transforms"],
        chosen["lookahead_m"])
    review = verify_opposite_site_packet(config, root)
    return config, chosen, review


def capture(root, host, port):
    config, chosen, review = check(root)
    if review["diagnostic_only"]:
        raise ValueError("Diagnostic opposite-turn site cannot enter Native capture")
    import carla  # Native dependency is deliberately lazy.
    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.get_world()
    if not world.get_settings().synchronous_mode:
        raise ValueError("Dedicated Native server must already be synchronous")
    if world.get_map().name != chosen["site"]["native_map_name"]:
        raise ValueError("Native world differs from reviewed opposite-turn map")
    library = world.get_blueprint_library()
    blueprints = {role: library.find(config["blueprint_ids"][role])
                  for role in ("ego", "other")}
    transforms = {role: _camera_pose(carla, chosen["transforms"][role])
                  for role in ("ego", "other")}
    light_ids = chosen["site"]["governed_signal_ids"]
    actors = {actor.id: actor for actor in world.get_actors()}
    lights = {role: actors[light_ids[role]] for role in ("ego", "other")}
    receipt = capture_candidate_media(root, world, carla, chosen["site"],
        config["turning_role"], blueprints, transforms, chosen["release_frames"],
        chosen["target_speeds_mps"], chosen["frames"], governed_lights=lights,
        client=client, lookahead_m=chosen["lookahead_m"])
    finalize_candidate_opposite_turn(root, root / "analysis-report.json")
    return receipt


def analyze(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if not (attempt / "body_history.jsonl").is_file():
        raise ValueError("Missing required source: body_history.jsonl")
    entry = finalize_candidate_opposite_turn(attempt, output)
    report = json.loads(output.read_text())
    report["raw_opposite_measurements"] = report.pop("measurements")
    report["measurements"] = {
        "body_entry_timing": measure_opposite_entry(entry, attempt),
        "opposite_turn_context": measure_opposite_route(entry, attempt),
        "signal_at_entry": measure_opposite_signal(entry, attempt),
        "stop_order": measure_opposite_stop(entry, attempt)}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\\n")
    return report


def _measurement(method, value, attempt, names):
    return {"method": method, "value": value,
            "sources": {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                        for name in names}}


def measure_opposite_entry(entry, attempt):
    return _measurement("measure_opposite_entry", {
        "first_body_entry": entry["first_body_entry"],
        "turning_minus_other_entry_time_s": entry["turning_minus_other_entry_time_s"]},
        attempt, ("body_history.jsonl", "crossing_history.jsonl",
                  "road_geometry.json", "video_frames.jsonl"))


def measure_opposite_route(entry, attempt):
    return _measurement("measure_opposite_route", entry["construction_geometry"],
        attempt, ("turn_route_context.json", "road_geometry.json",
                  "crossing_history.jsonl", "video_frames.jsonl"))


def measure_opposite_signal(entry, attempt):
    return _measurement("measure_opposite_signal", entry["signal_at_body_entry"],
        attempt, ("signal_context.json", "signal_history.jsonl",
                  "video_frames.jsonl"))


def measure_opposite_stop(entry, attempt):
    return _measurement("measure_opposite_stop", entry["stop_order"],
        attempt, ("stop_context.json", "stop_history.jsonl",
                  "video_frames.jsonl"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.check:
        check(root)
    elif args.attempt and args.output:
        analyze(args.attempt, args.output)
    elif args.output_dir:
        if args.output_dir.resolve() != root:
            raise ValueError("Capture output must be the materialized exact bundle")
        capture(root, args.host, args.port)
    else:
        parser.error("Select --check or --output-dir")
'''


OPPOSITE_BUNDLE_TEST = '''import json
import tempfile
import unittest
from pathlib import Path
from runner import check, capture


class MaterializedOppositeBundleTest(unittest.TestCase):
    def test_exact_candidate_binding_and_diagnostic_native_rejection(self):
        root = Path(__file__).resolve().parents[1]
        config, chosen, review = check(root)
        self.assertTrue(review["diagnostic_only"])
        self.assertEqual(config["selected_case_id"],
            "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_left_turn")
        self.assertEqual(set(config["candidate_plan"]["fallbacks"]),
                         {"fallback1", "fallback2", "fallback3"})
        with self.assertRaisesRegex(ValueError, "Diagnostic opposite-turn site"):
            capture(root, "127.0.0.1", 2000)

    def test_changed_inline_control_is_rejected(self):
        root = Path(__file__).resolve().parents[1]
        path = root / "construction.json"
        original = path.read_text()
        try:
            value = json.loads(original)
            value["candidate_construction"]["frames"] += 1
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "construction differs"):
                check(root)
        finally:
            path.write_text(original)
'''


def opposite_recording_description():
    return {"channels": [
        {"name": name, "unit": "structured record", "method": method,
         "time_window": "entire capture", "reference_frame": "original Native frame",
         "uncertainty": "synthetic diagnostic only", "sampling_rate_hz": 20}
        for name, method in (("signal_state", "original Native signal state by frame"),
                             ("stop_state", "original speed/body occupancy by frame"))],
        "context_inputs": [{"name": "entry_context", "unit": "structured record",
                            "method": "saved original-source join"}],
        "limitations": ["Synthetic opposite-turn site; no physical/legal acceptance"]}


def opposite_measurement_contract(disposition_offset=0):
    """Draft case-specific witness contract for the unselected left-turn branch."""
    source = ("NRS 484B.250(2), including its subsection-4 exception; "
              f"inputs/{ASSIGNMENT}/assignment.json")
    requirements = [
        ("Both complete vehicle bodies enter one sourced crossing; retain their original "
         "frame/time delta without a legal simultaneity cutoff", "body_entry_timing",
         "measure_opposite_entry", "measured",
         ["body_history.jsonl", "crossing_history.jsonl", "road_geometry.json",
          "video_frames.jsonl"]),
        ("Retain opposing approach bearings and the turning vehicle's source route "
         "and trajectory for the opposite-direction left-turn exception",
         "opposite_turn_context", "measure_opposite_route", "sourced_context",
         ["turn_route_context.json", "road_geometry.json", "crossing_history.jsonl",
          "video_frames.jsonl"]),
        ("Retain both governed Native signal states at body entry without treating Off "
         "as statutory inoperability or resolving official-device status",
         "signal_at_entry", "measure_opposite_signal", "sourced_context",
         ["signal_context.json", "signal_history.jsonl", "video_frames.jsonl"]),
        ("Retain both source-selected stop references, zero-speed histories and entry "
         "order for the subsection-4 stop and yield exception",
         "stop_order", "measure_opposite_stop", "measured",
         ["stop_context.json", "stop_history.jsonl", "video_frames.jsonl"])]
    dispositions = [{"requirement": wording, "source": source,
                     "status": "selected_required", "case_ids": [ASSIGNMENT + "__opposite_left_turn"],
                     "evidence_or_gap": "Source-hashed diagnostic measurement is implemented; "
                                        "reviewed Native source and legal judgment remain pending."}
                    for wording, *_ in requirements]
    contract = {"format": "worker-measurement-contract", "requirements": [
        {"disposition_index": disposition_offset + index, "requirement": wording, "source": source,
         "output_key": key, "method": method, "value_type": "object",
         "kind": kind, "inputs": inputs}
        for index, (wording, key, method, kind, inputs) in enumerate(requirements)],
        "negative": {"remove": ["body_history.jsonl"],
                     "error_contains": "Missing required source: body_history.jsonl"}}
    return dispositions, contract


def build_opposite_offline_bundle(output_root):
    """Generate four exact-ID, diagnostic-only bundles for pinned offline tests.

    The review packet is synthetic and the Native entrypoint rejects capture.
    Generated files stay under ignored .runtime-work, preserving returned-file cap.
    """
    output_root = Path(output_root).resolve()
    if output_root.exists() or ".runtime-work" not in output_root.parts:
        raise ValueError("Choose a fresh ignored .runtime-work output directory")
    spec = importlib.util.spec_from_file_location(
        "c125751_opposite_fixture", HERE / "tests/test_opposite_turn_construction.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    from opposite_turn_construction import TRIGGER_SOURCES, validate_opposite_fallbacks
    with tempfile.TemporaryDirectory() as temporary:
        packet_root = Path(temporary)
        fixture.DeviceSourceJoinTests()._opposite_finalizer_sources(packet_root)
        source_config = json.loads((packet_root / "config.json").read_text())
        site = source_config["site"]
        site_review = source_config["site_review"]
        site_files = [{"path": path.name, "content": path.read_text()}
                      for path in sorted(packet_root.glob("opposite-*.json"))]
    primary = {"site": site,
        "transforms": {"ego": [-10, 0, 0, 0, 0, 0],
                       "other": [10, 0, 0, 180, 0, 0]},
        "release_frames": {"ego": 8, "other": 10},
        "target_speeds_mps": {"ego": 5.0, "other": 5.0},
        "frames": 1100, "lookahead_m": 5.0}
    fallbacks = {}
    for name, risk in (("fallback1", "spawn_occupied"),
                       ("fallback2", "entry_timing_missed"),
                       ("fallback3", "turn_path_missed")):
        fallbacks[name] = dict(copy.deepcopy(primary), physical_risk_trigger=risk,
            trigger_measurement={"source": TRIGGER_SOURCES[name][0],
                                 "metric": TRIGGER_SOURCES[name][1],
                                 "failure_condition": "Original source records the named engineering failure"},
            source_review="synthetic CPU diagnostic alternative; Native review pending")
    fallbacks["fallback1"]["transforms"]["ego"] = [-12, 0, 0, 0, 0, 0]
    fallbacks["fallback2"]["target_speeds_mps"]["ego"] = 4.0
    fallbacks["fallback3"]["lookahead_m"] = 3.0
    validate_opposite_fallbacks(primary, fallbacks, "ego")
    output_root.mkdir(parents=True)
    case = ASSIGNMENT + "__opposite_left_turn"
    config = {"selected_case_id": case, "law_id": "NRS-484B-250-2",
              "cell_id": "C125751", "actor": "motor_vehicle_driver",
              "duration_s": 55, "rate_hz": 20,
              "turning_role": "ego", "site": site,
              "candidate_plan": {"primary": primary, "fallbacks": fallbacks},
              "blueprint_ids": {"ego": "vehicle.tesla.model3",
                                "other": "vehicle.audi.a2"},
              "recording_description": opposite_recording_description()}
    config["site_review"] = site_review
    code_files = sorted(path for path in HERE.glob("*.py") if path.name not in
        {"runner.py", "build_diagnostic_constructions.py", "saved_source_proof.py"})
    code_files += [HERE / "tests/test_opposite_turn_construction.py",
                   HERE / "tests/test_opposite_site_probe.py"]
    code_entries = [{"path": str(path.relative_to(HERE)), "content": path.read_text()}
                    for path in code_files]
    base_files = site_files + code_entries + [
        {"path": "runner.py", "content": OPPOSITE_ENTRYPOINT},
        {"path": "tests/test_opposite_bundle.py", "content": OPPOSITE_BUNDLE_TEST},
        {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": json.loads(
                    (HERE / "candidate-proof-manifest-v2.json").read_text())["runtime_manifest_sha256"],
                "cases": []}
    source_proposals = json.loads((HERE / "proposals/cases.json").read_text())
    proposal_case = copy.deepcopy(next(item for item in source_proposals["cases"]
        if item["case_id"].endswith("__signal_off")))
    proposal_case.update(case_id=case,
        rationale="Synthetic opposite-approach left-turn diagnostic source join",
        variable_assignments={"turning_role": "ego", "opposing_approach": True,
                              "governing_states": {"ego": "Off", "other": "Off"}},
        unresolved_judgment_calls=["official device status", "approximately same time",
                                   "opposite-left-turn exception and statutory yield"],
        recording_description=config["recording_description"])
    for key in ("paired_probe_id", "deliberate_differences", "probe"):
        proposal_case.pop(key, None)
    (output_root / "proposals").mkdir()
    _dump(output_root / "proposals/cases.json", {"cell_id": "C125751",
        "actor": "motor_vehicle_driver", "status": "synthetic_diagnostic_only",
        "cases": [proposal_case], "sweep_specs": [], "sweeps_expanded": True})
    for variant in ("primary", "fallback1", "fallback2", "fallback3"):
        chosen = primary if variant == "primary" else fallbacks[variant]
        metadata = {"selected_case_id": case,
            "site_sha256": hashlib.sha256(json.dumps(site, sort_keys=True,
                                                  allow_nan=False).encode()).hexdigest(),
            "turning_role": "ego", "candidate_variant": variant,
            "release_frames": chosen["release_frames"],
            "target_speeds_mps": chosen["target_speeds_mps"],
            "frames": chosen["frames"], "lookahead_m": chosen["lookahead_m"]}
        proposal = {"case_id": case, "law_id": "NRS-484B-250-2",
                    "cell_id": "C125751", "actor": "motor_vehicle_driver",
                    "entrypoint": "runner.py", "recording_description": config["recording_description"],
                    "candidate_construction": metadata, "files": base_files,
                    "status": "synthetic_diagnostic_only"}
        path = output_root / (variant + "-construction.json")
        _dump(path, proposal)
        entry = {"id": variant, "construction": path.name,
                 "construction_sha256": _sha(path)}
        if variant == "primary":
            manifest["cases"].append({"case_id": case, "kind": "delivery",
                **{key: entry[key] for key in ("construction", "construction_sha256")},
                "measurement_procedure": {"entrypoint": "runner.py"},
                "candidate_risk": {"status": "physical",
                    "reason": "Sourced spawn, entry timing and turn path may fail in Native capture"},
                "candidates": []})
        else:
            entry["trigger"] = fallbacks[variant]["trigger_measurement"]
            entry["changed_knobs"] = [{
                "fallback1": "paired reviewed spawn transforms",
                "fallback2": "ego target speed",
                "fallback3": "route-controller lookahead"}[variant]]
            manifest["cases"][0]["candidates"].append(entry)
    manifest_path = output_root / "manifest.json"
    _dump(manifest_path, manifest)
    dispositions, contract = opposite_measurement_contract()
    _dump(output_root / "draft-requirement-dispositions.json", dispositions)
    _dump(output_root / "draft-measurement-contract.json", contract)
    return manifest_path


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


def prove_opposite_entry_sweep(output_root):
    """Run paired original-frame entry offsets through finalizer and independent audit.

    These are authored diagnostic body tracks. They test the saved-source join
    and sensitivity to entry order, never Native motion or a legal time cutoff.
    """
    output_root = Path(output_root).resolve()
    if output_root.exists() or ".runtime-work" not in output_root.parts:
        raise ValueError("Choose a fresh ignored .runtime-work output directory")
    spec = importlib.util.spec_from_file_location(
        "c125751_opposite_source_fixture", HERE / "tests/test_opposite_turn_construction.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    from shapely.geometry import Polygon
    from opposite_turn_runner import analyze_candidate_opposite_entry, finalize_candidate_opposite_turn, _stop_state
    from opposite_site_probe import audit_opposite_candidate
    from worker_exchange.fixture_generator import generate as generate_media
    from worker_exchange.media import audit as audit_media, check_four_view_sources
    from worker_exchange.saved_processing import prepare_video
    from camera_setup import SIZES
    from batch_pipeline.carla import validate_attempt

    output_root.mkdir(parents=True)
    receipts = []
    for ego_index, other_index in ((1, 3), (1, 2), (1, 1), (2, 1), (3, 1)):
        root = output_root / f"ego-{ego_index}-other-{other_index}"
        root.mkdir()
        fixture.DeviceSourceJoinTests()._opposite_finalizer_sources(root)
        original = [json.loads(line) for line in
                    (root / "crossing_history.jsonl").read_text().splitlines()]
        polygon = Polygon(json.loads((root / "road_geometry.json").read_text())[
            "intersection_polygon_xy_m"])
        crossing, signals, stops, mapping, bodies, trace, evidence = ([] for _ in range(7))
        native_frames, native_graphs = [], []
        diagnostic_template = json.loads((HERE / "diagnostic-off-sources/capture/evidence.jsonl")
                                         .read_text().splitlines()[0])
        for index in range(5):
            frame, time_s = 100 + index, index * .05
            row = {"frame": frame, "time_s": time_s}
            for role, entry_index in (("ego", ego_index), ("other", other_index)):
                row[role] = copy.deepcopy(original[1 if index >= entry_index else 0][role])
            crossing.append(row)
            signals.append({"frame": frame, "time_s": time_s,
                "native_signal_id": 17, "other_native_signal_id": 18,
                "state": "Off", "other_state": "Off"})
            stops.append({"frame": frame, "time_s": time_s,
                **{role: _stop_state(row[role], polygon) for role in ("ego", "other")}})
            mapping.append({"carla_frame": frame, "time_s": time_s,
                            "video_frame": index})
            bodies.append({"native_frame": frame, "frame_index": index,
                "turning_role": "ego", "actor_sources": {
                    role: row[role] for role in ("ego", "other")},
                "camera_source_frames": {name: frame for name in
                    ("overview", "approach", "reference_corner", "driver_reference")}})
            ego_body = row["ego"]["body_vertices_xy_m"]
            position = [sum(p[0] for p in ego_body) / len(ego_body),
                        sum(p[1] for p in ego_body) / len(ego_body), 0.]
            trace.append({"frame": frame, "time_s": time_s,
                          "position": {"x": sum(p[0] for p in ego_body) / len(ego_body),
                                       "y": sum(p[1] for p in ego_body) / len(ego_body),
                                       "z": 0.},
                          "position_m": position,
                          "heading_deg": row["ego"]["heading_deg"],
                          "speed_mps": row["ego"]["speed_mps"],
                          "speed_mph": row["ego"]["speed_mps"] / .44704,
                          "velocity_mps": [row["ego"]["speed_mps"], 0., 0.],
                          "control": diagnostic_template.get("control", {
                              "throttle": 0, "steer": 0, "brake": 0,
                              "hand_brake": False, "reverse": False})})
            packet = copy.deepcopy(diagnostic_template)
            packet.update(original_frame=frame, replay_frame=frame,
                          recording_time_s=time_s, replay_simulation_time_s=time_s)
            packet["ego"].update(position_m=position,
                heading_deg=row["ego"]["heading_deg"],
                speed_mps=row["ego"]["speed_mps"],
                speed_provenance="synthetic_native_sample")
            packet["ego"]["body_vertices_m"] = [
                [x, y, z] for x, y in ego_body for z in (0., 1.5)]
            participants = []
            for role, actor_id in (("ego", 101), ("other", 102)):
                body = row[role]["body_vertices_xy_m"]
                participant = copy.deepcopy(diagnostic_template["original_observations"]["participants"][
                    0 if role == "ego" else 1])
                participant.update(actor_id=actor_id,
                    position_m=[sum(p[0] for p in body) / len(body),
                                sum(p[1] for p in body) / len(body), 0.],
                    heading_deg=row[role]["heading_deg"],
                    speed_mps=row[role]["speed_mps"],
                    velocity_mps=[row[role]["speed_mps"] * (1 if role == "ego" else -1), 0., 0.],
                    body_vertices_m=[[x, y, z] for x, y in body for z in (0., 1.5)])
                participants.append(participant)
            observation = packet["original_observations"]
            observation.update(frame=frame, time_s=time_s, participants=participants)
            evidence.append(packet)
            graph_path = f"graphs/base/{frame:08d}.adapter.json"
            native_frames.append({"frame": frame, "simulation_time": time_s,
                "base": graph_path, "adapter_graph": graph_path, "nodes": 0, "edges": 0,
                "extraction_seconds": 0, "capture_seconds": 0})
            native_graphs.append({"path": "capture/native/" + graph_path,
                "attributes": {"frame": frame, "observed_evidence": observation},
                "nodes": [], "edges": []})
        (root / "capture/native").mkdir(parents=True, exist_ok=True)
        for name, values in (("crossing_history.jsonl", crossing),
                             ("signal_history.jsonl", signals),
                             ("stop_history.jsonl", stops),
                             ("video_frames.jsonl", mapping),
                             ("body_history.jsonl", bodies),
                             ("trace.jsonl", trace),
                             ("capture/evidence.jsonl", evidence),
                             ("capture/native/frames.jsonl", native_frames)):
            (root / name).write_text("".join(json.dumps(value) + "\n" for value in values))
        generate_media({"files": {}, "graphs": native_graphs, "videos": []}, root)
        road = (HERE / "diagnostic-off-sources/road.xodr").read_text()
        road = road.replace("synthetic C125714 orthogonal crossing", "synthetic opposite approach join")
        road = road.replace("synthetic ego highway", "synthetic two-way approach")
        road = road[:road.index('<road name="synthetic other highway"')] + '</OpenDRIVE>'
        (root / "road.xodr").write_text(road)
        (root / "capture/recorder_info.txt").write_text("Create 101: vehicle.tesla.model3\nCreate 102: vehicle.tesla.model3\n")
        _dump(root / "capture/manifest.json", {"status": "draft",
            "acquisition": "synthetic_diagnostic",
            "case_id": json.loads((root / "config.json").read_text())["selected_case_id"],
            "map": "synthetic diagnostic", "frames": len(evidence),
            "required_observations": [], "extraction_confirmed": True,
            "sources": {name: _sha(root / name) for name in ("road.xodr", "trace.jsonl")}})
        videos = []
        for name, (width, height) in SIZES.items():
            (root / (name + ".mkv")).unlink()
            videos.append({"path": name + ".mkv", "frames": len(mapping),
                           "width": width, "height": height,
                           "fps": 20, "color": "black"})
        generate_media({"files": {}, "graphs": [], "videos": videos}, root)
        check_four_view_sources({name: root / (name + ".mkv") for name in SIZES})
        map_sha = _sha(root / "video_frames.jsonl")
        source_audits = {}
        for name in SIZES:
            source_audits[name + ".mkv"] = audit_media(
                root / (name + ".mkv"), len(mapping),
                mapping_sha256=map_sha, receipt=root / (name + "-decode.json"))
        prepare_video(root)
        audit_media(root / "raw.mkv", len(mapping), mapping_sha256=map_sha,
                    receipt=root / "raw-decode.json")
        config_path = root / "config.json"
        config = json.loads(config_path.read_text())
        config["duration_s"] = .25
        config["recording_description"] = opposite_recording_description()
        _dump(config_path, config)
        before = analyze_candidate_opposite_entry(root)
        analysis_path = root / "analysis-report.json"
        measured = finalize_candidate_opposite_turn(root, analysis_path)
        audited = audit_opposite_candidate(root, analysis_path)
        validate_attempt(root, {"case": {"case_id": config["selected_case_id"]},
            "cell": {"cell_id": config["cell_id"]}, "actor": "motor_vehicle_driver"},
            {"recording_description": config["recording_description"]},
            {"recorded_exit_code": 0}, {}, source_audits=source_audits)
        expected = round((ego_index - other_index) * .05, 9)
        if (round(measured["turning_minus_other_entry_time_s"], 9) != expected or
                measured["first_body_entry"] != before["first_body_entry"] or
                not audited["software_audit_passed"]):
            raise ValueError("Opposite original-frame entry sweep disagrees with independent audit")
        body_path = root / "body_history.jsonl"
        saved_body = body_path.read_bytes()
        body_path.write_bytes(saved_body + b" ")
        try:
            audit_opposite_candidate(root, analysis_path)
        except ValueError:
            pass
        else:
            raise ValueError("Independent audit accepted changed original body source")
        finally:
            body_path.write_bytes(saved_body)
        receipts.append({"ego_entry_index": ego_index,
                         "other_entry_index": other_index,
                         "turning_minus_other_entry_time_s": expected,
                         "body_history_sha256": _sha(body_path),
                         "analysis_sha256": _sha(analysis_path),
                         "four_camera_decodes_passed": True,
                         "composed_video_decode_passed": True,
                         "native_output_validation_passed": True,
                         "independent_audit_passed": True,
                         "changed_body_source_rejected": True})
    proof = {"format": "worker-c125751-opposite-entry-saved-diagnostic-sweep",
             "builder_sha256": _sha(HERE / "build_diagnostic_constructions.py"),
             "receipts": receipts, "native_motion_proven": False,
             "decodable_diagnostic_video_proven": True,
             "native_pixels_proven": False, "legal_time_cutoff_asserted": False,
             "physical_acceptance_claimed": False}
    _dump(output_root / "proof.json", proof)
    return proof


def prove_opposite_positive_compatibility(manifest_path, sweep_attempt, output_root):
    """Run four diagnostic candidates through actual analysis, Core and decode."""
    repo = HERE.parent.parent
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(
        repo / ".runtime-work/scenario-pipeline-artifacts")
    from worker_exchange.package_compatibility import _process_fixture
    from worker_exchange.fixture_recipe import fixture_fingerprint
    from worker_exchange.common import digest
    from worker_exchange.runtime_cli import execution_env, materialize
    from worker_exchange.saved_processing import copy_sources
    from worker_exchange.measurement_contract import validate as validate_measurements
    from worker_exchange.measurement_contract import verify_report
    manifest_path = Path(manifest_path).resolve()
    sweep_attempt = Path(sweep_attempt).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists() or ".runtime-work" not in output_root.parts:
        raise ValueError("Choose a fresh ignored .runtime-work output directory")
    output_root.mkdir(parents=True)
    fixture = output_root / "fixture"
    fixture.mkdir()
    excluded = {"config.json", "result.json", "analysis-report.json", "channels",
                "raw.mkv", "raw-decode.json", "receipts", "four-view-receipt.json"}
    for path in sweep_attempt.iterdir():
        if (path.name in excluded or path.name.endswith("-decode.json") or
                path.name.startswith("opposite-")):
            continue
        target = fixture / path.name
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    if not (fixture / "capture/native/frames.jsonl").is_file():
        raise ValueError("Diagnostic native frame packet missing")
    inventory = fixture_fingerprint(fixture)
    source = {"fixture_sha256": digest(inventory), "fixture_manifest": inventory}
    case = json.loads((sweep_attempt / "config.json").read_text())["selected_case_id"]
    dispositions, contract = opposite_measurement_contract()
    construction = json.loads((manifest_path.parent / "primary-construction.json").read_text())
    analyzer = next(item["content"] for item in construction["files"]
                    if item["path"] == "runner.py")
    validate_measurements(contract, dispositions, analyzer, case)
    receipts = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        attempt = output_root / candidate
        receipt = _process_fixture(manifest_path, case, fixture, attempt,
            repo / "runtime/library",
            repo / ".runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck",
            candidate, source)
        measured = verify_report(contract,
            json.loads((attempt / "analysis-report.json").read_text()), fixture)
        receipts.append({"candidate": candidate,
                         "construction_sha256": receipt["construction_sha256"],
                         "fixture_sha256": receipt["fixture_sha256"],
                         "positive_compatibility_passed": receipt["passed"],
                         "draft_measurements_verified": sorted(measured),
                         "converted_report_sha256": _sha(attempt / "converted/adapter_report.json")})
    negative = output_root / "missing-body-negative"
    materialize(manifest_path, case, negative, "primary")
    copy_sources(fixture, negative)
    (negative / "body_history.jsonl").unlink()
    failed = subprocess.run([sys.executable, str(negative / "runner.py"),
        "--attempt", str(negative), "--output", str(negative / "negative-analysis.json")],
        cwd=negative, env=execution_env(), capture_output=True, text=True, timeout=120)
    (output_root / "missing-body-negative.log").write_text(failed.stdout + failed.stderr)
    if failed.returncode == 0 or "body_history.jsonl" not in failed.stderr:
        raise ValueError("Missing original body source was not rejected")
    proof = {"format": "worker-c125751-opposite-positive-compatibility-probe",
             "builder_sha256": _sha(HERE / "build_diagnostic_constructions.py"),
             "manifest_sha256": _sha(manifest_path),
             "source_attempt": str(sweep_attempt.relative_to(repo)),
             "receipts": receipts, "missing_body_source_rejected": True,
             "draft_measurement_contract_verified": True,
             "formal_selected_fixture_recipe_proven": False,
             "recorded_only_saved_processing_proven": False,
             "physical_acceptance_claimed": False}
    _dump(output_root / "proof.json", proof)
    return proof


def prove_opposite_generated_fixture(manifest_path, sweep_attempt, output_root):
    """Rebuild the source packet from text, graph records and color video specs.

    This remains a synthetic compatibility fixture. It does not convert the
    diagnostic site into a selected Native construction.
    """
    repo = HERE.parent.parent
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(
        repo / ".runtime-work/scenario-pipeline-artifacts")
    from worker_exchange.fixture_generator import generate, inspect
    from worker_exchange.fixture_recipe import fixture_fingerprint
    from worker_exchange.common import digest
    from worker_exchange.package_compatibility import _process_fixture
    from worker_exchange.measurement_contract import verify_report
    manifest_path = Path(manifest_path).resolve()
    sweep_attempt = Path(sweep_attempt).resolve()
    output_root = Path(output_root).resolve()
    if output_root.exists() or ".runtime-work" not in output_root.parts:
        raise ValueError("Choose a fresh ignored .runtime-work output directory")
    output_root.mkdir(parents=True)
    excluded = {"config.json", "result.json", "analysis-report.json",
                "raw.mkv", "channels", "receipts", "four-view-receipt.json"}
    spec = {"files": {}, "graphs": [], "videos": []}
    for path in sorted(sweep_attempt.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(sweep_attempt).as_posix()
        if (path.parts[len(sweep_attempt.parts)] in excluded or
                path.name.endswith("-decode.json") or
                path.name.startswith("opposite-") or
                path.name == "raw-decode.json"):
            continue
        if path.name.endswith(".adapter.json"):
            graph = json.loads(path.read_text())
            if graph.get("nodes") or graph.get("edges"):
                raise ValueError("Diagnostic graph now needs explicit node/edge inventory")
            spec["graphs"].append({"path": relative,
                                   "attributes": graph["metadata"],
                                   "nodes": [], "edges": []})
        elif path.suffix == ".mkv":
            spec["videos"].append({"path": relative, "frames": 5,
                                   "width": 1920 if path.name == "overview.mkv" else 1280,
                                   "height": 1080 if path.name == "overview.mkv" else 720,
                                   "fps": 20, "color": "black"})
        else:
            spec["files"][relative] = path.read_text()
    inspect(spec)
    _dump(output_root / "diagnostic-fixture-spec.json", spec)
    fixture = output_root / "fixture"
    fixture.mkdir()
    generated = generate(spec, fixture)
    inventory = fixture_fingerprint(fixture, spec)
    source = {"fixture_sha256": digest(inventory), "fixture_manifest": inventory}
    case = ASSIGNMENT + "__opposite_left_turn"
    _, contract = opposite_measurement_contract()
    receipts = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        attempt = output_root / candidate
        receipt = _process_fixture(manifest_path, case, fixture, attempt,
            repo / "runtime/library",
            repo / ".runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck",
            candidate, source)
        verified = verify_report(contract,
            json.loads((attempt / "analysis-report.json").read_text()), fixture)
        receipts.append({"candidate": candidate,
                         "construction_sha256": receipt["construction_sha256"],
                         "compatibility_passed": receipt["passed"],
                         "measurement_keys": sorted(verified),
                         "converted_report_sha256": _sha(attempt / "converted/adapter_report.json")})
    proof = {"format": "worker-c125751-generated-opposite-fixture-probe",
             "builder_sha256": _sha(HERE / "build_diagnostic_constructions.py"),
             "manifest_sha256": _sha(manifest_path),
             "spec_sha256": _sha(output_root / "diagnostic-fixture-spec.json"),
             "generated_source_count": len(generated),
             "receipts": receipts,
             "returned_fixture_recipe_proven": False,
             "physical_acceptance_claimed": False}
    _dump(output_root / "proof.json", proof)
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
    parser.add_argument("--opposite-offline-bundle")
    parser.add_argument("--prove-opposite-entry-sweep")
    parser.add_argument("--prove-opposite-positive-compatibility", nargs=3)
    parser.add_argument("--prove-opposite-generated-fixture", nargs=3)
    args = parser.parse_args()
    if args.opposite_offline_bundle:
        output = {"manifest": str(build_opposite_offline_bundle(args.opposite_offline_bundle))}
    elif args.prove_opposite_generated_fixture:
        output = prove_opposite_generated_fixture(*args.prove_opposite_generated_fixture)
    elif args.prove_opposite_positive_compatibility:
        output = prove_opposite_positive_compatibility(*args.prove_opposite_positive_compatibility)
    elif args.prove_opposite_entry_sweep:
        output = prove_opposite_entry_sweep(args.prove_opposite_entry_sweep)
    elif args.audit_release_attempt:
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
