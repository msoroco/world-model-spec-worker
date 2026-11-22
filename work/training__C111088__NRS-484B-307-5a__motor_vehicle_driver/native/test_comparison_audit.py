"""Positive and tamper-negative checks for the independent comparison audit."""
import copy
import json

from audit_comparison import NATIVE, audit


def main():
    passed = audit()
    assert passed["passed"] and passed["fixed_configuration_isolated"]
    original = json.loads((NATIVE / "true-primary-saved-r8.json").read_text())
    for label, mutation, expected in [
        ("swapped-case", {"case_id": passed["cases"]["false"]["case_id"]}, "Saved receipt case/candidate mismatch"),
        ("false-recorded-only", {"recorded_only": False}, "Saved processing or source preservation failed"),
        ("false-acceptance", {"physical_acceptance_claimed": True}, "Saved receipt overclaims acceptance"),
        ("changed-result-hash", {"result_sha256": "0" * 64}, "Saved result missing or changed"),
    ]:
        altered = copy.deepcopy(original)
        altered.update(mutation)
        try:
            audit({"true": altered})
        except ValueError as exc:
            assert expected in str(exc), (label, str(exc))
        else:
            raise AssertionError("Audit accepted tamper: " + label)
    print(json.dumps({"positive": True, "rejected_tampers": 4,
                      "comparison_variable": passed["comparison_variable"]}))


if __name__ == "__main__":
    main()
