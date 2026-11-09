"""Positive and material negative checks of the eight copied request bundles."""
import copy
import json
import tempfile
from pathlib import Path
from build import HERE, build, put, sha
from check import check


def prove():
    entries = build()["entries"]
    positives = negatives = 0
    for entry in entries:
        suffix = entry["case_id"].split("__")[-1]
        candidate = entry["candidate_id"]
        src = HERE / "drafts" / suffix / candidate
        check(src)
        positives += 1
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp)
            for name in ("assignment-source.json", "case-plan.json", "crest.xodr", "config.json", "requested-tracks.jsonl"):
                (dst / name).write_bytes((src / name).read_bytes())
            cfg = json.loads((dst / "config.json").read_text())
            for field, value in (("source_text", "altered law"), ("camera_policy", "missing"),
                                 ("original_native_observed", True), ("status", "runnable")):
                bad = copy.deepcopy(cfg)
                bad[field] = value
                put(dst / "config.json", bad)
                try:
                    check(dst)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Negative accepted: " + field)
            put(dst / "config.json", cfg)
            lines = (dst / "requested-tracks.jsonl").read_text().splitlines()
            changed = json.loads(lines[100]); changed["requested_ego_xyz_m"][2] += 1
            lines[100] = json.dumps(changed, sort_keys=True)
            (dst / "requested-tracks.jsonl").write_text("\n".join(lines) + "\n")
            cfg["tracks_sha256"] = sha(dst / "requested-tracks.jsonl")
            put(dst / "config.json", cfg)
            try:
                check(dst)
            except ValueError:
                negatives += 1
            else:
                raise AssertionError("Rehashed grade mutation accepted")
    result = {"format": "c104496-request-proof-v1", "positive_count": positives,
              "negative_count": negatives, "source_bound": True, "original_native_observed": False}
    put(HERE / "request-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
