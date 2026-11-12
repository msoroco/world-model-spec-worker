"""Check physical outcome adaptation keeps synthetic motion unverified."""
import json
import tempfile
from pathlib import Path

from physical_outcome import outcome

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")


def main():
    cases = []
    for suffix in SUFFIXES:
        case = HERE.name + "__" + suffix
        attempt = ROOT / ".runtime-work" / f"c104538-final-{suffix}-primary-compat"
        if suffix == "below_500_ft":
            attempt = ROOT / ".runtime-work/c104538-final-below-primary-compat"
        result = outcome(attempt, case, diagnostic=True)
        maneuver = result["physical_checks"]["maneuver"]
        assert maneuver["status"] == "unverified"
        assert maneuver["diagnostic_engineering_status"] == "met"
        assert result["provenance_kind"] == "synthetic_local_diagnostic"
        assert result["maneuver_completed"] is False and result["realized_observables"] is None
        assert result["two_direction_original_pixel_visibility_proven"] is False
        try:
            outcome(attempt, case)
        except ValueError as error:
            assert "Synthetic source cannot prove original Native motion" in str(error)
        else:
            raise AssertionError("Synthetic shape promoted to Native")
        cases.append({"case_id": case, "status": maneuver["status"],
                      "engineering_shape": maneuver["diagnostic_engineering_status"],
                      "synthetic_as_native_rejected": True})
    with tempfile.TemporaryDirectory() as directory:
        missing = outcome(Path(directory), HERE.name + "__below_500_ft", diagnostic=True)
    assert missing["physical_checks"]["maneuver"]["status"] == "unverified"
    assert missing["maneuver_completed"] is False and missing["missing_sources"]
    report = {"format": "c104538-physical-outcome-cpu-proof-v1",
              "diagnostic_cases": cases, "missing_source_status": "unverified",
              "native_complete_fixture_created": False,
              "physical_preparation_receipt_bound": False,
              "original_motion_or_visibility_claimed": False}
    (HERE / "update024-physical-outcome-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
