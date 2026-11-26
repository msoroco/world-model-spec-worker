"""Build a common source-triggered approach-spawn fallback for each exact case."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    for name in ("diagnostic-execution-manifest.json", "execution-manifest.json"):
        manifest = ROOT / name
        data = json.loads(manifest.read_text())
        for entry in data["cases"]:
            primary = json.loads((ROOT / entry["construction"]).read_text())
            fallback = json.loads(json.dumps(primary))
            fallback["candidate_id"] = "fallback1"
            config = next(item for item in fallback["files"] if item["path"] == "config.json")
            value = json.loads(config["content"])
            value["scenario_parameters"]["entrant_start_m"] = -5
            config["content"] = json.dumps(value, indent=2, sort_keys=True) + "\n"
            suffix = entry["case_id"].removeprefix(ROOT.name + "__")
            path = ROOT / "cases" / suffix / "fallback1" / "construction.json"
            dump(path, fallback)
            entry["candidate_risk"]["reason"] = (
                "The reviewed entrant start may be occupied or too close to zone access; "
                "original Native spawn and approach readback must decide selection.")
            entry["candidates"] = [{"id": "fallback1",
                "construction": str(path.relative_to(ROOT)),
                "construction_sha256": sha(path),
                "trigger": {"source": "original Native entrant spawn and approach readback",
                            "metric": "spawn clearance and approach route feasibility",
                            "failure_condition": "primary entrant spawn collides or route cannot reach zone access"},
                "changed_knobs": ["entrant_start_m: 0 to -5 metres before source-reviewed zone start"]}]
        dump(manifest, data)
    print("built three common fallback constructions")


if __name__ == "__main__":
    main()
