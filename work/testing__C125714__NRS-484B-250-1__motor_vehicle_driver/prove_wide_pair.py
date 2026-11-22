"""Verify the separate-carriageway diagnostic comparison and its declared changes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from crossing_audit import audit_comparison
from prove_opposite_pairs import ROOT, load_case


FIELDS = ("crossing_id", "roadway_id", "ego_approach_direction")


def prove(proof_root):
    first, first_hashes = load_case(proof_root, "precedence")
    second, second_hashes = load_case(proof_root, "wide_same_crossing")
    result = audit_comparison(first, second, FIELDS)
    if (result["left"]["ego_approach_direction"] != "east" or
            result["right"]["ego_approach_direction"] != "west" or
            result["left"]["legal_judgment"] != "unresolved" or
            result["right"]["legal_judgment"] != "unresolved"):
        raise ValueError("wide crossing direction or legal status differs")
    try:
        audit_comparison(first, second, FIELDS[:2])
    except ValueError as error:
        if "undeclared difference: ego_approach_direction" not in str(error):
            raise
    else:
        raise ValueError("undeclared ego approach difference was accepted")
    receipt = {
        "format": "c125714-wide-crossing-diagnostic-pair",
        "diagnostic_only": True,
        "case_ids": [ROOT.name + "__precedence", ROOT.name + "__wide_same_crossing"],
        "fixture_source_sha256": [first_hashes, second_hashes],
        "declared_differences": list(FIELDS),
        "negative_undeclared_direction_rejected": True,
        "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
    }
    (ROOT / "wide-pair-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"cases": receipt["case_ids"], "diagnostic": True,
                      "declared_differences": list(FIELDS), "negative": "rejected"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", type=Path, required=True)
    prove(parser.parse_args().proof_root)
