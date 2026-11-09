"""Eight exact request positives and rehashed material negatives."""
import copy
import json
import tempfile
from pathlib import Path
from build import CASES, HERE, POLICIES, build, put, sha
from check import check


def prove():
    entries = build()["entries"]
    positives = negatives = 0
    for entry in entries:
        suffix = entry["case_id"].split("__")[-1]
        candidate = entry["candidate_id"]
        bundle = HERE / "drafts" / suffix / candidate
        check(bundle)
        positives += 1
        for kind in ("road", "track", "law", "status"):
            with tempfile.TemporaryDirectory() as temp:
                copied = Path(temp)
                for path in bundle.iterdir():
                    (copied / path.name).write_bytes(path.read_bytes())
                cfg = json.loads((copied / "config.json").read_text())
                if kind == "road":
                    path = copied / "crossroads.xodr"
                    path.write_text(path.read_text().replace('y="-20.0"', 'y="-19.0"'))
                    if path.read_bytes() == (bundle / "crossroads.xodr").read_bytes():
                        path.write_text(path.read_text().replace('y="-20"', 'y="-19"'))
                    cfg["road_sha256"] = sha(path)
                elif kind == "track":
                    path = copied / "requested-tracks.jsonl"
                    lines = path.read_text().splitlines()
                    row = json.loads(lines[125]); row["requested_ego_xyz_m"][0] += .5
                    lines[125] = json.dumps(row, sort_keys=True)
                    path.write_text("\n".join(lines) + "\n")
                    cfg["tracks_sha256"] = sha(path)
                elif kind == "law":
                    cfg["source_text"] += " altered"
                else:
                    cfg["status"] = "runnable"
                put(copied / "config.json", cfg)
                try:
                    check(copied)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Rehashed negative accepted: " + kind)
    result = {"format": "c111294-2502-request-proof-v1", "positive_count": positives,
              "negative_count": negatives, "original_native_observed": False,
              "delivery_ready": False}
    put(HERE / "request-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
