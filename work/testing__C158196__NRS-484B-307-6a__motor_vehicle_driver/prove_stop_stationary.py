"""Check the selected diagnostic stop source reaches a stationary end."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(negative_motion=False):
    manifest = HERE / "execution-manifest.json"
    case_id = HERE.name + "__stops_on_yellow"
    entry = next(item for item in json.loads(manifest.read_text())["cases"]
                 if item["case_id"] == case_id)
    recipe = json.loads((REPO / entry["fixture_recipe"]).read_text())
    source = HERE / "yellow-stop-diagnostic-sources.json"
    if recipe["generator"]["source"] != str(source.relative_to(REPO)) or recipe["generator"]["sha256"] != sha(source):
        raise ValueError("Selected stop fixture source changed")
    rows = [json.loads(line) for line in json.loads(source.read_text())["files"]["signal_vehicle_history.jsonl"].splitlines()]
    if len(rows) != 900 or [row["frame"] for row in rows] != list(range(900)):
        raise ValueError("Stop source lacks continuous original frames")
    if negative_motion:
        rows[-1]["ego_speed_mps"] = 1.0
    tail = rows[-100:]
    first_body = tail[0]["ego_body_vertices_xy_m"]
    if any(row["ego_speed_mps"] != 0.0 or row["ego_body_vertices_xy_m"] != first_body for row in tail):
        raise ValueError("Stationary-end source motion changed")
    return {"format": "worker-stop-stationary-source-cpu-proof", "case_id": case_id,
            "passed": True, "stationary_original_frames": [800, 899],
            "zero_speed_samples": len(tail), "unchanged_body_samples": len(tail),
            "source_sha256": sha(source), "manifest_sha256": sha(manifest),
            "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
            "scope": "Source-shaped diagnostic only; Native stop and feasibility unverified"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-motion", action="store_true")
    args = parser.parse_args()
    print(json.dumps(main(args.negative_motion), sort_keys=True))
