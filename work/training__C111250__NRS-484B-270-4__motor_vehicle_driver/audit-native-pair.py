"""Independent source-row comparison of the two synthetic Native-shaped cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def extent_overlap(body, bounds):
    xs = [point[0] for point in body]; ys = [point[1] for point in body]
    return max(xs) > bounds[0] and min(xs) < bounds[1] and \
           max(ys) > bounds[2] and min(ys) < bounds[3]


def audit_sources(primary, contrast):
    names = ("facility-context.json", "subsection3-context.json", "road.xodr",
             "video_frames.jsonl")
    for name in names:
        if sha(primary / name) != sha(contrast / name):
            raise ValueError("Comparison fixed source differs: " + name)
    context = json.loads((primary / "subsection3-context.json").read_text())
    if context.get("source_kind") != "synthetic_cpu_diagnostic" or \
       context.get("exception_legally_resolved") is not False:
        raise ValueError("Comparison context provenance differs")
    p, c = rows(primary / "body-history.jsonl"), rows(contrast / "body-history.jsonl")
    if len(p) != 600 or len(c) != 600:
        raise ValueError("Comparison source count differs")
    bounds = (3.5, 5.5, -7.0, 7.0)
    p_inside = [i for i, r in enumerate(p) if extent_overlap(r["body_xy_m"], bounds)]
    c_inside = [i for i, r in enumerate(c) if extent_overlap(r["body_xy_m"], bounds)]
    if not 0 < len(p_inside) < len(c_inside):
        raise ValueError("Brief crossing and sustained occupancy are not measured")
    if any(extent_overlap(p[i]["body_xy_m"], bounds) for i in range(200)) or \
       any(extent_overlap(p[i]["body_xy_m"], bounds) for i in range(500, 600)):
        raise ValueError("Brief crossing did not begin/end outside facility")
    for i, (a, b) in enumerate(zip(p, c)):
        if a["native_frame"] != b["native_frame"] or a["time_s"] != b["time_s"] or \
           a["speed_mps"] != b["speed_mps"]:
            raise ValueError("Comparison frame/time/speed differs at " + str(i))
    return {"passed": True, "format": "c111250-native-pair-audit-v1",
            "source_kind": "synthetic_cpu_diagnostic",
            "primary_crossing_overlap_frames": len(p_inside),
            "contrast_sustained_overlap_frames": len(c_inside),
            "first_crossing_frame": p_inside[0],
            "last_crossing_frame": p_inside[-1],
            "fixed_source_sha256": {name: sha(primary / name) for name in names},
            "body_source_sha256": {"controlled_1": sha(primary / "body-history.jsonl"),
                                   "controlled_2": sha(contrast / "body-history.jsonl")},
            "physical_or_legal_acceptance": False}


def main():
    p = HERE / "native-diagnostic-controlled_1-sources"
    c = HERE / "native-diagnostic-controlled_2-sources"
    proof = audit_sources(p, c)
    path = HERE / "native-pair-audit.json"
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": True, "sha256": sha(path),
                      "crossing": proof["primary_crossing_overlap_frames"],
                      "sustained": proof["contrast_sustained_overlap_frames"]}))


if __name__ == "__main__":
    main()
