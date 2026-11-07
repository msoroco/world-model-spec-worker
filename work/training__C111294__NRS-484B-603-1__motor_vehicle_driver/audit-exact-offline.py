"""Independent source, policy and receipt audit of eight approach drafts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads((HERE / "exact-offline-summary.json").read_text())
    batch = json.loads((ROOT / "batch.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    policies = json.loads((HERE / "draft-candidates.json").read_text())
    assert manifest["status"] == "draft_not_selected"
    assert manifest["runtime_manifest_sha256"] == batch["runtime"]["source_manifest_sha256"]
    assert summary["manifest_sha256"] == sha(manifest_path)
    assert summary["all_passed"] and not summary["selected"]
    assert len(summary["results"]) == 8
    assert {c["case_id"] for c in manifest["cases"]} == {
        c["case_id"] for c in plan["cases"]}
    audited = []
    policy_by_suffix = {row["case_id"].split("__")[-1]: row for row in policies["cases"]}
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        policy_rows = {row["name"]: row for row in policy_by_suffix[suffix]["candidates"]}
        assert set(policy_rows) == set(NAMES)
        expected_triggers = policy_by_suffix[suffix]["fallback_triggers"]
        assert set(expected_triggers) == set(NAMES[1:])
        assert len({row["metric"] for row in expected_triggers.values()}) == 3
        assert len({row["failure_condition"] for row in expected_triggers.values()}) == 3
        common_files = None
        primary_config = None
        for candidate in NAMES:
            selected = entry if candidate == "primary" else next(
                c for c in entry["candidates"] if c["id"] == candidate)
            folder = HERE / "exact-drafts" / suffix / candidate
            construction_path = HERE / selected["construction"]
            construction = json.loads(construction_path.read_text())
            receipt = json.loads((folder / "receipt.json").read_text())
            files = {f["path"]: f["content"] for f in construction["files"]}
            config = json.loads(files["config.json"])
            assert len(files) == len(construction["files"])
            assert sha(construction_path) == selected["construction_sha256"]
            assert receipt["construction_sha256"] == selected["construction_sha256"]
            assert receipt["exit_code"] == 0
            assert receipt["case_id"] == entry["case_id"]
            assert receipt["candidate_id"] == candidate
            assert receipt["offline_command_log_sha256"] == sha(folder / "command-proof.log")
            assert receipt["offline_test_log_sha256"] == sha(folder / "unit-proof.log")
            log = (folder / "unit-proof.log").read_text()
            assert "Ran 4 tests" in log and "OK" in log
            assert "native_capture_executed\": false" in log
            assert config["case_id"] == entry["case_id"]
            assert config["candidate_id"] == candidate
            assert config["law_id"] == "NRS-484B-603-1"
            assert config["comparison_variable"] == "hazard_approach_speed_profile"
            assert config["required_atoms"] == ["kin.speed", "kin.velocity"]
            assert config["rate_hz"] == 20 and config["duration_s"] == 24
            assert config["source_packets"] == []
            assert config["frozen_source_hashes"] == plan["sources"]
            assert all(sha(ROOT / s["path"]) == s["sha256"] for s in config["frozen_source_hashes"])
            assert [v["name"] for v in config["cameras"]] == [
                "overview", "ego_forward", "ego_side", "junction"]
            assert [v["name"] for v in config["recording_description"]["channels"]] == [
                "ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose"]
            for key, value in policy_rows[candidate].items():
                if key != "name":
                    assert config["knobs"][key] == value
            assert files["authored-road.xodr"] == (HERE / "draft-fixtures/road.xodr").read_text()
            assert files["draft-candidates.json"] == (HERE / "draft-candidates.json").read_text()
            source_files = {k: v for k, v in files.items() if k != "config.json"}
            if common_files is None:
                common_files = source_files
                primary_config = config
            else:
                assert selected["trigger"] == {
                    "source": "hashed saved Native samples",
                    "metric": expected_triggers[candidate]["metric"],
                    "failure_condition": expected_triggers[candidate]["failure_condition"]}
                assert source_files == common_files
                assert {k: v for k, v in config.items() if k not in ("candidate_id", "knobs")} == {
                    k: v for k, v in primary_config.items() if k not in ("candidate_id", "knobs")}
                changes = {k: v for k, v in config["knobs"].items()
                           if primary_config["knobs"].get(k) != v}
                assert bool(changes) == (candidate != "primary")
                assert selected["changed_knobs"] == list(changes)
            audited.append((suffix, candidate, selected["construction_sha256"]))
    assert len(audited) == 8 and len({row[2] for row in audited}) == 8
    print(json.dumps({"passed": True, "independent_audit": True,
                      "exact_unselected_offline_bundles": len(audited),
                      "manifest_sha256": sha(manifest_path),
                      "offline_summary_sha256": sha(HERE / "exact-offline-summary.json"),
                      "selected": False, "portable_compatibility_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
