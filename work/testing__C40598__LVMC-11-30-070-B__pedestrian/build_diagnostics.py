"""Build exact synthetic software diagnostics for four C40598 cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / 'runtime/fixtures/example.json'
ROAD = [[0, 0], [10, 0], [10, 8], [0, 8]]
MARKED = [[1, 0], [4, 0], [4, 8], [1, 8]]
UNMARKED = [[4.5, 0], [7.5, 0], [7.5, 8], [4.5, 8]]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def box(x: float, y: float) -> list[list[float]]:
    return [[x, y], [x + .4, y], [x + .4, y + .4], [x, y + .4]]


def build() -> None:
    plan = json.loads((HERE / 'case-plan.json').read_text())
    example = json.loads(EXAMPLE.read_text())
    for case in plan['cases']:
        case_id = case['case_id']
        short = case_id.split('__')[-1]
        folder = HERE / 'cases' / short
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic['files']
        capture = json.loads(files['capture/manifest.json'])
        capture['case_id'] = case_id
        files['capture/manifest.json'] = json.dumps(capture, sort_keys=True) + '\n'
        mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        x = {'marked': 2.0, 'unmarked': 5.0, 'outside': 8.3}[
            case['crosswalk_category']]
        frames = []
        for index, row in enumerate(mapping):
            side = 'start' if index < 2 else ('opposite' if index >= len(mapping) - 2 else 'roadway')
            y = -2.0 if side == 'start' else (9.0 if side == 'opposite' else float(index - 1))
            frames.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                'actor_id': 'synthetic-pedestrian', 'body_polygon_xy_m': box(x, y),
                'pedestrian_on_roadway': side == 'roadway', 'curb_side': side,
                'observation_source': 'synthetic_diagnostic'})
        site = {'roadway_id': 'synthetic-business-roadway',
            'roadway_polygon_xy_m': ROAD,
            'crosswalk_inventory': {'roadway_id': 'synthetic-business-roadway',
                'marked_crosswalk_polygons_xy_m': [MARKED],
                'unmarked_intersection_crosswalk_polygons_xy_m': [UNMARKED],
                'classification_method': 'synthetic geometry only'},
            'district_type': 'business', 'highway_span_ft': 600,
            'district_frontage_review': case['district_frontage_review'],
            'district_source_sha256': sha(('synthetic-district-source:' +
                case['district_frontage_review']).encode()),
            'controls_source_sha256': sha(b'synthetic-controls-source')}
        packet = {'assignment_id': HERE.name, 'case_id': case_id,
            'original_trace_id': 'synthetic-diagnostic-trace',
            'pedestrian_actor_id': 'synthetic-pedestrian',
            'site_source_sha256': sha(('synthetic-business-site:' +
                case['district_frontage_review']).encode()),
            'diagnostic_fixture': True, 'site': site, 'frames': frames}
        packet_text = json.dumps(packet, sort_keys=True) + '\n'
        files['original-crossing-observations.json'] = packet_text
        files['original-crossing-receipt.json'] = json.dumps({'case_id': case_id,
            'fps': 20, 'frame_count': len(frames), 'diagnostic_fixture': True,
            'source_sha256': sha(packet_text.encode())}, sort_keys=True) + '\n'
        files['fixture-provenance.json'] = json.dumps({'case_id': case_id,
            'scope': 'Synthetic 9-frame business-district software diagnostic; no original site or legal evidence'},
            sort_keys=True) + '\n'
        path = folder / 'diagnostic.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
        relative = str(path.relative_to(ROOT))
        write(folder / 'fixture-recipe.json', {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                'sha256': sha(path.read_bytes())}],
            'generator': {'source': relative, 'sha256': sha(path.read_bytes())}})
        write(folder / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': case_id,
            'requirements': [{'disposition_index': 0,
                'requirement': plan['requirement_dispositions'][0]['requirement'],
                'source': plan['requirement_dispositions'][0]['source'],
                'output_key': 'crossing', 'method': 'measure_crossing',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-crossing-observations.json',
                           'original-crossing-receipt.json']}],
            'negative': {'remove': ['original-crossing-observations.json'],
                'error_contains': 'Missing required source: original-crossing-observations.json'}})
        print(short, 'synthetic source/contract prepared', flush=True)


if __name__ == '__main__':
    build()
