"""Independent 600-frame speed-profile and controlled-condition audit."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-execution-manifest-600.json"
PROOF = HERE / "draft-600-source-proof.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    proof = json.loads(PROOF.read_text())
    if proof["manifest_sha256"] != sha(MANIFEST) or len(proof["results"]) != 8:
        raise ValueError("Exact 600-frame source proof differs")
    indexed = {(item["case"], item["candidate"]): item for item in proof["results"]}
    primaries = {}
    traces = {}
    summary = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for ref in [entry] + entry["candidates"]:
            candidate = ref["id"]
            construction = HERE / ref["construction"]
            if sha(construction) != ref["construction_sha256"]:
                raise ValueError("Construction bytes differ")
            bundle = json.loads(construction.read_text())
            config = json.loads(next(file["content"] for file in bundle["files"]
                                     if file["path"] == "config.json"))
            if (config["case_id"] != entry["case_id"] or config["duration_s"] != 30 or
                    config["rate_hz"] != 20 or config["knobs"]["duration_s"] != 30):
                raise ValueError("Long-duration exact contract differs")
            if candidate == "primary":
                primaries[suffix] = config
            else:
                knobs = primaries[suffix]["knobs"]
                changes = {key for key in knobs if config["knobs"][key] != knobs[key]}
                if changes != set(ref["changed_knobs"]):
                    raise ValueError("Fallback engineering knob set differs")
            row = indexed[suffix, candidate]
            source = ROOT / row["source_path"]
            if ROOT.resolve() not in source.resolve().parents or sha(source) != row["source_sha256"]:
                raise ValueError("Saved source hash differs")
            values = [json.loads(line) for line in source.read_text().splitlines()]
            if len(values) != 600:
                raise ValueError("Native source length differs")
            for i, sample in enumerate(values):
                if sample["frame"] != i or abs(sample["t_s"] - i / 20) > 1e-6:
                    raise ValueError("Independent 20 Hz join differs")
                if sample["ego_role"] != "motor_vehicle_driver" or \
                        sample["other_role"] != "motor_vehicle_driver" or \
                        sample["ego_actor_id"] == sample["other_actor_id"]:
                    raise ValueError("Actor identity differs")
                if i and math.dist(values[i-1]["ego_position_m"], sample["ego_position_m"]) > 2:
                    raise ValueError("Ego movement discontinuity")
            direction = 1 if values[-1]["ego_position_m"][1] > values[0]["ego_position_m"][1] else -1
            before = [math.dist(sample["ego_velocity_mps"], [0, 0, 0]) * 2.2369362920544
                      for sample in values if -60 <= direction * sample["ego_position_m"][1] < -50]
            preentry = [math.dist(sample["ego_velocity_mps"], [0, 0, 0]) * 2.2369362920544
                        for sample in values if -20 <= direction * sample["ego_position_m"][1] < -7]
            crossing = [math.dist(sample["ego_velocity_mps"], [0, 0, 0]) * 2.2369362920544
                        for sample in values if -7 <= direction * sample["ego_position_m"][1] <= 7]
            if min(map(len, (before, preentry, crossing))) < 3:
                raise ValueError("Approach or crossing window absent")
            decrease = sum(before)/len(before) - sum(preentry)/len(preentry)
            if abs(decrease - row["decrease_mph"]) > .002:
                raise ValueError("Independent speed decrease differs")
            if (suffix == "probe_a" and decrease < 3) or (suffix == "probe_b" and decrease >= 1):
                raise ValueError("Controlled speed relation differs")
            if candidate == "primary":
                traces[suffix] = values
            summary[suffix + "/" + candidate] = {"decrease_mph": round(decrease, 3),
                                                   "source_sha256": sha(source),
                                                   "construction_sha256": sha(construction)}
    a, b = primaries["probe_a"], primaries["probe_b"]
    for key in ("cell_id", "law_id", "actor", "rate_hz", "duration_s", "required_atoms",
                "source_packets", "mandatory_channels", "cameras", "recording_description"):
        if a[key] != b[key]:
            raise ValueError("Controlled package condition differs: " + key)
    if any(x["other_position_m"] != y["other_position_m"] for x, y in
           zip(traces["probe_a"], traces["probe_b"])):
        raise ValueError("Cross-traffic trajectory differs between controls")
    if any(traces["probe_a"][0][key] != traces["probe_b"][0][key] for key in
           ("ego_position_m", "ego_velocity_mps", "other_position_m")):
        raise ValueError("Initial controlled state differs")
    frozen = ROOT / "inputs" / HERE.name / "assignment.json"
    law = json.loads(frozen.read_text())["law"]["text"]
    if "decrease speed when approaching and crossing an intersection" not in law:
        raise ValueError("Frozen statutory text differs")
    audit = {"format": "c111294-independent-600-source-audit-v1", "passed": True,
             "scope": "synthetic CPU only; no physical hazard or legal judgment",
             "manifest_sha256": sha(MANIFEST), "proof_sha256": sha(PROOF),
             "frozen_source_sha256": sha(frozen), "fixed_conditions_checked": True,
             "comparison_variable": "hazard_approach_speed_profile", "cases": summary}
    target = HERE / "draft-600-source-audit.json"
    target.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(summary), "sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
