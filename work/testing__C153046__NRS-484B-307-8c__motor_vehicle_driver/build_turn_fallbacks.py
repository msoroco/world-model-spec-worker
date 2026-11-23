"""Author one distinct steering fallback for a measurable turn-completion risk."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        construction = json.loads((ROOT / entry["construction"]).read_text())
        alternate = json.loads(json.dumps(construction))
        controller = next(item for item in alternate["files"] if item["path"] == "red_left_turn_controller.py")
        before = '"turning": {"throttle": 0.15, "brake": 0.0, "steer": -0.35}'
        after = '"turning": {"throttle": 0.10, "brake": 0.0, "steer": -0.48}'
        if controller["content"].count(before) != 1:
            raise ValueError("primary turn controls changed")
        controller["content"] = controller["content"].replace(before, after)
        alternate["status"] = "partial: distinct steering fallback; original turn and legal yielding unverified"
        path = ROOT / "constructions" / (suffix + "-fallback1.json")
        path.write_text(json.dumps(alternate, indent=2) + "\n")
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "The primary fixed -0.35 steering request can miss the authored 90-degree left-turn event on an unreviewed site; measure original heading and route progress before selecting the fallback.",
        }
        entry["candidates"] = [{
            "id": "fallback1", "construction": str(path.relative_to(ROOT)),
            "construction_sha256": sha(path),
            "trigger": {"source": "trace.jsonl original Native frame and heading samples",
                        "metric": "net heading change and progress at the planned 30 s endpoint",
                        "failure_condition": "primary original trace does not meet the authored 90 +/- 20 degree turn event with at least 1 m of progress"},
            "changed_knobs": ["turning throttle 0.15 to 0.10", "turning steer -0.35 to -0.48"],
            "proof_status": "exact_offline_and_compatibility_pending",
        }]
        print("authored distinct steering fallback", suffix)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
