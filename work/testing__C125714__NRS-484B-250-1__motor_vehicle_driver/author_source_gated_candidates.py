"""Build exact delivery bundles whose Native launch requires external site review.

This author does not create reviewed source facts or mark cases ready. It turns the
existing seven engineering scenes into CPU-checkable constructions and preserves
the original diagnostic bundles for independent software proofs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SUFFIXES = ("precedence", "advance", "other_later", "opposite_straight",
            "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_bundle(suffix, candidate):
    base = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    path = base / ("fallback1-construction.json" if candidate == "fallback1" else "construction.json")
    return read(path)


def build(suffix, candidate):
    original = source_bundle(suffix, candidate)
    if original.get("diagnostic_only") is not True or original["case_id"] != ROOT.name + "__" + suffix:
        raise ValueError("seven exact diagnostic engineering sources required")
    bundle = deepcopy(original)
    files = {item["path"]: item for item in bundle["files"]}
    scene = json.loads(files["scene.json"]["content"])
    config = json.loads(files["config.json"]["content"])
    scene["diagnostic_only"] = False
    scene.pop("reviewed_context_source", None)
    scene.pop("reviewed_context_sha256", None)
    config["cameras"] = [
        {"name": name, "width": width, "height": height,
         "pose_strategy": "source-reviewed crossing and vehicle-relative Native pose",
         "fov_deg": 90}
        for name, width, height in CAMERAS]
    files["scene.json"]["content"] = json.dumps(scene, indent=2, ensure_ascii=False) + "\n"
    files["config.json"]["content"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    files["runner.py"]["content"] = (ROOT / "source_gated_runner.py").read_text(encoding="utf-8")
    bundle["files"] = [item for item in bundle["files"] if item["path"] not in
                       ("diagnostic-context.json", "tests/test_diagnostic_bundle.py")]
    bundle["files"].append({"path": "tests/test_selected_bundle.py",
        "content": (ROOT / "tests/test_selected_bundle.py").read_text(encoding="utf-8")})
    bundle["diagnostic_only"] = False
    bundle["mechanisms"] = ["source-gated original Native crossing capture",
                            "source-bound original body audit", "explicit ego response request"]
    bundle["measurement_plan"] = {"entry_and_clearance":
        "Original body frames; legal and public-highway review remains unresolved until site packet supplied"}
    bundle["static_checks"] = ["exact runner/config binding",
                               "Native source packet and hash required",
                               "diagnostic packet rejected before CARLA import"]
    bundle["termination_rules"] = ["Native exits before capture when reviewed site packet is absent",
                                   "seal only after capture and restoration"]
    target = ROOT / "cases" / suffix / "selected" / ("fallback1" if candidate == "fallback1" else "primary") / "construction.json"
    write(target, bundle)
    return {"candidate": candidate, "construction": str(target.relative_to(ROOT)),
            "sha256": sha(target), "case_id": bundle["case_id"]}


if __name__ == "__main__":
    rows = [build(suffix, candidate) for suffix in SUFFIXES for candidate in ("primary", "fallback1")]
    write(ROOT / "source-gated-candidate-index.json", {"format": "c125714-source-gated-candidates",
          "assignment_id": ROOT.name, "cases": rows,
          "scope": "CPU-prepared engineering scenes; original site review required at Native launch"})
    print(json.dumps({"cases": len(SUFFIXES), "constructions": len(rows)}))
