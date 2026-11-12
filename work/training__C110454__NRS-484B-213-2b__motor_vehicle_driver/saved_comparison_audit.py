"""Independent C110454 saved-source controlled comparisons.

The source comparison is useful CPU preparation, not physical or legal review.
Both diagnostic and original modes return no delivery acceptance.
"""
import json
from pathlib import Path

from camera_lifecycle_audit import audit as camera_audit
from source_join_audit import read, require, rows, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAIRS = {
    "main": ("reference", "contrast", "draft-execution-manifest.json",
             "c110454-update015-intersection-matrix-v1", "intersection"),
    "rail": ("rail_reference", "rail_contrast", "draft-statutory-execution-manifest.json",
             "c110454-update015-statutory-matrix-v2", "statutory"),
    "oneway": ("oneway_absent", "oneway_present", "draft-statutory-execution-manifest.json",
               "c110454-update015-statutory-matrix-v2", "statutory"),
    "traversal": ("traversal_reference", "traversal_contrast", "draft-traversal-execution-manifest.json",
                  "c110454-update015-traversal-matrix-v1", "traversal"),
}
IDENTITY = {"case_id", "selected_case_id", "supported_case_ids", "case", "case_suffix"}


def normalize_config(config):
    return {key: value for key, value in config.items() if key not in IDENTITY}


def compare_sources(kind, left, right):
    """Check held conditions and one declared variable using retained sources."""
    a, b = left["config"], right["config"]
    require(normalize_config(a) == normalize_config(b),
            "Held exact capture or controller config differs")
    ra, rb = left["road"], right["road"]
    sa, sb = left["samples"], right["samples"]
    ea, eb = left["evidence"], right["evidence"]
    fa, fb = left["frames"], right["frames"]
    require(len(sa) == len(sb) == len(ea) == len(eb) == len(fa) == len(fb) == 480,
            "Incomplete paired original interval")
    require(all(x.get("native_frame") == y.get("native_frame") and
                x.get("time_s") == y.get("time_s") and
                fx == fy and
                ex.get("world", {}).get("weather") == ey.get("world", {}).get("weather")
                for x, y, fx, fy, ex, ey in zip(sa, sb, fa, fb, ea, eb)),
            "Held frame/time map or weather differs")
    require(all(x["native_center_xy_m"][0] == y["native_center_xy_m"][0]
                for x, y in zip(sa, sb)), "Held longitudinal route differs")
    lateral = sum(x["native_center_xy_m"][1] != y["native_center_xy_m"][1]
                  for x, y in zip(sa, sb))
    speed = sum(x["speed_m_s"] != y["speed_m_s"] for x, y in zip(sa, sb))
    if kind == "oneway":
        changes = {key for key in ra if ra[key] != rb.get(key)}
        require(changes == {"road_directions_native", "one_way_native_readback"} and
                ra["one_way_native_readback"] is False and
                rb["one_way_native_readback"] is True and
                left["road_xodr_sha256"] != right["road_xodr_sha256"] and
                lateral == speed == 0,
                "One-way designation contrast or fixed route differs")
        allowed_context = {"case_suffix", "one_way", "road_directions_native"}
    else:
        require(ra == rb and
                left["road_xodr_sha256"] == right["road_xodr_sha256"] and
                lateral > 0, "Held road or lateral contrast differs")
        require(speed > 0 if kind == "traversal" else speed == 0,
                "Paired speed consequence or fixed schedule differs")
        if kind == "traversal":
            require(sa[-1]["native_center_xy_m"] == sb[-1]["native_center_xy_m"],
                    "Held traversal parking endpoint differs")
        allowed_context = {"case_suffix"}
    if kind in ("rail", "oneway"):
        ca, cb = left["statutory"], right["statutory"]
        require({key for key in ca if ca[key] != cb.get(key)} <= allowed_context and
                ca.get("native_map_sha256") == cb.get("native_map_sha256"),
                "Held statutory context differs")
        if kind == "rail":
            require(ca.get("railroad_crossing") is True and
                    ca.get("railroad_crossing_object_id") ==
                    cb.get("railroad_crossing_object_id") == "701",
                    "Railroad object source differs")
        else:
            require(ca.get("one_way") is False and cb.get("one_way") is True,
                    "One-way statutory context contrast absent")
    return {"lateral_changed_frames": lateral, "speed_changed_frames": speed,
            "held_frame_time_weather": True, "held_capture_config": True,
            "held_longitudinal_route": True}


def load_side(group, suffix, manifest, root_name, *, diagnostic):
    case = HERE.name + "__" + suffix
    entry = next(item for item in manifest["cases"] if item["case_id"] == case)
    construction_sha = entry["construction_sha256"]
    require(sha(HERE / entry["construction"]) == construction_sha,
            "Current construction hash differs")
    attempt = ROOT / ".runtime-work" / root_name / suffix / "primary" / "compatibility"
    processing = HERE / f"update015-{group}-proofs" / suffix / "primary" / "process-saved.json"
    camera = camera_audit(attempt, processing, case, "primary", construction_sha,
                          diagnostic=diagnostic)
    saved = read(processing)
    paths = ("road_geometry.json", "road.xodr") + (("statutory_context.json",)
              if group == "statutory" else ())
    require(all((attempt / name).is_file() and
                saved.get("original_source_hashes", {}).get(name) == sha(attempt / name)
                for name in paths), "Saved comparison source hash differs")
    result = {"config": read(attempt / "config.json"),
              "road": read(attempt / "road_geometry.json"),
              "samples": rows(attempt / "native_samples.jsonl"),
              "evidence": rows(attempt / "capture/evidence.jsonl"),
              "frames": rows(attempt / "video_frames.jsonl"),
              "road_xodr_sha256": sha(attempt / "road.xodr"),
              "joined_source_hashes": camera["source_join_sha256"],
              "camera_source_sha256": {name: item["sha256"] for name, item in
                                       camera["camera_sources"].items()},
              "source_sha256": {name: sha(attempt / name) for name in paths},
              "saved_processing_sha256": sha(processing),
              "construction_sha256": construction_sha}
    if group == "statutory":
        result["statutory"] = read(attempt / "statutory_context.json")
    return result


def audit_pair(kind, *, diagnostic=False):
    require(kind in PAIRS, "Unknown comparison")
    a, b, manifest_name, root_name, group = PAIRS[kind]
    manifest = read(HERE / manifest_name)
    plan = read(HERE / "case-plan.json")
    comparison_id = HERE.name + "__comparison_" + kind
    comparison = next(row for row in plan["comparisons"]
                      if row["comparison_id"] == comparison_id)
    require(comparison["case_ids"] == [HERE.name + "__" + a, HERE.name + "__" + b],
            "Declared exact comparison pair differs")
    left = load_side(group, a, manifest, root_name, diagnostic=diagnostic)
    right = load_side(group, b, manifest, root_name, diagnostic=diagnostic)
    observed = compare_sources(kind, left, right)
    return {"format": "c110454-saved-source-comparison-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "declared_differences": comparison["deliberate_differences"],
            "source_bindings": [{key: side[key] for key in
                                 ("source_sha256", "joined_source_hashes",
                                  "camera_source_sha256", "saved_processing_sha256",
                                  "construction_sha256")} for side in (left, right)],
            **observed, "source_comparison_passed": True,
            "diagnostic_fixture": diagnostic, "passed": False,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=PAIRS)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_pair(args.kind, diagnostic=args.diagnostic), indent=2))
