"""Build exact CPU-only constructions from the tested synthetic site fixture.

These constructions exercise the portable bundle and offline path. Their site
sources are explicitly diagnostic and the Native runner rejects their capture.
"""
import hashlib
import copy
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


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


def build_release_sweep(output_root):
    """Stage four Off-signal controller variants without adding case identities.

    These variants prove bundled CPU execution of release policies. Their
    synthetic site and media cannot establish realized Native entry timing.
    """
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
        config["ego_release_frame"] = release
        config["other_release_frame"] = 10
        config_entry["content"] = json.dumps(config, indent=2) + "\n"
        construction_path = output_root / f"construction-ego-{release}.json"
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
        manifest_path = output_root / f"manifest-ego-{release}.json"
        _dump(manifest_path, manifest)
        variants.append({"ego_release_frame": release, "other_release_frame": 10,
                         "case_id": case["case_id"],
                         "construction": str(construction_path),
                         "construction_sha256": _sha(construction_path),
                         "manifest": str(manifest_path)})
    return variants


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-sweep-output")
    parser.add_argument("--audit-release-attempt")
    args = parser.parse_args()
    if args.audit_release_attempt:
        output = audit_release_attempt(args.audit_release_attempt)
    elif args.release_sweep_output:
        output = build_release_sweep(args.release_sweep_output)
    else:
        output = build()
    print(json.dumps(output, indent=2))
