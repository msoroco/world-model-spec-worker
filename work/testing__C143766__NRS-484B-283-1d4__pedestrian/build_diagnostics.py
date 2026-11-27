"""Build source-specific synthetic 9-frame crossing software fixtures."""
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
        cid = case['case_id']
        short = cid.split('__')[-1]
        folder = HERE / 'cases' / short
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic['files']
        capture = json.loads(files['capture/manifest.json'])
        capture['case_id'] = cid
        files['capture/manifest.json'] = json.dumps(capture, sort_keys=True) + '\n'
        mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        example_trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
        entry_index = {'walk': 2, 'flashing': 4, 'steady': 7}[case['entry_phase']]
        arrival_index = 8 if case['arrival_phase'] == 'steady' else 6
        frames = []
        trace = []
        for index, row in enumerate(mapping):
            phase = 'walk' if index < 3 else 'flashing' if index < 7 else 'steady'
            frames.append({'frame': row['carla_frame'], 'time_s': row['time_s'],
                'signal_phase': phase,
                'countdown_visible': bool(case['countdown'] and phase == 'flashing'),
                'in_highway': entry_index <= index < arrival_index,
                'at_destination': index >= arrival_index,
                'position_m': example_trace[index]['position_m'],
                'pedestrian_pose_source_sha256': sha(b'synthetic-pose-packet'),
                'signal_readback_source_sha256': sha(b'synthetic-signal-packet'),
                'exception_context': {'NRS 484B.287': 'synthetic_unknown',
                    'NRS 484B.290': 'synthetic_unknown', 'NRS 484B.350': 'synthetic_unknown'}})
            trace.append(example_trace[index])
        packet = {'assignment_id': HERE.name, 'case_id': cid,
            'original_trace_id': 'synthetic-diagnostic-trace',
            'pedestrian_actor_id': 'synthetic-pedestrian',
            'crossing_id': 'synthetic-highway-crossing',
            'signal_actor_id': 'synthetic-official-facing-signal',
            'site_source_sha256': sha(b'synthetic-reviewed-site'),
            'signal_source_sha256': sha(b'synthetic-official-signal'),
            'destination_source_sha256': sha(b'synthetic-safety-destination'),
            'destination': case['destination'], 'diagnostic_fixture': True,
            'frames': frames}
        source_text = json.dumps(packet, sort_keys=True) + '\n'
        files['original-crossing-observations.json'] = source_text
        files['original-crossing-receipt.json'] = json.dumps({'case_id': cid,
            'fps': 20, 'frame_count': len(frames), 'diagnostic_fixture': True,
            'source_sha256': sha(source_text.encode())}, sort_keys=True) + '\n'
        files['fixture-provenance.json'] = json.dumps({'case_id': cid,
            'scope': 'Synthetic 9-frame crossing software diagnostic only; no original signal, pedestrian or legal evidence'},
            sort_keys=True) + '\n'
        path = folder / 'diagnostic.json'
        path.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
        relative = str(path.relative_to(ROOT))
        write(folder / 'fixture-recipe.json', {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                'sha256': sha(path.read_bytes())}],
            'generator': {'source': relative, 'sha256': sha(path.read_bytes())}})
        write(folder / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': cid,
            'requirements': [{'disposition_index': i,
                'requirement': disposition['requirement'], 'source': disposition['source'],
                'output_key': key, 'method': method,
                'value_type': 'object', 'kind': 'measured',
                'inputs': ['original-crossing-observations.json', 'original-crossing-receipt.json']}
                for i, (disposition, key, method) in enumerate(zip(
                    plan['requirement_dispositions'],
                    ('entry_phase', 'continuation_timing', 'countdown_context'),
                    ('measure_entry_phase', 'measure_continuation', 'measure_countdown_context')))],
            'negative': {'remove': ['original-crossing-observations.json'],
                'error_contains': 'Missing required source: original-crossing-observations.json'}})
        print(short, 'synthetic source fixture and measurement contract', flush=True)


if __name__ == '__main__':
    build()
