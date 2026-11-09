"""Exact CPU proof for the unselected red-plus-arrow Native requests."""
import json
from pathlib import Path
import shutil
import tempfile

from build import CASE, CASES, HERE, POLICIES, check, digest, write


def reject(bundle, mutation):
    with tempfile.TemporaryDirectory(prefix="c111603-negative-") as name:
        copy = Path(name) / "bundle"
        shutil.copytree(bundle, copy)
        mutation(copy)
        try:
            check(copy)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return True
    raise AssertionError("Changed C111603 request passed exact check")


def prove():
    positive = negative = 0
    pair_checks = []
    trigger_checks = []
    for suffix in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            result = check(bundle)
            assert result["frames"] == 480 and not result["delivery_ready"]
            positive += 1

            def edit_config(path):
                p = path / "config.json"
                data = json.loads(p.read_text())
                data["source_text"] = "changed statutory source"
                write(p, data)

            def edit_signal(path):
                p = path / "arrow-intersection.xodr"
                p.write_text(p.read_text().replace("green-right-arrow", "green-left-arrow"))

            def edit_track(path):
                p = path / "requested-tracks.jsonl"
                lines = p.read_text().splitlines()
                row = json.loads(lines[215]); row["requested_signal"]["green_arrow"] = "left"
                lines[215] = json.dumps(row)
                p.write_text("\n".join(lines) + "\n")

            def edit_actor(path):
                p = path / "requested-tracks.jsonl"
                lines = p.read_text().splitlines()
                row = json.loads(lines[220]); row["requested_other_vehicle_xyz_m"][0] += 2
                lines[220] = json.dumps(row)
                p.write_text("\n".join(lines) + "\n")

            for mutation in (edit_config, edit_signal, edit_track, edit_actor):
                reject(bundle, mutation)
                negative += 1

        left = HERE / "drafts" / suffix
        cfgs = {c: json.loads((left / c / "config.json").read_text()) for c in POLICIES}
        base = cfgs["primary"]
        assert cfgs["fallback1"]["approach_speed_mps"] < base["approach_speed_mps"]
        assert cfgs["fallback2"]["camera_policy"] == "elevated_overview"
        assert cfgs["fallback3"]["pre_approach_dwell_s"] == 2
        for candidate in POLICIES:
            assert digest(left / candidate / "arrow-intersection.xodr") == base["road_sha256"]
        trigger_checks.append(suffix)

    for candidate in POLICIES:
        one = HERE / "drafts" / "witness_1" / candidate
        two = HERE / "drafts" / "witness_2" / candidate
        a = json.loads((one / "config.json").read_text())
        b = json.loads((two / "config.json").read_text())
        assert a["source_text"] == b["source_text"]
        assert a["road_sha256"] == b["road_sha256"]
        for key in ("approach_speed_mps", "camera_policy", "pre_approach_dwell_s", "yield_hold_s"):
            assert a[key] == b[key]
        rows_a = [json.loads(row) for row in (one / "requested-tracks.jsonl").read_text().splitlines()]
        rows_b = [json.loads(row) for row in (two / "requested-tracks.jsonl").read_text().splitlines()]
        assert len(rows_a) == len(rows_b) == 480
        assert all(x["requested_signal"] == y["requested_signal"] and
                   x["requested_other_vehicle_xyz_m"] == y["requested_other_vehicle_xyz_m"]
                   for x, y in zip(rows_a, rows_b))
        assert any(x["requested_ego_xyz_m"] != y["requested_ego_xyz_m"]
                   for x, y in zip(rows_a, rows_b))
        pair_checks.append(candidate)
    result = {"format": "c111603-3079a-request-proof-v1", "assignment_id": CASE.name,
              "positive_count": positive, "negative_count": negative,
              "controlled_pair_count": len(pair_checks), "fallback_policy_groups": len(trigger_checks),
              "original_native_observed": False, "delivery_ready": False}
    write(HERE / "request-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
