"""CPU test of the selected visibility pair's fallback construction geometry."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import comparison_audit
from standing_geometry import measure

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def scene(suffix: str, fallback: bool) -> dict:
    name = "fallback1-scene.json" if fallback else "scene.json"
    return json.loads((HERE / "cases" / suffix / name).read_text())


def write_attempt(root: Path, label: str, value: dict) -> Path:
    path = root / label
    path.mkdir()
    (path / "scene.json").write_text(json.dumps(value, indent=2) + "\n")
    measured = measure(value)
    (path / "standing-measurement.json").write_text(json.dumps({"measured": {
        "minimum_unobstructed_opposite_width_m": measured["unobstructed_opposite_width_m"],
        "physical_passage_observed": measured["physical_passage_observed"],
    }}, indent=2) + "\n")
    return path


def main() -> None:
    clear = scene("passage_clear_view", True)
    occluded = scene("view_occluded_both", True)
    primary = scene("view_occluded_both", False)
    assert clear["standing_body_xy_m"] == occluded["standing_body_xy_m"]
    assert clear["standing_body_xy_m"] != primary["standing_body_xy_m"]
    assert clear["sight_occluders_xy_m"] == []
    for side in ("negative_x", "positive_x"):
        key = f"{side}:60.960m"
        assert measure(clear)["sight_probes"][key]["visible"]
        assert not measure(occluded)["sight_probes"][key]["visible"]
    assert measure(clear)["physical_passage_observed"]
    assert measure(occluded)["physical_passage_observed"]

    # The independent comparison audit also checks the selected attempt
    # directories. Replace only the delivery receipt validator with a test
    # double so the comparison branch itself runs without Native media.
    comparison_audit.audit_delivery = lambda path, diagnostic_test=False: {
        "case_id": json.loads((path / "scene.json").read_text())["case_id"]
    }
    scratch = HERE.parents[1] / ".runtime-work" / "c135705-fallback-review"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        root = Path(temporary)
        left = write_attempt(root, "clear_fallback", clear)
        right = write_attempt(root, "occluded_fallback", occluded)
        mixed = write_attempt(root, "occluded_primary", primary)
        comparison_id = "two_sided_visibility_with_fixed_passage"
        result = comparison_audit.audit(comparison_id, left, right, diagnostic_test=True)
        assert result["status"] == "cpu_source_audit_passed"
        try:
            comparison_audit.audit(comparison_id, left, mixed, diagnostic_test=True)
        except ValueError as error:
            assert "standing body changed" in str(error)
        else:
            raise AssertionError("mixed footprint selection was accepted")
    print(json.dumps({
        "case_ids": [clear["case_id"], occluded["case_id"]],
        "matched_standing_body_xy_m": clear["standing_body_xy_m"],
        "matched_opposite_width_m": measure(clear)["unobstructed_opposite_width_m"],
        "clear_view_200ft": True,
        "occluded_view_both_200ft": True,
        "matched_fallback_pair_audit": "passed",
        "mixed_fallback_primary_pair_audit": "rejected: standing body changed",
        "native_realization_claimed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
