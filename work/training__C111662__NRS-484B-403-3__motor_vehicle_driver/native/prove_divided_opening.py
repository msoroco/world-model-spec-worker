"""Positive/negative exact CPU proof of the separate divided-highway branch."""
import json
from pathlib import Path
import tempfile

from build import POLICIES, put, sha
from divided_opening import BRANCH, CENTERS, check, measure


def prove():
    positives = negatives = measured = 0
    results = []
    for suffix in CENTERS:
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            check(bundle)
            result = measure(bundle)
            positives += 1
            measured += 1
            results.append(result)
            for mutation in ("source", "road", "track", "status"):
                with tempfile.TemporaryDirectory() as temporary:
                    target = Path(temporary)
                    for file in bundle.iterdir():
                        (target / file.name).write_bytes(file.read_bytes())
                    cfg_path = target / "config.json"
                    cfg = json.loads(cfg_path.read_text())
                    if mutation == "source":
                        source = target / "assignment-source.json"
                        source.write_text(source.read_text().replace("business district", "school zone"))
                    elif mutation == "road":
                        road = target / "divided-highway.xodr"
                        road.write_text(road.read_text().replace('type="median"', 'type="driving"', 1))
                        cfg["road_sha256"] = sha(road)
                        put(cfg_path, cfg)
                    elif mutation == "track":
                        track = target / "requested-tracks.jsonl"
                        rows = track.read_text().splitlines()
                        row = json.loads(rows[5])
                        row["requested_ego_xyz_m"][0] += .25
                        rows[5] = json.dumps(row)
                        track.write_text("\n".join(rows) + "\n")
                        cfg["tracks_sha256"] = sha(track)
                        put(cfg_path, cfg)
                    else:
                        cfg["status"] = "runnable"
                        put(cfg_path, cfg)
                    try:
                        check(target)
                    except ValueError:
                        negatives += 1
                    else:
                        raise AssertionError("Divided branch mutation accepted: " + mutation)
    for candidate in POLICIES:
        reference = next(row for row in results if row["candidate_id"] == candidate
                         and row["case_id"].endswith("__divided_reference"))
        opening = next(row for row in results if row["candidate_id"] == candidate
                       and row["case_id"].endswith("__divided_opening"))
        if (reference["crossing_in_authored_opening"] or
                not opening["crossing_in_authored_opening"] or
                abs(opening["crossing_x_m"] - reference["crossing_x_m"] - 45) > .0002):
            raise ValueError("Controlled divided-opening pair changed")
    proof = {"format": "c111662-4033-divided-opening-proof-v1",
             "candidate_count": positives, "exact_positive_count": positives,
             "exact_negative_count": negatives, "synthetic_measurement_count": measured,
             "controlled_pairs": len(POLICIES), "measurements": results,
             "synthetic_request_only": True, "original_native_observed": False,
             "district_designation_verified": False,
             "opening_exception_legally_verified": False, "delivery_ready": False}
    put(BRANCH / "proof.json", proof)
    return proof


if __name__ == "__main__":
    proof = prove()
    print(json.dumps({key: proof[key] for key in
                      ("candidate_count", "exact_positive_count", "exact_negative_count",
                       "synthetic_measurement_count", "controlled_pairs")}))
