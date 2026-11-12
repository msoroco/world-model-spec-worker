"""Controlled source comparison for five selected exact timing points."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "update057-qualified-sweep-manifest.json"
INDEX = HERE / "update057-qualified-sweep-matrix-index.json"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def audit(claims):
    manifest, matrix = read(MANIFEST), read(INDEX)
    entries = [entry for entry in manifest["cases"]
               if entry["sweep_id"] == "C110919-right-of-way"]
    require(matrix["manifest_sha256"] == sha(MANIFEST) and
            len(entries) == len(claims) == 5, "Current timing matrix differs")
    receipts = {(item["case_id"], item["candidate_id"]): item for item in matrix["results"]}
    require(len(receipts) == 40, "Complete selected sweep matrix absent")
    fixed_config = None
    fixed_ego = None
    fixed_road = None
    fixed_signal = None
    observed = []
    for entry, claim in zip(entries, claims):
        ident = entry["case_id"]
        require(claim["case_id"] == ident and (ident, "primary") in receipts,
                "Timing comparison case or primary receipt differs")
        run = ROOT / ".runtime-work/c110919-update057-qualified-matrix" / sha(MANIFEST)[:12] / ident / "primary"
        attempt = run / "compatibility"
        config = read(attempt / "config.json")
        report = read(attempt / "analysis-report.json")
        result = read(attempt / "result.json")
        rows = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
        receipt = receipts[ident, "primary"]
        require(sha(run / "compatibility/compatibility.json") ==
                receipt["compatibility_receipt_sha256"] and
                sha(run / "saved/v0001/processing.json") ==
                receipt["saved_receipt_sha256"] and
                result["provenance_kind"] == "synthetic_local_diagnostic" and
                result["accepted"] is False and result["legal_verdict_claimed"] is False,
                "Source receipt or synthetic provenance differs")
        require(len(rows) == 480 and
                all(row.get("synthetic_diagnostic") is True and
                    row.get("speed_provenance") == "synthetic_native_sample"
                    for row in rows), "Native synthetic rows absent")
        frame = entry["authored_traffic_launch_frame"]
        require(config["traffic_launch_frame"] == frame and
                all(row["traffic_launch_frame"] == frame for row in rows) and
                claim["authored_launch_frame"] == frame,
                "Selected traffic launch differs from raw rows")
        held = {key: config[key] for key in ("case_suffix", "candidate_id", "cell_id",
                                            "law_id", "actor", "duration_s", "rate_hz",
                                            "knobs", "cameras", "mandatory_channels")}
        ego = [(row["native_body_xy_m"], row["speed_mps"],
                row["signal_state_observed"], row["walker_center_xy_m"],
                row["walker_conflict_occupied"]) for row in rows]
        road = sha(attempt / "road_geometry.json")
        signal = [(row["signal_state_observed"],
                   row["other_traffic_signal_state_observed"]) for row in rows]
        if fixed_config is None:
            fixed_config, fixed_ego, fixed_road, fixed_signal = held, ego, road, signal
        require(held == fixed_config and ego == fixed_ego and road == fixed_road and
                signal == fixed_signal,
                "Controlled comparison changed held ego, signal or road setup")
        measured = report["measurements"]["traffic_timing_sweep"]["value"]
        require(measured["authored_launch_frame"] == frame and
                measured["legal_right_of_way_verdict"] is None and
                result["realized_observables"]["ego_entry_relative_to_signal_directed_traffic"]["value"] ==
                measured["ego_minus_traffic_entry_s"] and
                claim["observed_traffic_first_frame"] ==
                measured["observed_traffic_first_frame"] and
                claim["observed_ego_first_frame"] ==
                measured["observed_ego_first_frame"] and
                claim["ego_minus_traffic_entry_s"] ==
                measured["ego_minus_traffic_entry_s"],
                "Measured timing comparison differs from saved Native result")
        observed.append(measured)
    observed = sorted(observed, key=lambda item: item["authored_launch_frame"])
    require([item["authored_launch_frame"] for item in observed] == [20, 30, 40, 50, 60] and
            [item["observed_traffic_first_frame"] for item in observed] ==
            [210, 220, 230, 240, 250] and
            len({item["observed_ego_first_frame"] for item in observed}) == 1 and
            [item["ego_minus_traffic_entry_s"] for item in observed] ==
            [2.9, 2.4, 1.9, 1.4, .9],
            "Synthetic timing launch did not vary the observed traffic path alone")
    return {"format": "c110919-selected-timing-controlled-comparison-v1",
            "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
            "comparisons_checked": 4, "launch_frames": [20, 30, 40, 50, 60],
            "observed_entry_gaps_s": [2.9, 2.4, 1.9, 1.4, .9],
            "fixed_ego_signal_road_checked": True,
            "synthetic_video_semantic_visibility_claimed": False,
            "original_native_accepted": False, "legal_verdict_claimed": False}


def main():
    manifest = read(MANIFEST)
    claims = []
    for entry in manifest["cases"]:
        if entry["sweep_id"] != "C110919-right-of-way":
            continue
        ident = entry["case_id"]
        run = ROOT / ".runtime-work/c110919-update057-qualified-matrix" / sha(MANIFEST)[:12] / ident / "primary"
        timing = read(run / "compatibility/analysis-report.json")["measurements"]["traffic_timing_sweep"]["value"]
        claims.append({"case_id": ident, "authored_launch_frame": entry["authored_traffic_launch_frame"],
                       "observed_traffic_first_frame": timing["observed_traffic_first_frame"],
                       "observed_ego_first_frame": timing["observed_ego_first_frame"],
                       "ego_minus_traffic_entry_s": timing["ego_minus_traffic_entry_s"]})
    output = audit(claims)
    negatives = {}
    for name, field, value in (
        ("wrong_launch", "authored_launch_frame", 999),
        ("wrong_traffic_entry", "observed_traffic_first_frame", 0),
        ("wrong_ego_entry", "observed_ego_first_frame", 0),
        ("invented_gap", "ego_minus_traffic_entry_s", 99),
    ):
        damaged = copy.deepcopy(claims)
        damaged[2][field] = value
        try:
            audit(damaged)
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("Damaged timing comparison accepted: " + name)
    output["claims"] = claims
    output["negative_rejections"] = negatives
    path = HERE / "update059-selected-timing-comparison-proof.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"comparisons_checked": 4,
                      "negative_rejections": len(negatives),
                      "proof_sha256": sha(path),
                      "original_native_accepted": False}))


if __name__ == "__main__":
    main()
