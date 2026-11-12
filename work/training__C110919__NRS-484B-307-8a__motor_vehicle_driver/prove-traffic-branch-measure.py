"""Exercise saved-only traffic/body measurement on synthetic source-shaped rows."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from traffic_branch_finalize import measure_traffic_branch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def body(x):
    return [[x - 1.0, -2.75], [x - 1.0, -.75],
            [x + 1.0, -2.75], [x + 1.0, -.75]]


def source(suffix):
    path = ROOT / ".runtime-work/c110919-update035-eight-case-matrix" / suffix / \
        "primary/compatibility/native_samples.jsonl"
    require(path.is_file(), "Current source-shaped ego history missing")
    return [json.loads(line) for line in path.read_text().splitlines()]


def attach(rows, suffix):
    answer = deepcopy(rows)
    for index, row in enumerate(answer):
        occupied = 220 <= index <= 260
        x = 10.0 if occupied else (-30.0 if index < 220 else 30.0)
        row.update(traffic_policy=suffix,
                   other_traffic_center_xy_m=[x, -1.75],
                   other_traffic_body_xy_m=body(x),
                   other_traffic_speed_mps=4.0,
                   other_traffic_signal_state_observed="Green",
                   traffic_conflict_occupied=occupied,
                   synthetic_diagnostic=True)
    return answer


def write_sources(folder, rows):
    road = {"cross_traffic_signal_actor_id": 602,
            "lanes": {"west_traffic_right": {"road_id": 3, "lane_id": -1,
                                               "forward_xy": [1.0, 0.0]}}}
    (folder / "road_geometry.json").write_text(json.dumps(road) + "\n")
    (folder / "native_samples.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))


def main():
    outcomes = {}
    negatives = {}
    with TemporaryDirectory(prefix="c110919-traffic-measure-", dir=ROOT / ".runtime-work") as name:
        folder = Path(name)
        for suffix, prior in (("traffic_yield_wait", "yield_wait"),
                              ("traffic_conflict_entry", "yield_conflict_entry")):
            rows = attach(source(prior), suffix)
            write_sources(folder, rows)
            outcome = measure_traffic_branch(folder, rows, suffix)
            overlap = outcome["value"]["body_traffic_overlap_frames"]
            require(bool(overlap) == (suffix == "traffic_conflict_entry"),
                    "Synthetic controlled traffic/body difference absent")
            outcomes[suffix] = {"measurement": outcome["value"],
                                "source_hashes": outcome["sources"]}
            damaged = deepcopy(rows)
            damaged[240]["other_traffic_signal_state_observed"] = "Red"
            try:
                measure_traffic_branch(folder, damaged, suffix)
            except ValueError as error:
                negatives[suffix + "__wrong_signal"] = str(error)
            else:
                raise ValueError("Wrong cross-traffic signal was accepted")
            damaged = deepcopy(rows)
            damaged[240].pop("other_traffic_body_xy_m")
            try:
                measure_traffic_branch(folder, damaged, suffix)
            except ValueError as error:
                negatives[suffix + "__missing_body"] = str(error)
            else:
                raise ValueError("Missing other-traffic body was accepted")
    proof = {"format": "c110919-cross-traffic-saved-measure-unit-v1",
             "diagnostic_only": True, "synthetic_ego_sources": True,
             "outcomes": outcomes, "negative_rejections": negatives,
             "original_native_accepted": False, "legal_verdict_claimed": False}
    target = HERE / "update037-traffic-measure-unit-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"measurements": len(outcomes),
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(target), "diagnostic_only": True}))


if __name__ == "__main__":
    main()
