"""Generate three CPU physical fixtures for one statutory case."""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "native"))

from statutory_physical_check import EVENTS, assess, lifecycle


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, kind):
    construction_name = "excavation-construction.json" if name == "excavation_kind" else "statutory-construction.json"
    construction = json.loads((ROOT / "cases" / name / construction_name).read_text())
    cfg = json.loads(next(item["content"] for item in construction["files"]
                          if item["path"] == "config.json"))
    recipe = json.loads((ROOT / ("selected-recipe-statutory-" + name + ".json")).read_text())
    needed = {"native_samples.jsonl", "video_frames.jsonl", "camera-frames.jsonl",
              "obstruction-inventory.json"}
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c135702-stat-physical-") as temp:
        folder = Path(temp)
        (folder / "config.json").write_text(json.dumps(cfg) + "\n")
        for source in recipe["sources"]:
            if source["path"] in needed:
                original = REPO / source["source"]
                if sha(original) != source["sha256"]:
                    raise ValueError("Fixture source changed")
                shutil.copyfile(original, folder / source["path"])
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
        raise AssertionError("Unexpected physical fixture status")
    target = ROOT / "cases" / name / "proofs" / ("physical-" + kind + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": cfg["case_id"], "kind": kind,
                      "status": expected, "synthetic_only": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--lifecycle", action="store_true")
    args = parser.parse_args()
    if args.lifecycle:
        lifecycle(list(EVENTS))
        wrong = list(EVENTS)
        wrong[3], wrong[4] = wrong[4], wrong[3]
        try:
            lifecycle(wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("Out-of-order Native release accepted")
        print(json.dumps({"events": EVENTS, "reordered_release_rejected": True}))
    else:
        if not args.name or not args.kind:
            parser.error("Select case name and fixture kind")
        run(args.name, args.kind)
