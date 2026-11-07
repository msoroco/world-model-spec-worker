"""Save six source-bound baseline decisions and isolated tracking/pixel crossings."""
import hashlib
import json
from pathlib import Path

from native.fallback_triggers import evaluate

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SOURCE = HERE / "signal-fixtures"
OUTPUT = SOURCE / "case-triggers"
SUFFIXES = ("below_100_ft", "at_100_ft", "above_100_ft",
            "below_300_ft", "at_300_ft", "above_300_ft")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                    for row in rows))


def measured(path, map_hash):
    result = evaluate(path, expected_sha256=sha(path), source_kind="synthetic_cpu_fixture",
                      map_sha256=map_hash)
    result["source_path"] = str(path.relative_to(REPO))
    return result


def main():
    OUTPUT.mkdir(exist_ok=True)
    manifest = json.loads((HERE / "native-construction-manifest.json").read_text())
    draft = json.loads((HERE / "draft-execution-manifest.json").read_text())
    cases = {case["case_id"].split("__")[-1]: case for case in draft["cases"]}
    report = []
    for suffix in SUFFIXES:
        path = SOURCE / (suffix + ".jsonl")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 800
        baseline = measured(path, manifest["map_sha256"])
        assert not baseline["fallback2"] and not baseline["fallback3"]
        assert baseline["fallback1"] == (suffix == "above_300_ft")
        onset = next(i for i, row in enumerate(rows) if row["signal"] == "left")
        track = json.loads(json.dumps(rows))
        track[onset + 10]["route_error_m"] = .5
        track_path = OUTPUT / (suffix + "-fallback2.jsonl")
        save(track_path, track)
        tracking = measured(track_path, manifest["map_sha256"])
        assert tracking["fallback2"] and tracking["fallback1"] == baseline["fallback1"]
        assert not tracking["fallback3"]
        visible = json.loads(json.dumps(rows))
        for row in visible[onset:onset + 20]:
            row["signal_visible"] = False
        visible_path = OUTPUT / (suffix + "-fallback3.jsonl")
        save(visible_path, visible)
        visibility = measured(visible_path, manifest["map_sha256"])
        assert visibility["fallback3"] and visibility["fallback1"] == baseline["fallback1"]
        assert not visibility["fallback2"]
        # The existing source-hashed above-300-foot primary is the measured
        # fallback1 crossing. Its exact fallback1 construction requests a
        # four-meter longer inbound route, which still needs Native readback.
        if suffix == "above_300_ft":
            case = cases[suffix]
            primary = json.loads((HERE / case["construction"]).read_text())
            alternate = next(c for c in case["candidates"] if c["id"] == "fallback1")
            fallback = json.loads((HERE / alternate["construction"]).read_text())
            def request(construction):
                config = next(f["content"] for f in construction["files"] if f["path"] == "config.json")
                return json.loads(config)["native_request"]
            before, after = request(primary), request(fallback)
            assert before["start_x_m"] == -112 and after["start_x_m"] == -116
            assert before["signal_onset_x_m"] == after["signal_onset_x_m"]
            assert abs(after["signal_onset_x_m"] - after["start_x_m"] - 14.512) < 1e-9
        report.append({"case": suffix, "baseline": baseline,
                       "tracking_crossing": tracking, "visibility_crossing": visibility})
    output = {"format": "c329610-413-2-case-trigger-coverage-v1", "cases": report,
              "source_kind": "synthetic_cpu_fixture", "selected": False,
              "original_native_or_pixels_observed": False,
              "fallback1_requested_start_extension_m": 4.0,
              "fallback1_requested_runway_m_above_300_ft": 14.512}
    (HERE / "case-trigger-coverage.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(report), "isolated_crossings": 12,
                      "measured_fallback1_crossings": 1,
                      "fallback1_requested_runway_m_above_300_ft": 14.512,
                      "selected": False}))


if __name__ == "__main__":
    main()
