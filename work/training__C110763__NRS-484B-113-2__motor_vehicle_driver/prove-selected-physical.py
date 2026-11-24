"""Exercise reverse completion on source-hashed synthetic Native-shaped rows."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, kind):
    if case not in ("condition_a", "condition_b"):
        raise ValueError("Unknown exact case")
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"].endswith("__probe_1" if case == "condition_a" else "__probe_2"))
    base = {"case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
            "accepted": False, "legal_verdict_claimed": False, "original_native_motion_verified": False}
    if kind == "lifecycle":
        runner = HERE / "native" / "runner.py"
        code = runner.read_text()
        for token in ("finally:", "capture.close", "encoder.stdin.close", "restore(client,saved)"):
            if token not in code:
                raise ValueError("Native runner lacks cleanup source: " + token)
        return {**base, "events": EVENTS, "exit_code": 0, "runner_sha256": sha(runner),
                "scope": "synthetic ownership-order contract; not an executed CARLA capture"}
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown outcome fixture")
    generator = HERE / ("current-600-primary-generator.json" if case == "condition_a" else "current-600-controlled-generator.json")
    recipe = HERE / ("current-600-primary-recipe.json" if case == "condition_a" else "current-600-controlled-recipe.json")
    source = json.loads(generator.read_text())
    binding = json.loads(recipe.read_text())
    if binding["generator"]["sha256"] != sha(generator):
        raise ValueError("Synthetic source generator differs from current recipe")
    raw = source["files"]["native_samples.jsonl"]
    rows = [json.loads(line) for line in raw.splitlines()]
    if kind == "missing_evidence":
        rows = []
    elif kind == "incomplete_motion":
        rows = rows[:100]
    full = len(rows) == 600
    joined = bool(rows) and all(row["native_frame"] == 100 + i and row["video_frame"] == i and
                                abs(row["time_s"] - (i + 1) / 20) < 1e-6 for i, row in enumerate(rows))
    surveyed = bool(rows) and all(row.get("native_intersection_survey") is True and
                                    len(row.get("native_body_xy_m", [])) == 4 for row in rows)
    reverse = sum(row["signed_forward_velocity_m_s"] < -0.05 for row in rows)
    displacement = (rows[0]["native_center_xy_m"][0] - rows[-1]["native_center_xy_m"][0]) if rows else 0.0
    stopped = bool(rows) and abs(rows[-1]["signed_forward_velocity_m_s"]) <= 0.05
    threshold = 1.5 if case == "condition_a" else 3.5
    complete = full and joined and surveyed and reverse >= 20 and displacement >= threshold and stopped
    status = "unverified" if not rows else "met" if complete else "not_met"
    return {**base, "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_checks": {"maneuver": {"status": status,
                "method": "600 joined Native-shaped center/body/velocity samples, reverse displacement and final stop",
                "sources": [generator.name] if rows else ["missing diagnostic Native samples"]}},
            "maneuver_completed": complete,
            "realized_observables": ({"sample_count": len(rows), "reverse_frames": reverse,
                                      "reverse_displacement_m": displacement,
                                      "final_stop": stopped, "joined": joined,
                                      "surveyed_body": surveyed} if rows else {}),
            "retained_source_sha256": {"native_samples.jsonl": hashlib.sha256(raw.encode()).hexdigest()} if rows else {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case": args.case, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status", "lifecycle"),
                      "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
