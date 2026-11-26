"""Check authored crosswalk parking targets without claiming Native readback."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import box

from geometry import check, open_drive, target_center
from runner import body_xy


class _Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class _Bounds:
    def get_world_vertices(self, transform):
        return [_Point(x, y) for x, y in ((1, 1), (-1, -1), (1, -1), (-1, 1))]


class _Actor:
    bounding_box = _Bounds()

    def get_transform(self):
        return None


def main():
    root = Path(__file__).resolve().parent
    scope = check()
    document = ET.fromstring(open_drive())
    road = document.find(".//road[@id='1']")
    obj = road.find(".//object[@type='crosswalk']")
    assert obj is not None
    start_y = -100 + float(obj.attrib['s'])
    crosswalk = box(-float(obj.attrib['width']) / 2, start_y,
                    float(obj.attrib['width']) / 2,
                    start_y + float(obj.attrib['length']))
    overlaps = {}
    for label, occupied in [('clear', False), ('occupy', True)]:
        x, y = target_center(occupied)
        footprint = box(x - .95, y - 2.35, x + .95, y + 2.35)
        overlaps[label] = footprint.intersection(crosswalk).area
    assert overlaps['clear'] == 0 and overlaps['occupy'] > 0
    from shapely.geometry import Polygon
    assert Polygon(body_xy(_Actor())).is_valid
    assert Polygon(body_xy(_Actor())).area == 4
    assert scope['cell_id'] == 'C229397' and scope['law_id'] == 'NRS-484B-450-1e'
    proof = {
        'format': 'c229397-authored-crosswalk-target-proof-v1',
        'geometry_sha256': hashlib.sha256((root / 'geometry.py').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256((root / 'runner.py').read_bytes()).hexdigest(),
        'crosswalk_source': 'authored OpenDRIVE road 1 object 501',
        'crosswalk_bounds_xy_m': list(crosswalk.bounds),
        'target_overlap_m2': overlaps,
        'native_map_readback_observed': False,
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_verdict': None,
    }
    (root / 'geometry-proof.json').write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
    print(json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    main()
