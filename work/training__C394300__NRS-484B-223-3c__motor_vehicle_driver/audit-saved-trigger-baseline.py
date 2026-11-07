"""Independently audit 3(c) synthetic package sources and two measured fallbacks."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from trigger_evidence import evaluate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path, values):
    path.write_text("".join(json.dumps(row) + "\n" for row in values))


def main():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    report = []
    for suffix in ("below_50_ft", "at_50_ft", "above_50_ft"):
        log = (HERE / f"package-compatibility-{suffix}-primary.log").read_text().splitlines()
        assert len(log) >= 2 and log[0].startswith("scratch ")
        source = Path(log[0].split(" ", 1)[1]) / "fixture"
        assert source.is_dir() and source.parent.is_relative_to(HERE.parents[1] / ".runtime-work")
        receipt = json.loads(log[1])["positive"]
        entry = next(case for case in manifest["cases"] if case["case_id"].endswith("__" + suffix))
        assert receipt["passed"] is True and receipt["candidate_id"] == "primary"
        assert receipt["construction_sha256"] == entry["construction_sha256"]
        assert sha(HERE / entry["construction"]) == entry["construction_sha256"]
        samples = rows(source / "native_samples.jsonl")
        assert len(samples) == 480
        assert [r["native_frame"] for r in samples] == list(range(100, 580))
        assert all(r["controller_request"]["route_error_m"] == 0.0 for r in samples)
        baseline1 = evaluate(source, "fallback1")
        baseline2 = evaluate(source, "fallback2")
        assert baseline1["triggered"] is False
        assert baseline2["triggered"] is False
        assert baseline1["metric"]["turn_completion_time_s"] == 6.75
        assert baseline1["metric"]["inbound_body_containment_fraction"] == 1.0
        assert baseline2["metric"]["max_premerge_route_error_m"] == 0.0
        assert baseline1["source_hashes"]["native_samples.jsonl"] == sha(source / "native_samples.jsonl")
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary)
            shutil.copyfile(source / "road_geometry.json", probe / "road_geometry.json")
            changed = json.loads(json.dumps(samples))
            changed[0]["native_body_xy_m"][0][0] = -75.0
            save(probe / "native_samples.jsonl", changed)
            assert evaluate(probe, "fallback1")["triggered"] is True
            changed = json.loads(json.dumps(samples))
            changed[0]["controller_request"]["route_error_m"] = 0.36
            save(probe / "native_samples.jsonl", changed)
            assert evaluate(probe, "fallback2")["triggered"] is True
            changed[0]["controller_request"].pop("route_error_m")
            save(probe / "native_samples.jsonl", changed)
            try:
                evaluate(probe, "fallback2")
            except ValueError as error:
                assert "route_error_m" in str(error)
            else:
                raise AssertionError("Missing route error was accepted")
        report.append({"case": suffix, "frames": 480,
                       "turn_completion_time_s": baseline1["metric"]["turn_completion_time_s"],
                       "baseline_fallback1": False, "baseline_fallback2": False,
                       "isolated_crossings": ["body_containment", "route_error"],
                       "source_sha256": sha(source / "native_samples.jsonl")})
    print(json.dumps({"passed": True, "source_kind": "synthetic_local_diagnostic",
                      "original_native_or_pixels_observed": False, "cases": report}, sort_keys=True))


if __name__ == "__main__":
    main()
