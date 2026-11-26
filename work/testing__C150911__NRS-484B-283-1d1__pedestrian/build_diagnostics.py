"""Build four exact synthetic WALK fixtures and selected measurement contracts."""
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
            frames.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                'signal_indication': case['requested_signal_at_entry'],
                'pedestrian_facing_signal': case['requested_pedestrian_facing_signal'],
                'pedestrian_in_crosswalk': index >= 2,
                'crossing_direction_matches_signal': case['requested_pedestrian_facing_signal'],
                'driver_yield_observed': case['requested_driver_yield'],
                'driver_actor_ids': ['synthetic-driver'],
                'exception_context': {'NRS 484B.287': 'synthetic_unknown',
                    'NRS 484B.290': 'synthetic_unknown',
                    'NRS 484B.350': 'synthetic_unknown'}})
        packet = {'assignment_id': HERE.name, 'case_id': case_id,
            'original_trace_id': 'synthetic-diagnostic-trace',
            'pedestrian_actor_id': 'synthetic-walker',
            'crosswalk_id': 'synthetic-crosswalk',
            'pedestrian_signal_id': 'synthetic-official-signal-protocol',
            'site_source_sha256': sha(b'synthetic-site-protocol'),
            'exception_source_sha256': sha(b'synthetic-exception-protocol'),
            'diagnostic_fixture': True, 'frames': frames}
        packet_text = json.dumps(packet, sort_keys=True) + '\n'
        files['original-walk-observations.json'] = packet_text
        files['original-walk-receipt.json'] = json.dumps({'case_id': case_id,
            'fps': 20, 'frame_count': len(frames), 'diagnostic_fixture': True,
            'source_sha256': sha(packet_text.encode())}, sort_keys=True) + '\n'
        files['fixture-provenance.json'] = json.dumps({'case_id': case_id,
            'scope': 'Synthetic 9-frame WALK software diagnostic, not original signal, motion or legal evidence'},
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
                'output_key': 'walk_entry', 'method': 'measure_walk_entry',
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-walk-observations.json', 'original-walk-receipt.json']}],
            'negative': {'remove': ['original-walk-observations.json'],
                'error_contains': 'Missing required source: original-walk-observations.json'}})
        print(short, 'synthetic diagnostic and contract', flush=True)


if __name__ == '__main__':
    build()
