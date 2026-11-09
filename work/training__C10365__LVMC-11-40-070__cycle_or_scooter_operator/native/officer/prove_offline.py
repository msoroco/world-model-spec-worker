"""Positive and material negative checks of all eight exact copied bundles."""
import copy
import json
from pathlib import Path
import tempfile

from build import HERE, CASES, POLICIES, build
from check import check


def prove():
    build()
    positives = []
    negatives = []
    for suffix in CASES:
        for candidate in POLICIES:
            source = HERE / "drafts" / suffix / candidate
            positives.append(check(source))
            for name, mutate in (
                ("law", lambda b: (b / "assignment-source.json").write_text(
                    (b / "assignment-source.json").read_text().replace(
                        "unless otherwise directed by a Police Officer", ""))),
                ("cell", lambda b: (b / "assignment-source.json").write_text(
                    (b / "assignment-source.json").read_text().replace(
                        '"control": "police_officer"', '"control": "traffic_control_device"'))),
                ("officer_cue", lambda b: (b / "config.json").write_text(
                    (b / "config.json").read_text().replace(
                        CASES[suffix], "unrelated_cue"))),
                ("track", lambda b: (b / "requested-tracks.jsonl").write_text(
                    (b / "requested-tracks.jsonl").read_text().replace(
                        '"requested_speed_mps":', '"requested_speed_changed":', 1))),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    bundle = Path(tmp)
                    for filename in ("config.json", "assignment-source.json",
                                     "case-plan.json", "alley-stop.xodr",
                                     "requested-tracks.jsonl"):
                        (bundle / filename).write_bytes((source / filename).read_bytes())
                    mutate(bundle)
                    try:
                        check(bundle)
                    except (ValueError, KeyError) as exc:
                        negatives.append({"case": suffix, "candidate": candidate,
                                          "mutation": name, "rejected": str(exc)})
                    else:
                        raise AssertionError(f"{suffix}/{candidate}/{name} accepted")
    result = {"format": "c10365-exact-offline-proof-v1",
              "positive_count": len(positives), "negative_count": len(negatives),
              "positives": positives, "negatives": negatives,
              "original_native_observed": False, "delivery_ready": False}
    (HERE / "offline-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = prove()
    print(json.dumps({"positive_count": result["positive_count"],
                      "negative_count": result["negative_count"]}))
