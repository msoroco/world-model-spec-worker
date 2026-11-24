"""Run 600-frame exact drafts offline and measure retained synthetic Native traces."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
MANIFEST = HERE / "draft-execution-manifest-600.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_measure(path):
    spec = importlib.util.spec_from_file_location("c111294_long_measure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = Path(tempfile.mkdtemp(prefix="c111294-source-600-", dir=ROOT / ".runtime-work"))
    results = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        source_name = "decrease" if suffix == "probe_a" else "hold"
        for ref in [entry] + entry["candidates"]:
            candidate = ref["id"]
            output = scratch / (suffix + "-" + candidate)
            command = [str(PYTHON), str(ROOT / "runtime.py"), "offline", "--manifest",
                       str(MANIFEST), "--case", entry["case_id"], "--candidate", candidate,
                       "--output", str(output), "--python", str(PYTHON)]
            process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=300)
            if process.returncode or json.loads(process.stdout).get("offline_passed") is not True:
                raise RuntimeError("Exact offline command failed: " + process.stdout)
            source = output / "draft-fixtures" / (source_name + "-synthetic-native.jsonl")
            measure = load_measure(output / "measure_approach.py")
            digest = sha(source)
            measured = measure(source, digest)
            expected = "measured_early_decrease_held" if suffix == "probe_a" else "measured_no_material_decrease"
            if measured["frames"] != 600 or measured["measured_relation"] != expected:
                raise ValueError("Exact 600-frame speed relation differs")
            try:
                measure(source, "0" * 64)
            except ValueError as error:
                if "Saved Native source hash changed" not in str(error):
                    raise
            else:
                raise AssertionError("Changed source hash was accepted")
            missing = output / "missing-native.jsonl"
            try:
                measure(missing, digest)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Missing Native source was accepted")
            log = output / "offline.log"
            if "Ran 4 tests" not in log.read_text() or not log.read_text().rstrip().endswith("OK"):
                raise ValueError("Exact bundled Native offline tests differ")
            results.append({"case": suffix, "candidate": candidate,
                            "construction_sha256": ref["construction_sha256"],
                            "source_path": str(source.relative_to(ROOT)),
                            "source_sha256": digest, "offline_log_sha256": sha(log),
                            "measured_relation": expected, "decrease_mph": measured["decrease_mph"],
                            "physical_native_capture_verified": False})
            print(suffix, candidate, "offline/source passed", flush=True)
    proof = {"format": "c111294-unselected-600-source-proof-v1", "passed": True,
             "assignment_id": HERE.name, "manifest_sha256": sha(MANIFEST),
             "results": results, "positive_count": 8, "changed_hash_rejections": 8,
             "missing_source_rejections": 8,
             "scope": "synthetic source-only CPU diagnostics, no original Native or legal judgment"}
    target = HERE / "draft-600-source-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "bundles": len(results), "sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
