"""Bind all eight repaired drafts to tested, exact source bytes."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest_path = root / "right-only-candidates-manifest.json"
manifest = json.loads(manifest_path.read_text())
expected_geometry = json.loads((root / "right-only-primary/construction.json").read_text())
expected_geometry = next(f["content"] for f in expected_geometry["files"] if f["path"] == "geometry.py")
expected_trigger = (root / "native/fallback_triggers.py").read_text()
expected_tests = (root / "native/test_fallback_triggers.py").read_text()
rows = []
for case in manifest["cases"]:
    label = case["case_id"].rsplit("__", 1)[1]
    assert label in ("reference", "contrast")
    assert case["kind"] == "draft_not_selected"
    for entry in [case, *case["candidates"]]:
        candidate = entry["id"]
        construction_path = root / entry["construction"]
        construction = json.loads(construction_path.read_text())
        digest = hashlib.sha256(construction_path.read_bytes()).hexdigest()
        assert digest == entry["construction_sha256"]
        assert construction["case_id"] == case["case_id"]
        files = {f["path"]: f["content"] for f in construction["files"]}
        assert files["geometry.py"] == expected_geometry
        assert files["fallback_triggers.py"] == expected_trigger
        assert files["tests/test_fallback_triggers.py"] == expected_tests
        log = root / "right-only-candidates" / label / candidate / "unit-test.log"
        content = log.read_text()
        assert "Ran 16 tests" in content and "\nOK\n" in content
        assert '"right_only_turn_link_and_adjacent_straight_link_authored": true' in content
        if candidate == "fallback1":
            assert "Observed requested-lane link differs from expected state" in entry["trigger"]["failure_condition"]
        rows.append({
            "case": label,
            "candidate": candidate,
            "construction_sha256": digest,
            "offline_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "offline_tests": 16,
            "native_executed": False,
            "selected": False,
        })
assert len(rows) == 8
receipt = {
    "passed": True,
    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    "right_only_road_sha256": hashlib.sha256((root / "native/right_only_road.xodr").read_bytes()).hexdigest(),
    "cases": rows,
    "native_executed": False,
    "selected_delivery_cases": 0,
}
(root / "right-only-candidates-audit.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
