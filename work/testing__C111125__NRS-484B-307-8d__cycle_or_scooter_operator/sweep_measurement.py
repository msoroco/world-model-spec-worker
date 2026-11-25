"""Measure a generated judgment sweep from sealed original Native readbacks.

The reported value is physical coverage data. It does not decide whether a
detector failed, whether a participant had right of way, or whether conduct
complied with NRS 484B.307(8)(d).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"


def _linked(root: Path, ref: dict) -> tuple[Path, str]:
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("sealed original source reference missing")
    path = (root / ref["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("sealed original source missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ref["sha256"]:
        raise ValueError("sealed original source hash differs")
    return path, digest


def measure(proposal: dict, case_id: str, attempt_root: Path) -> dict:
    """Return one realized observable; require a stopped original approach.

    The source-defined field is sampled from first stationary position before
    the stop boundary through the first straight entry. This avoids startup
    transients and never substitutes a requested control for a readback.
    """
    if not case_id.startswith(ASSIGNMENT + "__") or not proposal.get("sweeps_expanded"):
        raise ValueError("expanded exact sweep proposal required")
    cases = [row for row in proposal.get("cases", []) if row.get("case_id") == case_id]
    if len(cases) != 1 or cases[0].get("target_type") != "judgment_sweep":
        raise ValueError("exact generated judgment sweep case missing")
    case = cases[0]
    specs = [row for row in proposal.get("sweep_specs", []) if row.get("sweep_id") == case.get("sweep_id")]
    if len(specs) != 1 or specs[0].get("status") != "complete":
        raise ValueError("complete source-reviewed sweep specification missing")
    spec = specs[0]
    if case_id not in spec.get("selection_order", []) or case.get("sweep_spec_version") != spec.get("spec_version"):
        raise ValueError("generated sweep case differs from frozen source specification")
    if len(spec.get("axes", [])) != 1:
        raise ValueError("exact one-dimensional sweep axis required")
    axis = spec["axes"][0]
    variable = axis["variable"]
    binding = spec.get("numeric_control_binding", {})
    field = axis.get("measurement", {}).get("original_readback_field")
    if (not isinstance(field, str) or not field.isidentifier() or
            binding.get("original_readback_field") != field or
            variable not in case.get("sweep_point", {})):
        raise ValueError("sourced numeric control/readback binding missing")
    root = Path(attempt_root).resolve()
    attempt = json.loads((root / "attempt.json").read_text(encoding="utf-8"))
    if attempt.get("case_id") != case_id or attempt.get("diagnostic_fixture") is True:
        raise ValueError("original generated sweep attempt missing")
    packet_path, packet_sha = _linked(root, attempt.get("packet_ref"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    native_path, native_sha = _linked(root, packet.get("native_trace_ref"))
    geometry_path, geometry_sha = _linked(root, packet.get("geometry_ref"))
    rows = json.loads(native_path.read_text(encoding="utf-8")).get("frames")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != 900 or packet.get("frames") != rows:
        raise ValueError("full original Native sweep trace missing or differs")
    if [row.get("frame") for row in rows] != list(range(rows[0]["frame"], rows[0]["frame"] + 900)):
        raise ValueError("original sweep frame sequence broken")
    stamps = [row.get("timestamp_s") for row in rows]
    if (any(not isinstance(value, (int, float)) or isinstance(value, bool) or
            not math.isfinite(value) for value in stamps) or
            any(abs(stamps[index + 1] - stamps[index] - 0.05) > 0.001
                for index in range(899))):
        raise ValueError("original sweep time sequence broken")
    stop_boundary = geometry.get("stop_boundary_station_m")
    entry_boundary = geometry.get("entry_station_m")
    if not all(isinstance(value, (int, float)) and math.isfinite(value)
               for value in (stop_boundary, entry_boundary)) or stop_boundary >= entry_boundary:
        raise ValueError("original sweep boundaries missing")
    if any(not isinstance(row.get("ego_station_m"), (int, float)) or
           not math.isfinite(row["ego_station_m"]) or
           not isinstance(row.get("ego_speed_mps"), (int, float)) or
           not math.isfinite(row["ego_speed_mps"]) or row["ego_speed_mps"] < 0
           for row in rows):
        raise ValueError("original sweep bicycle motion missing")
    stop = next((i for i, row in enumerate(rows) if row["ego_station_m"] < stop_boundary
                 and row["ego_speed_mps"] <= 0.05), None)
    entry = next((i for i, row in enumerate(rows) if row["ego_station_m"] >= entry_boundary), None)
    if stop is None or entry is None or stop >= entry:
        raise ValueError("original stopped approach and straight entry required")
    values = [row.get(field) for row in rows[stop:entry + 1]]
    if not values or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                         or not math.isfinite(value) for value in values):
        raise ValueError("original numeric sweep readback missing")
    statistic = axis["measurement"]["statistic"]
    summaries = {"min": min(values), "max": max(values),
                 "mean": sum(values) / len(values), "first": values[0], "last": values[-1]}
    if statistic not in summaries:
        raise ValueError("unsupported original sweep statistic")
    return {"format": "c111125-original-sweep-measurement-v1",
            "case_id": case_id, "sweep_id": spec["sweep_id"],
            "source_hashes": {"packet": packet_sha, "native_trace": native_sha,
                              "geometry": geometry_sha},
            "requested_setpoint": {variable: case["sweep_point"][variable]},
            "realized_observables": {axis["observable"]: {"value": summaries[statistic],
                                                           "unit": axis["unit"]}},
            "window_frames": [rows[stop]["frame"], rows[entry]["frame"]],
            "raw_sample_count": len(values), "diagnostic_fixture": False,
            "physical_acceptance": False, "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError("sweep measurement output must remain outside original attempt")
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    receipt = measure(proposal, args.case, args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("retain previous original sweep measurement")
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case, "realized_observables": receipt["realized_observables"]}))


if __name__ == "__main__":
    main()
