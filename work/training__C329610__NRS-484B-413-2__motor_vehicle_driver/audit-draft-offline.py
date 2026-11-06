"""Independent exact-construction/offline receipt audit for 24 signal bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
IDS = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    summary = json.loads((HERE / "draft-offline-summary.json").read_text())
    assert manifest["status"] == "draft_not_selected" and len(manifest["cases"]) == 6
    assert len(summary["results"]) == 24
    assert summary["runtime_manifest_sha256"] == sha(REPO / "runtime/pipeline/SOURCE-MANIFEST.json")
    receipts = {(r["case_id"], r["candidate_id"]): r for r in summary["results"]}
    assert len(receipts) == 24
    cases = {c["case_id"]: c for c in plan["cases"]}
    for entry in manifest["cases"]:
        case = cases[entry["case_id"]]
        contracts = json.loads((HERE / entry["measurement_contract"]).read_text())
        assert contracts["case_id"] == entry["case_id"] and contracts["duration_s"] == 40
        assert contracts["target_distance_ft"] == case["requested_setting"]
        refs = {"primary": entry, **{r["id"]: r for r in entry["candidates"]}}
        assert set(refs) == set(IDS)
        configs = {}
        for ident, ref in refs.items():
            construction = HERE / ref["construction"]
            assert sha(construction) == ref["construction_sha256"]
            bundle = json.loads(construction.read_text())
            assert (bundle["case_id"], bundle["law_id"], bundle["cell_id"], bundle["actor"]) == (
                case["case_id"], plan["law_id"], plan["cell_id"], plan["actor"])
            files = {f["path"]: f["content"] for f in bundle["files"]}
            assert "runner.py" in files and "tests/test_bundle.py" in files and "geometry.py" in files
            config = json.loads(files["config.json"])
            configs[ident] = config
            request = config["native_request"]
            assert (request["case_id"], request["candidate_id"], request["target_signal_distance_ft"]) == (
                case["case_id"], ident, case["requested_setting"])
            assert request["duration_s"] == 40 and request["rate_hz"] == 20
            assert request["area"] == case["area_classification"]
            assert request["source_assignment_sha256"] == plan["sources"][0]["sha256"]
            receipt = receipts[(case["case_id"], ident)]
            assert receipt["exit_code"] == 0 and receipt["construction_sha256"] == ref["construction_sha256"]
            assert sha(HERE / receipt["command_log"]) == receipt["command_log_sha256"]
            assert sha(HERE / receipt["unit_log"]) == receipt["unit_log_sha256"]
            assert "Ran 3 tests" in (HERE / receipt["unit_log"]).read_text()
            assert "offline --manifest" in receipt["command"] and "--candidate " + ident in receipt["command"]
        primary = configs["primary"]["native_request"]
        assert len({c["native_request"]["start_x_m"] for c in configs.values()}) == 2
        assert configs["fallback1"]["native_request"]["start_x_m"] < primary["start_x_m"]
        assert configs["fallback2"]["native_request"]["target_speed_mps"] < primary["target_speed_mps"]
        assert configs["fallback3"]["native_request"]["camera_policy"] != primary["camera_policy"]
        assert all(c["native_request"]["signal_onset_x_m"] == primary["signal_onset_x_m"] for c in configs.values())
    print(json.dumps({"cases_audited": 6, "bundles_audited": 24,
                      "tests_per_bundle": 3, "selected": False}))


if __name__ == "__main__":
    main()
