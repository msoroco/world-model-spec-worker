"""Independent source audit of the two exact right-only lane diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(reference, contrast):
    a, b = (Path(reference), Path(contrast))
    if sha(a / "road.xodr") != sha(b / "road.xodr"):
        raise ValueError("Road geometry changed between selected cases")
    geometry = [json.loads((root / "road_geometry.json").read_text()) for root in (a, b)]
    if geometry[0] != geometry[1] or geometry[0]["right_only_lane_design_native_verified"]:
        raise ValueError("Surveyed geometry drift or synthetic Native designation claim")
    samples = [rows(root / "native_samples.jsonl") for root in (a, b)]
    maps = [rows(root / "video_frames.jsonl") for root in (a, b)]
    if len(samples[0]) != len(samples[1]) or len(samples[0]) != 480 or maps[0] != maps[1]:
        raise ValueError("Frame count or original video/time join changed")
    observed = []
    for left, right in zip(*samples):
        for key in ("native_frame", "time_s", "native_road_id", "native_forward_xy"):
            if left[key] != right[key]:
                raise ValueError("Fixed Native motion field changed: " + key)
        if left["native_center_xy_m"][0] != right["native_center_xy_m"][0]:
            raise ValueError("Fixed longitudinal position changed")
        if abs(right["native_center_xy_m"][1] - left["native_center_xy_m"][1] - 3.5) > 1e-8:
            raise ValueError("Unexpected lateral placement change")
        if (left["native_lane_id"], right["native_lane_id"]) != (-1, -2):
            raise ValueError("Requested approach lane contrast changed")
        for lp, rp in zip(left["native_body_xy_m"], right["native_body_xy_m"]):
            if abs(lp[0] - rp[0]) > 1e-8 or abs(rp[1] - lp[1] - 3.5) > 1e-8:
                raise ValueError("Full Native body contrast changed")
        observed.append(left["native_road_id"] == 14)
    if not any(observed) or not all(row["native_road_id"] == 2 for row in samples[0][-40:]):
        raise ValueError("Complete source-shaped crossing not sampled")
    return {"format": "c382389-selected-source-comparison-v1", "passed": True,
            "frames_per_case": 480, "intersection_sample_frames": sum(observed),
            "reference_lane_id": -1, "contrast_lane_id": -2,
            "fixed": ["authored road", "surveyed geometry", "longitudinal motion", "frame/time map",
                      "Native forward and road identity", "full-body footprint shape"],
            "deliberate_difference": "3.5 m lateral placement and approach lane -1 versus -2",
            "sources": {label: {name: sha(root / name) for name in
                ("road.xodr", "road_geometry.json", "native_samples.jsonl", "video_frames.jsonl")}
                for label, root in (("reference", a), ("contrast", b))},
            "native_executed": False, "legal_verdict_claimed": False}


def main():
    import copy
    base = HERE / "current-fixture"
    receipt = audit(base / "reference", base / "contrast")
    original = rows(base / "contrast/native_samples.jsonl")
    negatives = []
    for key, mutation in (("longitudinal", lambda row: row["native_center_xy_m"].__setitem__(0, 999)),
                          ("lane", lambda row: row.__setitem__("native_lane_id", -1)),
                          ("frame", lambda row: row.__setitem__("native_frame", 999))):
        changed = copy.deepcopy(original)
        mutation(changed[100])
        try:
            audit_rows(rows(base / "reference/native_samples.jsonl"), changed)
        except ValueError as error:
            negatives.append({"mutation": key, "rejection": str(error)})
        else:
            raise ValueError("Negative source mutation survived: " + key)
    receipt["negative_mutations"] = negatives
    path = HERE / "selected-comparison-proof.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "negative_mutations": len(negatives)}))


def audit_rows(a, b):
    for left, right in zip(a, b):
        if left["native_frame"] != right["native_frame"]:
            raise ValueError("Fixed Native frame changed")
        if left["native_center_xy_m"][0] != right["native_center_xy_m"][0]:
            raise ValueError("Fixed longitudinal position changed")
        if (left["native_lane_id"], right["native_lane_id"]) != (-1, -2):
            raise ValueError("Requested approach lane contrast changed")


if __name__ == "__main__":
    main()
