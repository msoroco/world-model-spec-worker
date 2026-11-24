"""Build an unselected exact primary using exclusive right-only lane topology."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
old = json.loads((root / "draft-candidates/reference/primary/construction.json").read_text())
geometry = next(f for f in old["files"] if f["path"] == "geometry.py")
code = geometry["content"]
remove = "    ET.SubElement(straight,'laneLink',**{'from':'-2','to':'-2'})\n"
assert code.count(remove) == 1
code = code.replace(remove, "")
check = "    assert len(links)==3 and {tuple(link.attrib.items()) for link in links}=={"
replacement = "    assert len(links)==2 and {tuple(link.attrib.items()) for link in links}=={"
assert code.count(check) == 1
code = code.replace(check, replacement)
code = code.replace("'right_only_and_adjacent_straight_connectors_authored':True",
                    "'right_only_turn_link_and_adjacent_straight_link_authored':True")
geometry["content"] = code
old["status"] = "unselected_right_only_topology_repair_draft"
old["mechanisms"] = [
    "right-only lane -2 has turn connector only; adjacent lane -1 retains straight connector",
    "contrast is an attempted straight crossing from the right-only approach, without a permitted straight lane link",
    "observed-pose path controller and four synchronized lossless cameras"]
folder = root / "right-only-primary"
folder.mkdir(exist_ok=True)
construction = folder / "construction.json"
construction.write_text(json.dumps(old, indent=2) + "\n")
digest = hashlib.sha256(construction.read_bytes()).hexdigest()
manifest_source = json.loads((root / "draft-execution-manifest.json").read_text())
reference = next(e for e in manifest_source["cases"] if e["case_id"].endswith("__reference"))
reference["construction"] = "right-only-primary/construction.json"
reference["construction_sha256"] = digest
reference["candidates"] = []
reference["kind"] = "draft_not_selected"
manifest_source["cases"] = [reference]
manifest_source["status"] = "right_only_topology_repair_unselected"
(root / "right-only-primary-manifest.json").write_text(json.dumps(manifest_source, indent=2) + "\n")
print(digest)
