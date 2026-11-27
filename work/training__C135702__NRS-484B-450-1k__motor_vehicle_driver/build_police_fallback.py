"""Risk-based controller fallback for each source-gated police case."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    manifest_path = ROOT / "police-pair-draft-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        primary = json.loads((ROOT / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(primary))
        config_file = next(item for item in fallback["files"] if item["path"] == "config.json")
        config = json.loads(config_file["content"])
        config["passing_throttle"] = .35
        config["brake_station_x_m"] = -15
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        path = ROOT / "cases" / suffix / "fallback1-construction.json"
        path.write_text(json.dumps(fallback, indent=2) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry["candidate_risk"] = {"status": "physical",
                                   "reason": "Original passing vehicle may not sustain a stable pre-obstruction halt with the primary braking station."}
        entry["candidates"] = [{"id": "fallback1",
                                "construction": str(path.relative_to(ROOT)),
                                "construction_sha256": digest,
                                "trigger": {"source": "original native_samples.jsonl",
                                            "metric": "minimum_passing_speed_m_s and passing_halt_frames",
                                            "failure_condition": "fewer than 20 source halt frames before the physical obstruction"},
                                "changed_knobs": ["passing_throttle .25 to .35", "brake_station_x_m -11 to -15"]}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build()
