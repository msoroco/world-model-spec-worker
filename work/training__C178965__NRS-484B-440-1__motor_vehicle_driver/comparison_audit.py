"""Independent CPU comparison of fixed roadside sources and declared changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "native/tests"))
from test_saved import fixture
from finalize_saved import summarize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(paths):
    rows = []
    for number, path in enumerate(paths, 1):
        tag = f"probe_0{number}"
        case = HERE.name + "__" + tag
        result = summarize(path, case, diagnostic=True)
        stopped = result["stopped"]
        rows.append({"case_id": case, "survey_sha256": sha(Path(path) / "original-highway-survey.json"),
                     "frames": result["frame_count"], "stopped": len(stopped),
                     "on_pavement": sum(row["pavement_overlap_m"] > 0 for row in stopped),
                     "minimum_opposite_width_m": min(row["opposite_unobstructed_width_m"] for row in stopped),
                     "failure_frames": sum(row["failure_active"] for row in stopped),
                     "forward_clear": all(row["clear_200ft_forward_proxy"] for row in stopped),
                     "backward_clear": all(row["clear_200ft_backward_proxy"] for row in stopped),
                     "trace_sha256": result["source_sha256"]["trace"]})
    if len({row["survey_sha256"] for row in rows}) != 1 or any(row["frames"] != 600 for row in rows):
        raise ValueError("Comparison changed fixed road survey or capture duration")
    if [row["on_pavement"] for row in rows] != [0, 200, 200]:
        raise ValueError("Comparison lost off/on pavement difference")
    if [row["failure_frames"] for row in rows] != [0, 0, 200]:
        raise ValueError("Comparison lost disabled construction difference")
    if not all(row["forward_clear"] and row["backward_clear"] for row in rows):
        raise ValueError("Comparison lacks both directional sight observations")
    return {"format": "c178965-comparison-diagnostic-v1", "cases": rows,
            "fixed_survey": True, "legal_result": None, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--negative-missing-sight", action="store_true")
    args = parser.parse_args()
    plan = json.loads((HERE / "case-plan.json").read_text())
    if args.comparison != plan["comparisons"][0]["comparison_id"]:
        raise ValueError("Wrong exact comparison")
    if not (args.diagnostic or args.negative_missing_sight):
        raise ValueError("Original accepted recordings required for comparison audit")
    temp_root = Path(os.environ.get("TMPDIR", "/")).resolve()
    if not temp_root.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Set TMPDIR under .runtime-work")
    with tempfile.TemporaryDirectory(dir=temp_root, prefix="c178965-comparison-") as temporary:
        paths = []
        for number in (1, 2, 3):
            path = Path(temporary) / f"probe_0{number}"
            path.mkdir()
            fixture(path, number)
            paths.append(path)
        if args.negative_missing_sight:
            (paths[2] / "visibility-native.jsonl").unlink()
        print(json.dumps(audit(paths), sort_keys=True))


if __name__ == "__main__":
    main()
