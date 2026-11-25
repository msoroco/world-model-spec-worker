"""Independent rail-stop queue and marked-lane comparison audit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from finalize import analyze

ASSIGNMENT = "training__C202463__NRS-484B-560-3__motor_vehicle_driver"
PAIRS = {("a", "b"): "right_position", ("b", "c"): "two_queue",
         ("c", "d"): "four_marked_lanes", ("d", "e"): "five_marked_lanes"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(attempt_a, attempt_b, processing_a, processing_b, diagnostic=False, review_path=None):
    a, b = Path(attempt_a).resolve(), Path(attempt_b).resolve()
    pa, pb = (json.loads(Path(path).read_text()) for path in (processing_a, processing_b))
    identities = [p.get("case_id", "") for p in (pa, pb)]
    suffixes = tuple(value.removeprefix(ASSIGNMENT + "__probe_") for value in identities)
    if suffixes not in PAIRS or any(value != ASSIGNMENT + "__probe_" + suffix
                                    for value, suffix in zip(identities, suffixes)):
        raise ValueError("Exact rail comparison cases differ")
    if not all(p.get("passed") is True and p.get("recorded_only") is True for p in (pa, pb)):
        raise ValueError("Recorded-only rail processing proof missing")
    if diagnostic:
        for source in ("road.xodr", "rail-review/required-stop.json",
                       "rail-review/required-stop.source.txt",
                       "rail-review/rail-crossing.json", "rail-review/rail-crossing.source.txt",
                       "rail-review/gate-indication.json", "rail-review/gate-indication.source.txt"):
            if sha(a / source) != sha(b / source):
                raise ValueError("Fixed rail source differs: " + source)
    else:
        if review_path is None or not Path(review_path).is_file():
            raise ValueError("Original pairwise rail context review missing")
        review_path = Path(review_path)
        review = json.loads(review_path.read_text())
        source_text = review_path.with_suffix(".source.txt")
        if (not source_text.is_file() or review.get("source_sha256") != sha(source_text)
                or review.get("review_status") != "independently_reviewed"
                or not review.get("reviewer_id") or review.get("case_ids") != identities
                or review.get("road_sha256") != [sha(a / "road.xodr"), sha(b / "road.xodr")]
                or review.get("sole_variation") != PAIRS[suffixes]
                or review.get("other_context_invariants_reviewed") is not True):
            raise ValueError("Original pairwise rail context source differs")
    configs = [json.loads((path / "config.json").read_text()) for path in (a, b)]
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                  "cameras", "source_actor_ids", "required_atoms", "brake_margin_m"):
        if configs[0].get(field) != configs[1].get(field):
            raise ValueError("Fixed rail configuration differs: " + field)
    measured = [analyze(path) for path in (a, b)]
    if [item["case_id"] for item in measured] != identities:
        raise ValueError("Rail measurements differ from processing case IDs")
    first, second = (item["measurement"] for item in measured)
    if suffixes in (("a", "b"), ("b", "c")):
        if [item["total_marked_lanes"] for item in (first, second)] != [2, 2]:
            raise ValueError("Queue contrast changed marked lane count")
        if sha(a / "rail-review/lane-markings.json") != sha(b / "rail-review/lane-markings.json"):
            raise ValueError("Queue contrast changed reviewed lane markings")
        expected = ("right_single", "left_single") if suffixes == ("a", "b") else (
            "left_single", "left_abreast")
        if tuple(c["queue_mode"] for c in configs) != expected:
            raise ValueError("Queue contrast selected another controller")
        if suffixes == ("a", "b"):
            if not (first["minimum_right_edge_gap_m"] < second["minimum_right_edge_gap_m"]
                    and first["abreast_two_queue_frames"] == second["abreast_two_queue_frames"] == 0):
                raise ValueError("Measured far-right contrast absent")
        elif not (first["abreast_two_queue_frames"] == 0
                  and second["abreast_two_queue_frames"] == 300
                  and first["minimum_right_edge_gap_m"] == second["minimum_right_edge_gap_m"]):
            raise ValueError("Measured two-queue contrast absent")
    else:
        expected_lanes = [2, 4] if suffixes == ("c", "d") else [4, 5]
        if [item["total_marked_lanes"] for item in (first, second)] != expected_lanes:
            raise ValueError("Measured marked-lane boundary differs")
        if [c["marked_lane_count"] for c in configs] != expected_lanes or any(
                c["queue_mode"] != "left_abreast" for c in configs):
            raise ValueError("Lane threshold comparison changed queue controller")
        if not (first["abreast_two_queue_frames"] == second["abreast_two_queue_frames"] == 300
                and first["minimum_right_edge_gap_m"] == second["minimum_right_edge_gap_m"]):
            raise ValueError("Lane threshold comparison changed queue geometry")
    if diagnostic and any(json.loads((path / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") != "synthetic_fixture" for path in (a, b)):
        raise ValueError("Diagnostic rail comparison needs identified CPU fixtures")
    return {"format": "c202463-comparison-audit-v1", "case_ids": identities,
        "diagnostic_fixture": diagnostic, "fixed_road_sha256": sha(a / "road.xodr"),
        "deliberate_difference": PAIRS[suffixes],
        "measured_marked_lanes": [first["total_marked_lanes"], second["total_marked_lanes"]],
        "measured_abreast_frames": [first["abreast_two_queue_frames"], second["abreast_two_queue_frames"]],
        "measured_right_gap_m": [first["minimum_right_edge_gap_m"], second["minimum_right_edge_gap_m"]],
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("attempt-a", "attempt-b", "processing-a", "processing-b", "output"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review")
    args = parser.parse_args()
    result = compare(args.attempt_a, args.attempt_b, args.processing_a,
                     args.processing_b, args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
