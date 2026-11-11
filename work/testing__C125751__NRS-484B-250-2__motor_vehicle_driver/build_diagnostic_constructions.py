"""Build exact CPU-only constructions from the tested synthetic site fixture.

These constructions exercise the portable bundle and offline path. Their site
sources are explicitly diagnostic and the Native runner rejects their capture.
"""
import hashlib
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
            config["recording_description"] = {
                "channels": [], "context_inputs": [],
                "limitations": ["Synthetic diagnostic site; no Native or legal acceptance"]}
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
                                      "construction": path.name, "construction_sha256": _sha(path)})
    _dump(HERE / "diagnostic-execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
