"""Test all eight 30-second draft saved-footprint paths on retained synthetic rows."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / ".venv-cpu/bin/python"
MANIFEST = HERE / "draft-execution-manifest-600.json"
sys.path.insert(0, str(HERE))
from synthetic_proof import sample


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, cwd):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    return result


def main():
    scratch = Path(tempfile.mkdtemp(prefix="c110454-saved-600-", dir=ROOT / ".runtime-work"))
    manifest = json.loads(MANIFEST.read_text())
    outcomes = []
    for suffix in ("probe_a", "probe_b"):
        source = scratch / (suffix + "-native.jsonl")
        source.write_text("".join(json.dumps(sample(suffix, i), separators=(",", ":")) + "\n"
                                  for i in range(600)))
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            output = scratch / (suffix + "-" + candidate)
            case = HERE.name + "__" + suffix
            offline = command([PYTHON, ROOT / "runtime.py", "offline", "--manifest", MANIFEST,
                               "--case", case, "--candidate", candidate, "--output", output,
                               "--python", PYTHON], ROOT)
            if offline.returncode:
                raise RuntimeError("Exact 600-frame offline failed: " + offline.stdout)
            (output / "native_samples.jsonl").write_bytes(source.read_bytes())
            positive = command([PYTHON, output / "finalize-measure.py", "--attempt", output,
                                "--output", output / "analysis-report.json"], output)
            if positive.returncode:
                raise RuntimeError("Saved positive failed: " + positive.stdout)
            report = json.loads((output / "analysis-report.json").read_text())
            measured = report["measurements"]["intersection_parking_footprint"]
            value = measured["value"]
            expected = "outside_intersection" if suffix == "probe_a" else "within_intersection"
            if (value["parking_relation"] != expected or value["parked_frames"] != 360
                    or measured["sources"]["native_samples.jsonl"] != sha(source)):
                raise ValueError("Source-bound 600-frame parking relation differs")
            (output / "native_samples.jsonl").unlink()
            negative = command([PYTHON, output / "finalize-measure.py", "--attempt", output,
                                "--output", output / "negative-report.json"], output)
            if negative.returncode == 0 or "Missing required source: native_samples.jsonl" not in negative.stdout:
                raise ValueError("Missing Native source was accepted")
            outcomes.append({"case": suffix, "candidate": candidate,
                             "source_path": str(source.relative_to(ROOT)),
                             "source_sha256": sha(source),
                             "measurement_sha256": sha(output / "analysis-report.json"),
                             "offline_log_sha256": sha(output / "offline.log"),
                             "negative_log_sha256": hashlib.sha256(negative.stdout.encode()).hexdigest(),
                             "parked_frames": value["parked_frames"],
                             "parking_relation": expected,
                             "overlap_m2": value["max_intersection_body_overlap_m2"],
                             "original_native_verified": False})
            print(suffix, candidate, "saved positive and negative passed", flush=True)
    a = [item for item in outcomes if item["case"] == "probe_a"]
    b = [item for item in outcomes if item["case"] == "probe_b"]
    if not all(item["overlap_m2"] == 0 for item in a) or not all(item["overlap_m2"] > 10 for item in b):
        raise ValueError("Controlled full-body contrast differs")
    proof = {"format": "c110454-unselected-600-saved-proof-v1", "passed": True,
             "assignment_id": HERE.name, "manifest_sha256": sha(MANIFEST),
             "cases": outcomes, "scope": "synthetic source-only saved measurement, no current full compatibility or physical claim"}
    target = HERE / "draft-saved-600-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "positive": len(outcomes), "negative": len(outcomes),
                      "proof_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
