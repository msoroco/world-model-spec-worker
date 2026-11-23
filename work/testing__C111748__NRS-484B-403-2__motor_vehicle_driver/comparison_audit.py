"""Independent saved-source comparison for the assigned device-duty pairs."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("native_device_for_comparison", ROOT / "native_device.py")
_native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)


class ComparisonError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise ComparisonError(reason)


def audit(comparison_id: str, sources: list[tuple[Path, str, str]]) -> dict:
    """Recheck each sealed Native source, then isolate one declared difference."""
    require(comparison_id in {"device_obedience", "device_applicability"}, "unknown comparison")
    require(len(sources) == 2, "comparison requires two exact sources")
    rows = []
    for path, case_id, sha256 in sources:
        measurement = _native.analyze(path, case_id=case_id, sha256=sha256)
        rows.append((json.loads(path.read_text(encoding="utf-8")), measurement))
    a, b = (r[0] for r in rows)
    ma, mb = (r[1] for r in rows)
    base = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__"
    suffixes = {case_id.removeprefix(base) for _, case_id, _ in sources}
    required = ({"prohibited_obey", "prohibited_attempt"} if comparison_id == "device_obedience"
                else {"prohibited_attempt", "neutral_device_turn"})
    require(suffixes == required, "wrong exact case pair")
    for key in ("actor", "map_sha256", "route_sha256", "ego_id", "highway_status", "camera_plan_sha256", "duration_s"):
        require(a.get(key) is not None and a[key] == b.get(key), f"fixed {key} differs or is missing")
    for key in ("authority_source_sha256", "legal_consistency_source_sha256", "governed_approach", "device_id"):
        require(a["device"].get(key) is not None and a["device"][key] == b["device"].get(key), f"fixed device {key} differs or is missing")
    require(a["frames"][0]["time_s"] == b["frames"][0]["time_s"] and len(a["frames"]) == len(b["frames"]), "frame window differs")
    if comparison_id == "device_obedience":
        require(ma["prohibits_u_turn"] and mb["prohibits_u_turn"], "prohibition not fixed")
        require(a["device"]["display_source_sha256"] == b["device"]["display_source_sha256"], "fixed display differs")
        require({ma["turn_observed"], mb["turn_observed"]} == {False, True}, "driver action did not differ")
    else:
        require(ma["turn_observed"] and mb["turn_observed"], "turn action not fixed")
        require({ma["prohibits_u_turn"], mb["prohibits_u_turn"]} == {False, True}, "device applicability did not differ")
        require(a["device"]["display_source_sha256"] != b["device"]["display_source_sha256"], "display source did not differ")
    return {"comparison_id": comparison_id, "case_ids": [case_id for _, case_id, _ in sources],
            "native_sha256": [sha256 for _, _, sha256 in sources], "fixed_conditions_checked": True,
            "declared_difference_observed": True, "legal_conclusion": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparison", required=True)
    ap.add_argument("--source", nargs=3, action="append", metavar=("PATH", "CASE", "SHA256"), required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = audit(args.comparison, [(Path(p), c, h) for p, c, h in args.source])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
