"""Verify the returned officer pair's current-runtime offline proof."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest_path = ROOT / "officer-pair-draft-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    proof = json.loads((ROOT / "officer-pair-offline-proof.json").read_text())
    assert proof["manifest_sha256"] == digest(manifest_path)
    assert proof["physical_acceptance_claimed"] is False
    assert len(manifest["cases"]) == 2
    expected = set()
    for case in manifest["cases"]:
        assert case["case_id"].split("__")[-1] in {
            "officer_controls_ego", "officer_not_controlling_ego"
        }
        for name, item in [("primary", case), *[(c["id"], c) for c in case["candidates"]]]:
            assert name in {"primary", "fallback1", "fallback2", "fallback3"}
            construction = ROOT / item["construction"]
            assert item["construction_sha256"] == digest(construction)
            body = json.loads(construction.read_text())
            assert body["case_id"] == case["case_id"]
            for file in body["files"]:
                if file.get("source"):
                    assert Path(file["source"]).read_text() == file["content"]
            expected.add((case["case_id"], name))
    seen = set()
    for receipt in proof["results"]:
        key = (receipt["case_id"], receipt["candidate"])
        assert key in expected and key not in seen
        seen.add(key)
        assert receipt["exit_code"] == 0
        log = ROOT / receipt["log"]
        assert receipt["log_sha256"] == digest(log)
        outcome = json.loads(log.read_text())
        assert outcome["case_id"] == key[0]
        assert outcome["candidate_id"] == key[1]
        assert outcome["offline_passed"] is True
        assert outcome["simulation_started"] is False
    assert seen == expected
    return {"draft_cases": len(manifest["cases"]), "offline_proofs": len(seen)}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
