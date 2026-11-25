"""Expand the two judgment sweeps only from reviewed, hash-bound source ranges.

The returned proposal is a candidate for later construction. This command does
not turn synthetic evidence into original authority or make a legal judgment.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from signal_trial import construct_plan


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
SWEEPS = ("detector_causality", "directed_yield")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def linked(root, ref):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("reviewed sweep source reference missing")
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("reviewed sweep source missing")
    if digest(path) != ref["sha256"]:
        raise ValueError("reviewed sweep source stale")
    return path


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def prepare(proposal_path, authority_root, site_ref, ranges_ref):
    root = Path(authority_root).resolve()
    site_path = linked(root, site_ref)
    ranges_path = linked(root, ranges_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original site authority missing")
    construct_plan(site, root, "two_cycles_failed_detection")
    ranges = json.loads(ranges_path.read_text(encoding="utf-8"))
    if ranges.get("reviewed_original_ranges") is not True or ranges.get("site_sha256") != digest(site_path):
        raise ValueError("source-reviewed sweep ranges absent or bound to another site")
    control_path = linked(root, ranges.get("control_ref"))
    control = json.loads(control_path.read_text(encoding="utf-8"))
    if (control.get("reviewed_original_controls") is not True or
            control.get("site_sha256") != digest(site_path)):
        raise ValueError("source-supported numeric controls missing or bound to another site")
    controls = control.get("supported_numeric_controls")
    if not isinstance(controls, list) or len(controls) != 2:
        raise ValueError("two source-supported numeric controls required")
    controls_by_name = {}
    for entry in controls:
        if (not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or
                not entry["name"] or not isinstance(entry.get("adapter_method"), str) or
                not entry["adapter_method"].isidentifier() or
                not isinstance(entry.get("original_readback_field"), str) or
                not entry["original_readback_field"].isidentifier() or
                not isinstance(entry.get("unit"), str) or not entry["unit"]):
            raise ValueError("numeric control lacks executable adapter/readback binding")
        if entry["name"] in controls_by_name:
            raise ValueError("duplicate source numeric control")
        controls_by_name[entry["name"]] = entry
    for ref in ranges.get("evidence_refs", []):
        linked(root, ref)
    if not ranges.get("evidence_refs"):
        raise ValueError("original sweep feasibility evidence missing")
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
    if proposal.get("cell_id") != "C111125" or proposal.get("actor") != "cycle_or_scooter_operator":
        raise ValueError("wrong source sweep proposal")
    baseline = next((c for c in proposal["cases"] if c["target_type"] == "baseline"), None)
    if baseline is None:
        raise ValueError("baseline recording description missing")
    specs = proposal.get("sweep_specs", [])
    if len(specs) != 2 or {s["sweep_id"] for s in specs} != {"source_pending_0", "source_pending_1"}:
        raise ValueError("two original judgment placeholders required")
    entries = ranges.get("sweeps")
    if not isinstance(entries, dict) or set(entries) != set(SWEEPS):
        raise ValueError("both reviewed physical sweep ranges required")
    placeholder_by_id = {spec["sweep_id"]: spec for spec in specs}
    expanded_specs = []
    for placeholder_id, key in zip(("source_pending_0", "source_pending_1"), SWEEPS):
        placeholder = placeholder_by_id[placeholder_id]
        axis = entries[key]
        variable = axis.get("variable")
        if not isinstance(variable, str) or variable not in controls_by_name:
            raise ValueError("sweep axis lacks sourced numeric adapter control: " + key)
        binding = controls_by_name[variable]
        if axis.get("unit") != binding["unit"] or axis.get("measurement", {}).get("original_readback_field") != binding["original_readback_field"]:
            raise ValueError("sweep axis differs from sourced numeric readback: " + key)
        if axis.get("kind") not in ("controller", "world_setup"):
            raise ValueError("sweep control kind unsupported: " + key)
        if not all(finite(axis.get(k)) for k in ("min", "max", "spacing")) or not axis["min"] < axis["max"] or not 0 < axis["spacing"] <= axis["max"] - axis["min"]:
            raise ValueError("sourced sweep range/spacing invalid: " + key)
        for field in ("observable", "unit", "range_rationale", "spacing_rationale", "feasibility_evidence", "measurement"):
            if not axis.get(field):
                raise ValueError("sourced sweep axis missing " + field)
        measurement = axis["measurement"]
        if not all(measurement.get(k) for k in ("method", "time_window", "statistic")):
            raise ValueError("sourced sweep measurement incomplete")
        if measurement["statistic"] not in ("min", "max", "mean", "first", "last"):
            raise ValueError("sourced sweep statistic unsupported")
        if not axis.get("feasibility_source_ref"):
            raise ValueError("sweep feasibility source binding missing")
        linked(root, axis["feasibility_source_ref"])
        spec = {"sweep_id": ASSIGNMENT + "__" + key,
                "target_law_id": placeholder["target_law_id"],
                "judgment_refs": placeholder["judgment_refs"],
                "status": "complete", "mode": "one_dimensional",
                "axes": [{k: axis[k] for k in ("variable", "observable", "unit", "min", "max", "spacing", "measurement", "range_rationale", "spacing_rationale", "feasibility_evidence")}],
                "landmarks": axis.get("landmarks", []),
                "rationale": "Fixed source-reviewed physical coverage for " + key + "; no legal threshold or label",
                "variable_assignments": dict(baseline["variable_assignments"]),
                "recording_description": baseline["recording_description"]}
        spec["variable_assignments"][variable] = {"kind": axis["kind"], "unit": axis["unit"], "value": axis["min"]}
        spec["numeric_control_binding"] = {"adapter_method": binding["adapter_method"],
                                             "original_readback_field": binding["original_readback_field"],
                                             "control_sha256": digest(control_path)}
        expanded_specs.append(spec)
    proposal["sweep_specs"] = expanded_specs
    repo = Path(__file__).resolve().parents[2]
    output_root = repo / ".runtime-work" / "c111125-reviewed-sweep-expansion"
    output_root.mkdir(parents=True, exist_ok=True)
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output_root)
    os.environ["TMPDIR"] = str(output_root)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(repo / "runtime"))
    from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(proposal)
    proposal["reviewed_sweep_authority"] = {"site_sha256": digest(site_path),
                                             "ranges_sha256": digest(ranges_path),
                                             "control_sha256": digest(control_path)}
    return proposal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--ranges-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    proposal = prepare(args.proposal, args.authority_root,
                       json.loads(args.site_ref.read_text()), json.loads(args.ranges_ref.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("retain previous reviewed sweep expansion")
    args.output.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sweeps_expanded": True,
                      "source_reviewed_cases": sum(c.get("target_type") == "judgment_sweep" and c.get("sweep_id") in {s["sweep_id"] for s in proposal["sweep_specs"]} for c in proposal["cases"])}))


if __name__ == "__main__":
    main()
