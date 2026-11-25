"""CPU proof for observed-source traffic response comparison."""
import copy
import json
from pathlib import Path

from audit_traffic_sources import compare, measure, sha
from prove_saved import fixture, put

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / ".runtime-work/c109137-traffic-source-proof"
ASSIGNMENT = "training__C109137__NRS-484B-217-2__motor_vehicle_driver"


def write_rows(path, rows):
    path.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in rows))


def make(label):
    bundle = HERE / "drafts/probe_1/primary"
    raw, frames, review = fixture(bundle, OUT / label)
    original = [json.loads(x) for x in raw.read_text().splitlines()]
    rows = copy.deepcopy(original)
    if label == "following_brake":
        for i in range(200, len(rows)):
            rows[i]["following"]["velocity_native_xyz_mps"] = [1, 0, 0]
            rows[i]["following"]["speed_mps"] = 1
    write_rows(raw, rows)
    reviewed = json.loads(review.read_text())
    reviewed["case_id"] = ASSIGNMENT + "__traffic_" + label
    reviewed["raw_sha256"] = sha(raw)
    put(review, reviewed)
    return raw, frames, review, rows, reviewed


def reject(raw, frames, review, rows, reviewed, label, mutate, expected):
    changed = copy.deepcopy(rows)
    mutate(changed)
    write_rows(raw, changed)
    check_review = copy.deepcopy(reviewed)
    check_review["raw_sha256"] = sha(raw)
    put(review, check_review)
    try:
        measure(raw, frames, review)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f"{label} rejected for wrong reason: {exc}")
    else:
        raise AssertionError("Traffic source mutation accepted: " + label)
    finally:
        write_rows(raw, rows)
        put(review, reviewed)
    return {"mutation": label, "expected_error": expected}


def reject_comparison(clear, raw, frames, review, rows, reviewed, label, mutate, expected):
    changed = copy.deepcopy(rows)
    mutate(changed)
    write_rows(raw, changed)
    check_review = copy.deepcopy(reviewed)
    check_review["raw_sha256"] = sha(raw)
    put(review, check_review)
    try:
        compare(clear, measure(raw, frames, review))
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f"{label} rejected for wrong reason: {exc}")
    else:
        raise AssertionError("Changed fixed traffic condition accepted: " + label)
    finally:
        write_rows(raw, rows)
        put(review, reviewed)
    return {"mutation": label, "expected_error": expected}


def main():
    clear = make("clear_traffic")
    response = make("following_brake")
    a = measure(*clear[:3])
    b = measure(*response[:3])
    report = compare(a, b)
    if a["following_speed_drop_mps"] != 0 or b["following_speed_drop_mps"] != 1:
        raise AssertionError("Source-measured response differs")
    raw, frames, review, rows, reviewed = response
    negatives = [
        reject(raw, frames, review, rows, reviewed, "missing_participant",
               lambda r: r[220].pop("following"), "Traffic participant identity absent"),
        reject(raw, frames, review, rows, reviewed, "velocity_mismatch",
               lambda r: r[220]["following"].__setitem__("speed_mps", 19),
               "Traffic observed velocity absent or inconsistent"),
        reject(raw, frames, review, rows, reviewed, "frame_join",
               lambda r: r[220].__setitem__("native_frame", 9999),
               "Traffic Native/video frame join differs"),
        reject(raw, frames, review, rows, reviewed, "source_provenance",
               lambda r: r[220].__setitem__("source_kind", "original_native"),
               "Traffic observed source provenance differs"),
    ]
    crossing = b["first_stripe_body_frame"]
    negatives.append(reject_comparison(
        a, raw, frames, review, rows, reviewed, "changed_stripe_entry",
        lambda r: [vertex.__setitem__(1, -abs(vertex[1]) - 1)
                   for vertex in r[crossing]["ego"]["body_native_xyz_m"]],
        "Traffic comparison changed fixed condition: first_stripe_body_frame"))
    signal = b["first_left_indicator_frame"]
    negatives.append(reject_comparison(
        a, raw, frames, review, rows, reviewed, "changed_indicator_onset",
        lambda r: r[signal].__setitem__("observed_left_indicator", False),
        "Traffic comparison changed fixed condition: first_left_indicator_frame"))
    changed = copy.deepcopy(rows)
    changed[220]["following"]["speed_mps"] = 19
    write_rows(raw, changed)
    try:
        measure(raw, frames, review)
    except ValueError as exc:
        if "source hash differs" not in str(exc):
            raise
        negatives.append({"mutation": "unsealed_bytes", "expected_error": "Traffic review source hash differs"})
    else:
        raise AssertionError("Unsealed source accepted")
    finally:
        write_rows(raw, rows)
    report["negative_rejections"] = negatives
    report["source_scope"] = "synthetic Native-shaped actor/video rows only"
    receipt = HERE / "traffic-source-comparison-proof.json"
    put(receipt, report)
    print(json.dumps({"passed": True, "observed_source_windows": 2,
                      "negative_rejections": len(negatives), "receipt_sha256": sha(receipt)}))


if __name__ == "__main__":
    main()
