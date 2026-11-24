"""CPU proof that the authored right-only topology is exclusive."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from geometry import open_drive
from right_only_design import build, validate


def rejected(xml, message):
    try:
        validate(xml)
    except ValueError as error:
        assert message in str(error), str(error)
        print("REJECT", error)
    else:
        raise AssertionError("invalid topology accepted")


def main():
    xml = build()
    report = validate(xml)
    assert report["right_only_turn_link"] and not report["right_only_straight_link"]
    assert report["adjacent_straight_link"] and report["legal_verdict"] is None
    here = Path(__file__).resolve().parent
    (here / "right_only_road.xodr").write_text(xml)
    (here / "right-only-design-receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS exclusive right-only authored connector topology")
    print("XODR SHA256", report["authored_xodr_sha256"])
    rejected(open_drive(), "topology mismatch")
    root = ET.fromstring(xml)
    root.find("road[@id='1']/objects").clear()
    rejected(ET.tostring(root, encoding="unicode"), "arrow source missing")
    root = ET.fromstring(xml)
    straight = next(c for c in root.findall("junction/connection")
                    if c.attrib["connectingRoad"] == "14")
    ET.SubElement(straight, "laneLink", {"from": "-2", "to": "-2"})
    rejected(ET.tostring(root, encoding="unicode"), "topology mismatch")
    print("PASS three altered-source negatives")


if __name__ == "__main__":
    main()
