"""Build three risk-triggered alternatives for the first exact turn case."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPECS = (
    ("fallback1", "spawn_height_offset_m", .7,
     "Original Native ego spawn readback", "spawn success at surveyed approach waypoint",
     "Primary 0.5 m clearance intersects the road or actor spawn fails"),
    ("fallback2", "target_speed_mps", 3.5,
     "Original Native body progress and target reach", "turn target reached inside 160-frame budget",
     "Primary 4 m/s feedback overshoots the sourced target or cannot stay on connected route"),
    ("fallback3", "overview_mount_z_m", 9.,
     "Original overview camera decoded frames", "full-body and both surveyed road legs visible",
     "Primary 8 m overview mount clips the body or governing road geometry"),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    primary = json.loads((ROOT / "construction.json").read_text())
    manifest_path = ROOT / "provisional-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["cases"][0]
    entry["construction_sha256"] = digest(ROOT / "construction.json")
    entry["candidate_risk"] = {"status": "physical", "reason":
        "Surveyed Native road spawn, turn target tracking and original camera coverage need physical verification"}
    candidates = []
    for ident, knob, value, source, metric, failure in SPECS:
        proposal = deepcopy(primary)
        config = next(item for item in proposal["files"] if item["path"] == "config.json")
        settings = json.loads(config["content"])
        settings["engineering"][knob] = value
        config["content"] = json.dumps(settings, indent=2) + "\n"
        name = ident + "-construction.json"
        target = ROOT / name
        target.write_text(json.dumps(proposal, indent=2) + "\n")
        candidates.append({"id": ident, "construction": name,
                           "construction_sha256": digest(target),
                           "changed_knobs": [f"{knob}={value}"],
                           "trigger": {"source": source, "metric": metric,
                                       "failure_condition": failure}})
    entry["candidates"] = candidates
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return [item["construction_sha256"] for item in candidates]


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
