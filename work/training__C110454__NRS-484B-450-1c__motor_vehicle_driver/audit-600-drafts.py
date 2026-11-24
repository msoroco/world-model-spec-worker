"""Independently audit the two 600-frame parking traces and eight exact drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-execution-manifest-600.json"
SAVED = HERE / "draft-saved-600-proof.json"
OFFLINE = HERE / "draft-offline-600-proof.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_overlap(vertices):
    xs = [point[0] for point in vertices]
    ys = [point[1] for point in vertices]
    return max(0, min(max(xs), 7) - max(min(xs), -7)) * \
           max(0, min(max(ys), 7) - max(min(ys), -7))


def main():
    manifest = json.loads(MANIFEST.read_text())
    saved = json.loads(SAVED.read_text())
    offline = json.loads(OFFLINE.read_text())
    if not saved["passed"] or not offline["passed"] or len(saved["cases"]) != 8 or \
            len(offline["results"]) != 8 or len(manifest["cases"]) != 2:
        raise ValueError("Eight exact long-duration proofs required")
    if saved["manifest_sha256"] != sha(MANIFEST) or offline["manifest_sha256"] != sha(MANIFEST):
        raise ValueError("Long-duration manifest binding differs")
    saved_index = {(item["case"], item["candidate"]): item for item in saved["cases"]}
    offline_index = {(item["case"], item["candidate"]): item for item in offline["results"]}
    results = {}
    primaries = {}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        refs = [entry] + entry["candidates"]
        if {ref["id"] for ref in refs} != {"primary", "fallback1", "fallback2", "fallback3"}:
            raise ValueError("Candidate inventory differs")
        for ref in refs:
            candidate = ref["id"]
            construction = HERE / ref["construction"]
            if sha(construction) != ref["construction_sha256"]:
                raise ValueError("Exact construction source changed")
            value = json.loads(construction.read_text())
            config = json.loads(next(file["content"] for file in value["files"]
                                     if file["path"] == "config.json"))
            if config["case_id"] != entry["case_id"] or config["duration_s"] != 30 or \
                    config["rate_hz"] != 20 or config["engineering_knobs"]["duration_s"] != 30:
                raise ValueError("Exact 30-second construction differs")
            if candidate == "primary":
                primaries[suffix] = config
            else:
                base = primaries[suffix]["engineering_knobs"]
                changes = {key for key in base if config["engineering_knobs"][key] != base[key]}
                if changes != set(ref["changed_knobs"]) or len(changes) != 1:
                    raise ValueError("Fallback changes more than its one engineering knob")
            saved_row = saved_index[suffix, candidate]
            offline_row = offline_index[suffix, candidate]
            if offline_row["construction_sha256"] != ref["construction_sha256"] or \
                    offline_row["planned_frames"] != 600 or saved_row["parked_frames"] != 360:
                raise ValueError("Offline or source-bound receipt differs")
            source = ROOT / saved_row["source_path"]
            if ROOT.resolve() not in source.resolve().parents or sha(source) != saved_row["source_sha256"]:
                raise ValueError("Source trace hash or routing differs")
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            if len(rows) != 600:
                raise ValueError("Original trace length differs")
            overlaps = []
            for i, row in enumerate(rows):
                if row["video_frame"] != i or row["native_frame"] != 1000 + i or \
                        abs(row["time_s"] - i / 20) > 1e-6:
                    raise ValueError("Independent 20 Hz frame join differs")
                if any(row["exceptions"].values()) or any(row["exception_source"].values()):
                    raise ValueError("Exception control differs")
                if row["speed_m_s"] <= .05:
                    overlaps.append(body_overlap(row["body_xy_m"]))
            if len(overlaps) != 360:
                raise ValueError("Independent sustained parking count differs")
            measured = round(max(overlaps), 5)
            if measured != saved_row["overlap_m2"]:
                raise ValueError("Saved full-body overlap differs from independent geometry")
            if (suffix == "probe_a" and measured != 0) or \
                    (suffix == "probe_b" and measured <= 10):
                raise ValueError("Controlled inside/outside contrast differs")
            results[suffix + "/" + candidate] = {"overlap_m2": measured,
                                                  "source_sha256": sha(source),
                                                  "construction_sha256": sha(construction)}
    a, b = primaries["probe_a"], primaries["probe_b"]
    for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz", "required_atoms",
                "source_packets", "mandatory_channels", "recording_description", "cameras",
                "engineering_knobs"):
        if a[key] != b[key]:
            raise ValueError("Comparison fixed condition differs: " + key)
    law = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())["law"]["text"]
    if "Within an intersection." not in law or "except when necessary to avoid conflict" not in law:
        raise ValueError("Current frozen law text differs")
    proof = {"format": "c110454-independent-600-draft-audit-v1", "passed": True,
             "scope": "synthetic CPU only; exact current compatibility and physical claims absent",
             "manifest_sha256": sha(MANIFEST), "saved_proof_sha256": sha(SAVED),
             "offline_proof_sha256": sha(OFFLINE), "law_source_sha256": sha(ROOT / "inputs" / HERE.name / "assignment.json"),
             "comparison_variable": "intersection_parking_footprint",
             "fixed_conditions_checked": True, "cases": results}
    target = HERE / "draft-600-audit.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(results), "sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
