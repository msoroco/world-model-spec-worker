"""Rebuild eight unselected drafts with an exclusive right-turn lane link."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
source_manifest = json.loads((root / "draft-execution-manifest.json").read_text())
geometry_source = (root / "native/geometry.py").read_text()
remove = "    ET.SubElement(straight,'laneLink',**{'from':'-2','to':'-2'})\n"
assert geometry_source.count(remove) == 1
geometry_source = geometry_source.replace(remove, "")
old_assert = "    assert len(links)==3 and {tuple(link.attrib.items()) for link in links}=={"
assert geometry_source.count(old_assert) == 1
geometry_source = geometry_source.replace(old_assert, old_assert.replace("==3", "==2"))
geometry_source = geometry_source.replace(
    "'right_only_and_adjacent_straight_connectors_authored':True",
    "'right_only_turn_link_and_adjacent_straight_link_authored':True",
)
replacement = {
    "geometry.py": geometry_source,
    "fallback_triggers.py": (root / "native/fallback_triggers.py").read_text(),
    "tests/test_fallback_triggers.py": (root / "native/test_fallback_triggers.py").read_text(),
}
manifest = json.loads(json.dumps(source_manifest))
manifest["status"] = "right_only_topology_repair_unselected"
for case in manifest["cases"]:
    case["kind"] = "draft_not_selected"
    case["candidate_risk"]["reason"] = (
        "Exclusive right-turn link is authored; original Native execution, lane cue, "
        "continuous crossing, tracking, and framing remain to be measured"
    )
    label = case["case_id"].rsplit("__", 1)[1]
    entries = [case, *case["candidates"]]
    for entry in entries:
        candidate = entry["id"]
        old = json.loads((root / entry["construction"]).read_text())
        seen = set()
        for file in old["files"]:
            if file["path"] in replacement:
                file["content"] = replacement[file["path"]]
                seen.add(file["path"])
        assert seen == set(replacement), (label, candidate, seen)
        old["status"] = "unselected_right_only_topology_repair_draft"
        old["mechanisms"] = [
            "lane -2 has only a right-turn link; adjacent lane -1 retains the straight link",
            "contrast attempts a straight crossing from the right-only lane without a straight lane link",
            "source-bound trigger expects the case-specific lane-link state",
            "observed-pose controller and four synchronized lossless cameras",
        ]
        destination = root / "right-only-candidates" / label / candidate / "construction.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(old, indent=2) + "\n")
        entry["construction"] = str(destination.relative_to(root))
        entry["construction_sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
        if candidate == "fallback1":
            entry["trigger"]["metric"] = "case-specific lane-link state and full-body straight exit"
            entry["trigger"]["failure_condition"] = (
                "Observed requested-lane link differs from expected state "
                "(reference straight link present; contrast straight link absent), "
                "or full-body exit absent by 24 s"
            )
out = root / "right-only-candidates-manifest.json"
out.write_text(json.dumps(manifest, indent=2) + "\n")
for case in manifest["cases"]:
    print(case["case_id"])
    for entry in [case, *case["candidates"]]:
        print(entry["id"], entry["construction_sha256"])
