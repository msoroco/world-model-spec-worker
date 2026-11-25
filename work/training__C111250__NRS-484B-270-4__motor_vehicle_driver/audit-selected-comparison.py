"""Independent selected pair and fallback receipt audit; CPU fixture scope."""
import argparse
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
audit_sources = runpy.run_path(str(HERE / "audit-native-pair.py"))["audit_sources"]


def read(path):
    return json.loads(path.read_text())


def config(path):
    bundle = read(path)
    return json.loads(next(file["content"] for file in bundle["files"]
                           if file["path"] == "config.json"))


def audit(reject_comparison_drift=False, remove_native_source=False):
    manifest = read(HERE / "execution-manifest.json")
    entries = {entry["case_id"].rsplit("__", 1)[1]: entry
               for entry in manifest["cases"]}
    if set(entries) != {"controlled_1", "controlled_2"}:
        raise ValueError("Selected exact pair missing")
    fixed = ("cell_id", "law_id", "actor", "rate_hz", "duration_s", "cameras",
             "required_atoms", "source_packets", "recording_description")
    for candidate in ("primary", "fallback1"):
        configs = []
        for suffix in ("controlled_1", "controlled_2"):
            entry = entries[suffix]
            selected = entry if candidate == "primary" else entry["candidates"][0]
            configs.append(config(HERE / selected["construction"]))
            receipt = read(HERE / f"selected-{suffix}-{candidate}-compatibility.json")
            saved = read(HERE / f"selected-{suffix}-{candidate}-processing.json")
            if (receipt["case_id"] != entry["case_id"] or not receipt["passed"]
                    or receipt["construction_sha256"] != selected["construction_sha256"]
                    or saved["case_id"] != entry["case_id"] or not saved["recorded_only"]
                    or saved["analysis_revision"]["construction_sha256"] != selected["construction_sha256"]
                    or saved["missing_evidence"] or saved["physical_acceptance_claimed"]
                    or saved["legal_acceptance_claimed"]):
                raise ValueError("Selected comparison proof differs")
        if reject_comparison_drift and candidate == "primary":
            configs[1]["duration_s"] = 29
        if any(configs[0][key] != configs[1][key] for key in fixed):
            raise ValueError("Comparison fixed condition changed")
        if configs[0]["case_suffix"] != "outside_cycle_lane" or \
           configs[1]["case_suffix"] != "within_cycle_lane" or \
           configs[0]["camera_lateral_shift_m"] != configs[1]["camera_lateral_shift_m"]:
            raise ValueError("Comparison route or fallback differs")
    if remove_native_source:
        raise ValueError("Missing required source: body-history.jsonl")
    observed = audit_sources(HERE / "native-diagnostic-controlled_1-sources",
                             HERE / "native-diagnostic-controlled_2-sources")
    return {"passed": True, "comparison_id": HERE.name + "__comparison",
            "fixed_candidate_pairs": 2, "observations": observed,
            "scope": "synthetic CPU source/receipt comparison; Native physical and legal review pending"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reject-comparison-drift", action="store_true")
    parser.add_argument("--remove-native-source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.reject_comparison_drift,
                           args.remove_native_source), indent=2))
