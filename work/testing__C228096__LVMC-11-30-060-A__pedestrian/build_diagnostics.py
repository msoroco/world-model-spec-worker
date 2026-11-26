"""Build four exact synthetic outside-crosswalk software diagnostic fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / 'runtime/fixtures/example.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


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
        frames = []
        for index, row in enumerate(mapping):
            present = case['requested_vehicle_on_roadway']
            frames.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                'pedestrian_on_roadway': index >= 2,
                'pedestrian_yield_observed': case['requested_pedestrian_yield'],
                'vehicles_on_roadway': ['synthetic-vehicle'] if present else [],
                'pedestrian_xyz_m': [float(index), 0.0, 0.0],
                'vehicle_positions_xyz_m': {'synthetic-vehicle': [10.0 - index, 1.0, 0.0]}
                    if present else {},
                'observation_source': 'synthetic_diagnostic',
                'roadway_inventory_source': 'synthetic_diagnostic_all_actors'})
        site = {'roadway_id': 'synthetic-roadway',
            'crossing_point_id': 'synthetic-outside-crosswalk-point',
            'approach_xy_m': [0.0, 0.0], 'crossing_exit_xy_m': [8.0, 0.0],
            'within_marked_crosswalk': False,
            'within_unmarked_intersection_crosswalk': False,
            'prohibited_place_under_11_30_070':
                case['requested_prohibited_place_under_11_30_070']}
        packet = {'assignment_id': HERE.name, 'case_id': case_id,
            'original_trace_id': 'synthetic-diagnostic-trace',
            'pedestrian_actor_id': 'synthetic-pedestrian',
            'site_source_sha256': sha(b'synthetic-roadway-crosswalk-protocol'),
            'diagnostic_fixture': True, 'site': site, 'frames': frames}
        packet_text = json.dumps(packet, sort_keys=True) + '\n'
        files['original-crossing-observations.json'] = packet_text
        files['original-crossing-receipt.json'] = json.dumps({'case_id': case_id,
            'fps': 20, 'frame_count': len(frames), 'diagnostic_fixture': True,
            'source_sha256': sha(packet_text.encode())}, sort_keys=True) + '\n'
        files['fixture-provenance.json'] = json.dumps({'case_id': case_id,
            'scope': 'Synthetic 9-frame outside-crosswalk software diagnostic, not original roadway or legal evidence'},
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
                'output_key': 'outside_entry', 'method': 'measure_outside_entry',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-crossing-observations.json',
                           'original-crossing-receipt.json']}],
            'negative': {'remove': ['original-crossing-observations.json'],
                'error_contains': 'Missing required source: original-crossing-observations.json'}})
        print(short, 'synthetic diagnostic and contract', flush=True)


if __name__ == '__main__':
    build()
