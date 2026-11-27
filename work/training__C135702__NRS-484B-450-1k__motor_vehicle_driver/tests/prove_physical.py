"""Create three synthetic physical-outcome checks and a lifecycle-order test."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from physical_check import EVENTS, assess, lifecycle


def run_fixture(suffix, kind):
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c135702-physical-") as temp:
        folder = Path(temp)
        source = ROOT / "selected-source" / (("condition_" + suffix) if suffix in ("a", "b") else suffix)
        for name in ("native_samples.jsonl", "video_frames.jsonl",
                     "camera-frames.jsonl", "obstruction-inventory.json"):
            shutil.copyfile(source / name, folder / name)
        if suffix == "a":
            cfg = json.loads((ROOT / "config.json").read_text())
        elif suffix == "b":
            construction = json.loads((ROOT / "cases/condition_b/construction.json").read_text())
            cfg = json.loads(next(item["content"] for item in construction["files"]
                                  if item["path"] == "config.json"))
        else:
            cfg = json.loads((ROOT / "cases" / suffix / "config.json").read_text())
        (folder / "config.json").write_text(json.dumps(cfg) + "\n")
        if kind == "incomplete_motion":
            path = folder / "native_samples.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row["ego_speed_m_s"] = 2
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (folder / "native_samples.jsonl").unlink()
        result = assess(folder)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise AssertionError("Physical fixture returned another outcome")
        target = ROOT / "physical-proofs" / (suffix + "-" + kind + ".json")
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"case_id": result["case_id"], "kind": kind,
                          "status": expected, "synthetic_only": True}))


def run_lifecycle():
    proof = lifecycle(list(EVENTS))
    swapped = list(EVENTS)
    swapped[3], swapped[4] = swapped[4], swapped[3]
    try:
        lifecycle(swapped)
    except ValueError as error:
        if "precedes Native ownership closure" not in str(error):
            raise
    else:
        raise AssertionError("Out-of-order owner release passed")
    print(json.dumps({"events": proof["events"],
                      "reordered_release_rejected": True,
                      "original_capture_attested": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-suffix", choices=("a", "b", "police_absent", "police_present"))
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--lifecycle", action="store_true")
    args = parser.parse_args()
    if args.lifecycle:
        run_lifecycle()
    else:
        if not args.case_suffix or not args.kind:
            parser.error("select one exact case suffix and fixture kind")
        run_fixture(args.case_suffix, args.kind)
