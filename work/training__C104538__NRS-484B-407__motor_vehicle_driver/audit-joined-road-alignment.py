"""Independent raw-row audit of the synthetic joined Core road alignment."""
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.geometry import reference, static_map
from shapely.geometry import Point


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = REPO / '.runtime-work/c104538/joined-package-v1/fixture'
    current = REPO / '.runtime-work/c104538/joined-package-v3/fixture'
    converted = REPO / '.runtime-work/c104538/joined-package-v3/output/converted'
    road = ET.parse(current / 'road.xodr').getroot()
    x, y, heading, curvature = reference(road.find('./road/planView/geometry'), 200.0)
    assert curvature == 0.002
    cosine, sine = math.cos(heading), math.sin(heading)
    def transformed(point):
        a, b, z = point
        return [x + cosine*a + sine*b, -y - sine*a + cosine*b, z]
    before, after = rows(old / 'trace.jsonl'), rows(current / 'trace.jsonl')
    history = rows(current / 'native_body_history.jsonl')
    evidence = rows(current / 'capture/evidence.jsonl')
    assert len(before) == len(after) == len(history) == len(evidence) == 480
    regions, polygons, _ = static_map(current / 'road.xodr')
    roadway = [polygons[r['id']] for r in regions if r['kind'] == 'roadway' and r['curvature'] != 0]
    assert roadway
    for a, b, h, e in zip(before, after, history, evidence):
        assert all(abs(p-q) < 1e-9 for p,q in zip(transformed(a['position_m']), b['position_m']))
        assert b['position_m'] == h['ego_center_xyz_m'] == e['ego']['position_m']
        assert h['ego_body_vertices_m'] == e['ego']['body_vertices_m']
        assert any(region.intersects(Point(b['position_m'][0], -b['position_m'][1])) for region in roadway)
    report = json.loads((converted / 'adapter_report.json').read_text())
    coverage = report['atom_coverage']
    assert coverage['missing'] == ['env.ice_or_snow', 'env.visibility']
    assert coverage['atoms']['st.curvature']['passed']
    assert coverage['atoms']['st.sight_distance']['passed']
    scenes = json.loads((converted / 'trace.json').read_text())['scenes']
    assert len(scenes) == 480
    assert all(any('curvature' in r for r in scene['structures']) for scene in scenes)
    assert all(any('sight_distance' in r for r in scene['structures']) for scene in scenes)
    print(json.dumps({'passed': True, 'source_frames': 480,
        'road_sha256': sha(current / 'road.xodr'),
        'aligned_trace_sha256': sha(current / 'trace.jsonl'),
        'core_report_sha256': sha(converted / 'adapter_report.json'),
        'missing': coverage['missing'],
        'scope': 'synthetic processing; retained visibility rays are not case-original pixels or rays'},
        sort_keys=True))


if __name__ == '__main__':
    main()
