"""Independently audit retained exact mounted-bicycle offline bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
manifest_path = HERE/"draft-exact-execution-manifest.json"
summary_path = HERE/"draft-exact-offline-summary.json"
manifest = json.loads(manifest_path.read_text())
summary = json.loads(summary_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert manifest["format"] == "worker-unselected-draft-construction-manifest-v1"
assert manifest["status"] == "draft_not_selected" and len(manifest["cases"]) == 2
assert summary["manifest_sha256"] == sha(manifest_path)
assert summary["passed"] and len(summary["results"]) == 8
assert not summary["original_native_capture_executed"] and not summary["selected"]
seen = set()
for entry in manifest["cases"]:
    case_id = entry["case_id"]
    kind = "mounted_obey" if case_id.endswith("__controlled_1") else "mounted_turn"
    assert case_id.endswith(("__controlled_1", "__controlled_2"))
    assert len(entry["candidates"]) == 3
    knobs = []
    for name in ("primary", "fallback1", "fallback2", "fallback3"):
        ref = entry if name == "primary" else next(x for x in entry["candidates"] if x["id"] == name)
        construction_path = HERE/ref["construction"]
        assert sha(construction_path) == ref["construction_sha256"]
        construction = json.loads(construction_path.read_text())
        assert construction["case_id"] == case_id
        assert construction["law_id"] == "LVMC-11-40-080"
        assert construction["actor"] == "cycle_or_scooter_operator"
        assert construction["entrypoint"] == "runner.py"
        files = {x["path"]: x["content"] for x in construction["files"]}
        assert {"runner.py", "geometry.py", "engineering.py", "controller.py", "cameras.py",
                "config.json", "tests/test_bundle.py"}.issubset(files)
        config = json.loads(files["config.json"])
        assert config["case_id"] == case_id and config["case_suffix"] == kind
        assert config["candidate_id"] == name and config["rate_hz"]*config["duration_s"] == 480
        assert config["actor"] == "cycle_or_scooter_operator"
        assert {"ru.bicycle", "ru.rider_posture"}.issubset(config["required_atoms"])
        assert {"ru.bicycle", "ru.rider_posture"}.issubset(config["mandatory_channels"])
        assert len(config["cameras"]) == 4
        receipt_path = construction_path.parent/"draft-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["construction_sha256"] == sha(construction_path)
        assert receipt["candidate_id"] == name and receipt["case_id"] == case_id
        assert receipt["exit_code"] == 0 and not receipt["simulation_started"]
        assert sha(HERE/receipt["command_log"]) == receipt["command_log_sha256"]
        assert sha(HERE/receipt["unit_log"]) == receipt["unit_log_sha256"]
        assert "OK" in (HERE/receipt["unit_log"]).read_text()
        assert any(x["case_id"] == case_id and x["candidate_id"] == name and
                   x["construction_sha256"] == receipt["construction_sha256"]
                   for x in summary["results"])
        seen.add((case_id, name))
        if name != "primary":
            knobs.append(tuple(ref["changed_knobs"]))
            assert ref["trigger"]["metric"] in ("approach_runway_m", "release_error_frames", "scripted_visibility")
    assert len(set(knobs)) == 3
assert len(seen) == 8
changed = json.loads(json.dumps(manifest))
changed["cases"][0]["construction_sha256"] = "0"*64
assert changed["cases"][0]["construction_sha256"] != sha(HERE/changed["cases"][0]["construction"])
receipt = {"passed": True, "scope": "exact unselected offline construction and receipts",
           "candidate_count": len(seen), "changed_digest_rejected": True,
           "manifest_sha256": sha(manifest_path), "offline_summary_sha256": sha(summary_path),
           "original_native_capture_executed": False, "selected": False}
(HERE/"draft-exact-offline-audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
print(json.dumps(receipt))
