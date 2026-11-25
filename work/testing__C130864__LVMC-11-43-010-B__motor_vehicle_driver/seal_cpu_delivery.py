"""Verify and bind returned diagnostic CPU proof receipts without legal claims."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest_sha = sha(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    cases = {e["case_id"]: e for e in manifest["cases"]}
    offline = read("cpu-offline-proofs.json")
    canonical = read("cpu-canonical-compatibility-proofs.json")
    independent = read("cpu-independent-proofs.json")
    saved = read("cpu-saved-proofs.json")
    comparisons = read("cpu-comparison-proofs.json")
    assert len(cases) == 6 and len(offline) == 12 and len(canonical) == 12
    assert len(independent) == 6 and len(saved) == 12 and len(comparisons) == 5
    for row in offline:
        assert row["exit_code"] == 0
        assert sha(ROOT / row["log"]) == row["log_sha256"]
        selected = cases[row["case_id"]] if row["candidate"] == "primary" else cases[row["case_id"]]["candidates"][0]
        assert row["construction_sha256"] == selected["construction_sha256"]
    for row in canonical:
        assert row["exit_code"] == 0 and row["manifest_sha256"] == manifest_sha
        assert sha(ROOT / row["log"]) == row["log_sha256"]
        for key in ("compatibility.json", "compatibility-analysis.log", "negative-analysis.log"):
            assert sha(ROOT / row[key + "_path"]) == row[key + "_sha256"]
        receipt = json.loads((ROOT / row["compatibility.json_path"]).read_text())
        assert receipt["passed"] is True and receipt["negative_removed"]
        selected = cases[row["case_id"]] if row["candidate"] == "primary" else cases[row["case_id"]]["candidates"][0]
        assert receipt["construction_sha256"] == selected["construction_sha256"]
    for row in independent:
        assert row["positive_exit_code"] == 0 and row["negative_exit_code"] != 0
        for key in ("positive_log", "negative_log", "positive_receipt"):
            assert sha(ROOT / row[key]) == row[key + "_sha256"]
    for row in saved:
        assert row["manifest_sha256"] == manifest_sha and row["exit_code"] == 0
        assert row["originals_preserved"] is True
        assert row["missing_evidence"] is (row["variant"] == "missing-map")
        assert sha(ROOT / row["log"]) == row["log_sha256"]
        assert sha(ROOT / row["receipt"]) == row["receipt_sha256"]
        receipt = json.loads((ROOT / row["receipt"]).read_text())
        assert receipt["recorded_only"] is True and receipt["originals_preserved"] is True
    assert all(row["source_bound"] and row["diagnostic_only"] and
               not row["physical_acceptance"] and row["legal_verdict"] is None
               for row in comparisons)
    output = {"format": "c130864-selected-cpu-delivery-audit",
              "assignment_id": ROOT.name, "selected_manifest_sha256": manifest_sha,
              "case_count": len(cases), "offline_candidate_proofs": len(offline),
              "canonical_compatibility_proofs": len(canonical),
              "independent_positive_negative_proofs": len(independent),
              "saved_positive_missing_map_proofs": len(saved),
              "source_bound_comparisons": len(comparisons),
              "proof_indexes": {name: sha(ROOT / name) for name in (
                  "cpu-offline-proofs.json", "cpu-canonical-compatibility-proofs.json",
                  "cpu-independent-proofs.json", "cpu-saved-proofs.json",
                  "cpu-comparison-proofs.json")},
              "diagnostic_only": True, "physical_acceptance": False,
              "legal_verdict": None,
              "source_gap": "Reviewed original C130864 multilane roundabout map, lane routes, camera poses, jurisdiction and applicable legal gap interpretation are absent from supplied inputs."}
    (ROOT / "selected-cpu-delivery-audit.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_count": len(cases), "manifest_sha256": manifest_sha,
                      "checks": "passed"}))


if __name__ == "__main__":
    main()
