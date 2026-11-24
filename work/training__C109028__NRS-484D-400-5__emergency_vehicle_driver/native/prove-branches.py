"""Exercise the pursuit and lamps-only statutory alternatives on retained source shapes."""
import json
from pathlib import Path
import tempfile

from measure import measure, rows, sha
from prove import BRANCHES, make_source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def compare(first, second, permitted_native, permitted_dispatch):
    a, b = measure(*first), measure(*second)
    ca, cb = json.loads(first[0].read_text()), json.loads(second[0].read_text())
    excluded = {"case_id", "emergency_call_requested", "immediate_pursuit_requested",
                "siren_requested"}
    if {k: v for k, v in ca.items() if k not in excluded} != \
            {k: v for k, v in cb.items() if k not in excluded}:
        raise ValueError("Fixed construction differs")
    if rows(first[2]) != rows(second[2]):
        raise ValueError("Matched video join differs")
    for x, y in zip(rows(first[1]), rows(second[1])):
        if {k: v for k, v in x.items() if k not in permitted_native} != \
                {k: v for k, v in y.items() if k not in permitted_native}:
            raise ValueError("Matched Native signal or motion differs")
    for x, y in zip(rows(first[3]), rows(second[3])):
        if {k: v for k, v in x.items() if k not in permitted_dispatch} != \
                {k: v for k, v in y.items() if k not in permitted_dispatch}:
            raise ValueError("Matched dispatch source differs")
    return {"case_ids": [a["case_id"], b["case_id"]],
            "siren_frames": [a["siren_observed_frames"], b["siren_observed_frames"]],
            "outside_documented_response_frames":
                [a["siren_outside_documented_response_frames"],
                 b["siren_outside_documented_response_frames"]],
            "source_hashes": [[sha(p) for p in first], [sha(p) for p in second]],
            "physical_legal_verdict": None}


def reject(files, target, old, new, expected):
    path = files[target]
    original = path.read_text()
    path.write_text(original.replace(old, new, 1))
    try:
        try:
            measure(*files)
        except ValueError as exc:
            if expected not in str(exc):
                raise
            return {"mutation": target, "expected_error": expected, "actual_error": str(exc)}
        raise AssertionError("Altered source accepted")
    finally:
        path.write_text(original)


def run():
    ROOT.joinpath(".runtime-work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c109028-branches-") as folder:
        files = {}
        for name in BRANCHES:
            base = Path(folder) / name
            base.mkdir()
            files[name] = make_source(base, name)
        results = {name: measure(*item) for name, item in files.items()}
        if {name: result["siren_outside_documented_response_frames"]
                for name, result in results.items()} != {
                "probe_a": 0, "probe_b": 200, "pursuit": 0,
                "call_lamps_only": 0, "ordinary_lamps_only": 0}:
            raise AssertionError("Statutory alternative source results differ")
        comparisons = {
            "call_vs_ordinary_siren": compare(files["probe_a"], files["probe_b"],
                                               set(), {"emergency_call_documented"}),
            "call_vs_pursuit_siren": compare(files["probe_a"], files["pursuit"],
                                             set(), {"emergency_call_documented",
                                                     "immediate_pursuit_documented"}),
            "call_siren_vs_lamps_only": compare(files["probe_a"], files["call_lamps_only"],
                                                {"siren_observed"}, set()),
            "call_vs_ordinary_lamps_only": compare(files["call_lamps_only"],
                                                   files["ordinary_lamps_only"],
                                                   set(), {"emergency_call_documented"}),
        }
        negatives = [
            reject(files["pursuit"], 3, '"native_frame": 1000', '"native_frame": 999',
                   "Retained frame/time join differs"),
            reject(files["call_lamps_only"], 2, '"native_frame": 1000',
                   '"native_frame": 999', "Retained frame/time join differs"),
        ]
        missing = files["pursuit"][3]
        saved = missing.read_text()
        missing.unlink()
        try:
            try:
                measure(*files["pursuit"])
            except ValueError as exc:
                if "Missing retained source" not in str(exc):
                    raise
                negatives.append({"mutation": "missing_dispatch", "actual_error": str(exc)})
            else:
                raise AssertionError("Missing dispatch source accepted")
        finally:
            missing.write_text(saved)
        receipt = {"format": "c109028-branch-source-proof-v1",
                   "branch_results": results, "controlled_comparisons": comparisons,
                   "negatives": negatives, "synthetic_diagnostic": True,
                   "original_native_observed": False, "physical_legal_verdict": None}
    (HERE / "branch-source-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return {"branches": len(results), "comparisons": len(comparisons),
            "negatives": len(negatives)}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
