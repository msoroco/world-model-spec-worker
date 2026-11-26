"""Build four exact synthetic nearest-rail software diagnostic fixtures."""
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


def footprint(distance: float) -> list[list[float]]:
    return [[distance, -1.0], [distance + 4.0, -1.0],
            [distance + 4.0, 1.0], [distance, 1.0]]


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
        target = case['requested_nearest_vehicle_to_rail_m']
        rails = [{'rail_id': 'synthetic-rail-nearest', 'points_m': [[0.0, -20.0], [0.0, 20.0]]},
                 {'rail_id': 'synthetic-rail-farther', 'points_m': [[-5.0, -20.0], [-5.0, 20.0]]}]
        frames = []
        for index, row in enumerate(mapping):
            d = target + max(0, 5 - index)
            frames.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                'vehicle_action': 'park' if index >= 5 else 'approach',
                'vehicle_footprint_m': footprint(d), 'ego_xyz_m': [d + 2.0, 0.0, 0.0],
                'ego_speed_mps': 0.0 if index >= 5 else 1.0,
                'other_vehicle_actor_id': 'synthetic-other-vehicle',
                'other_vehicle_xyz_m': [30.0 - index, 3.0, 0.0],
                'other_vehicle_speed_mps': 1.0,
                'observation_source': 'synthetic_diagnostic'})
        exceptions = {name: 'absent' for name in ('traffic_conflict_necessity',
            'law_compliance', 'officer_direction', 'official_device_direction')}
        exceptions['traffic_conflict_necessity'] = case['requested_traffic_conflict_necessity_status']
        packet = {'assignment_id': HERE.name, 'case_id': case_id,
            'original_trace_id': 'synthetic-diagnostic-trace',
            'vehicle_actor_id': 'synthetic-ego', 'vehicle_action': 'park',
            'vehicle_footprint_m': footprint(target), 'rail_polylines_m': rails,
            'exception_context': exceptions,
            'site_source_sha256': sha(b'synthetic-railroad-protocol'),
            'diagnostic_fixture': True,
            'site': {'railroad_identity': 'synthetic-railroad',
                'carrier_provenance': 'synthetic_diagnostic',
                'other_vehicle_actor_id': 'synthetic-other-vehicle'},
            'frames': frames}
        packet_text = json.dumps(packet, sort_keys=True) + '\n'
        files['original-rail-observations.json'] = packet_text
        files['original-rail-receipt.json'] = json.dumps({'case_id': case_id,
            'fps': 20, 'frame_count': len(frames), 'diagnostic_fixture': True,
            'source_sha256': sha(packet_text.encode())}, sort_keys=True) + '\n'
        files['fixture-provenance.json'] = json.dumps({'case_id': case_id,
            'scope': 'Synthetic 9-frame rail-distance protocol; no original railroad or legal evidence'},
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
                'output_key': 'nearest_rail', 'method': 'measure_nearest_rail',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-rail-observations.json', 'original-rail-receipt.json']}],
            'negative': {'remove': ['original-rail-observations.json'],
                'error_contains': 'Missing required source: original-rail-observations.json'}})
        print(short, 'synthetic rail diagnostic and contract', flush=True)


if __name__ == '__main__':
    build()
