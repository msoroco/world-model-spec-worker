"""Build exact, unselected engineering hazard-release probes from the proved far case.

These settings are controller parameters, never legal immediate-hazard cutoffs.
No canonical selection or Native physical acceptance is implied by this draft.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_SUFFIX = "approaching_far"
POINTS = {"approaching_release_3s": 3.0, "approaching_release_5s": 5.0}
LABELS = ("primary", "fallback1", "fallback2", "fallback3")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    canonical = json.loads((ROOT / "execution-manifest.json").read_text())
    selected = next(row for row in canonical["cases"]
                    if row["case_id"].endswith("__" + SOURCE_SUFFIX))
    entries = []
    index = []
    for suffix, release in POINTS.items():
        case_id = ROOT.name + "__" + suffix
        folder = ROOT / "cases" / suffix
        entry = copy.deepcopy(selected)
        entry["case_id"] = case_id
        entry["kind"] = "diagnostic_unselected"
        for key in ("offline", "compatibility", "negative", "post_capture",
                    "physical_preparation", "delivery_acceptance"):
            entry.pop(key, None)
        variants = []
        for label in LABELS:
            source_row = selected if label == "primary" else next(
                row for row in selected["candidates"] if row["id"] == label)
            bundle = copy.deepcopy(json.loads((ROOT / source_row["construction"]).read_text()))
            bundle["case_id"] = case_id
            for file in bundle["files"]:
                content = file["content"].replace(SOURCE_SUFFIX, suffix)
                if file["path"] == "config.json":
                    config = json.loads(content)
                    config["controller_release_ttc_s"] = (
                        release + 1.5 if label == "fallback1" else release)
                    config["hazard_sweep_role"] = "release_grid_" + str(int(release)) + "s"
                    config["hazard_legal_threshold"] = None
                    content = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
                file["content"] = content
            name = "construction.json" if label == "primary" else label + "-construction.json"
            path = folder / name
            write(path, bundle)
            variant = {"id": label, "construction": str(path.relative_to(ROOT)),
                       "construction_sha256": sha(path)}
            variants.append(variant)
            target = entry if label == "primary" else next(
                row for row in entry["candidates"] if row["id"] == label)
            for key in ("offline", "compatibility", "negative", "post_capture"):
                target.pop(key, None)
            target["construction"] = variant["construction"]
            target["construction_sha256"] = variant["construction_sha256"]
            if label == "fallback1":
                target["changed_knobs"] = ["controller_release_ttc_s"]
        entries.append(entry)
        index.append({"case_id": case_id, "engineering_release_ttc_s": release,
                      "legal_threshold": None, "canonical_selection": False,
                      "variants": variants})
    write(ROOT / "hazard-release-draft-index.json", {
        "format": "worker-hazard-release-construction-draft", "source_case": selected["case_id"],
        "cases": index})
    write(ROOT / "hazard-release-draft-manifest.json", {
        "format": canonical["format"], "assignment_id": ROOT.name,
        "runtime_manifest_sha256": canonical["runtime_manifest_sha256"], "cases": entries})
    return index


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
