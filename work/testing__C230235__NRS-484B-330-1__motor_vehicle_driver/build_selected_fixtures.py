"""Build source-hashed CPU-only fixtures and exact measurement contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from flagger_zone import CASES, SOURCES
from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'runtime/fixtures/example.json'
INPUTS = {
    'qualifying_driver_highway': ('source-packet.json', 'original-ticks.jsonl',
                                  'driver_identity.txt', 'vehicle_class.txt', 'highway_status.txt'),
    'flagger_authority_and_role': ('source-packet.json', 'original-ticks.jsonl',
                                   'flagger_identity.txt', 'flagger_authorization.txt',
                                   'traffic_control_role.txt'),
    'clearly_marked_construction': ('source-packet.json', 'construction_or_maintenance.txt',
                                    'construction_marking.txt'),
    'designated_temporary_zone': ('source-packet.json', 'zone_designation.txt',
                                  'zone_boundaries.txt'),
    'applicable_flagger_signal': ('source-packet.json', 'original-ticks.jsonl',
                                  'signal_content.txt', 'signal_orientation.txt',
                                  'signal_visibility.txt', 'intended_recipient.txt',
                                  'release_event.txt'),
    'original_driver_response': ('source-packet.json', 'original-ticks.jsonl',
                                 'trace.jsonl', 'video_frames.jsonl', 'vehicle_motion.txt'),
}
KEYS = tuple(INPUTS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=False) + '\n')


def build():
    base = json.loads(BASE.read_text())
    trace = [json.loads(row) for row in base['files']['trace.jsonl'].splitlines()]
    assert len(trace) == 9
    plan = json.loads((HERE / 'case-plan.json').read_text())
    dispositions = plan['requirement_dispositions']
    count = 0
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        folder = HERE / 'cases' / case.name / 'diagnostic-sources' / 'original-flagger-source'
        folder.mkdir(parents=True, exist_ok=True)
        scene = {'cell_id': 'C230235', 'actor': 'motor_vehicle_driver',
                 'qualifying_vehicle': True, 'highway': True,
                 'driver_id': 'diagnostic-driver', 'vehicle_id': 'diagnostic-vehicle',
                 'flagger_id': 'diagnostic-flagger', 'designated': case.designated,
                 'marked_construction': case.marked_construction, 'authorized': case.authorized,
                 'signal': case.signal, 'response': case.response,
                 'zone_rect_m': [0, 0, 50, 10], 'stop_line_xy': [10, 5],
                 'flagger_xy': [10, 8], 'vehicle_route_xy': [[0, 5], [50, 5]],
                 'signal_frame': 2, 'release_frame': 7}
        refs = {}
        for name in (*SOURCES, 'map_opendrive'):
            path = folder / (name + '.txt')
            path.write_text('SYNTHETIC SOFTWARE FIXTURE ONLY: ' + name + '\n')
            digest = sha(path)
            refs[name] = {'path': path.name, 'sha256': digest,
                          'observation': 'Synthetic software exercise for ' + name,
                          'review_status': 'synthetic'}
            scene['map_opendrive_sha256' if name == 'map_opendrive'
                  else name + '_source_sha256'] = digest
        packet = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
                  'source_kind': 'synthetic_fixture', 'review_status': 'synthetic',
                  'scene': scene, 'source_refs': refs}
        write(folder / 'source-packet.json', packet)
        rows = []
        for index, frame in enumerate(trace):
            speed = (0.0 if case.response == 'stop' and 2 <= index < 7
                     else max(1.0, frame['speed_mps']))
            row = {'original_frame': frame['frame'], 'time_s': frame['time_s'],
                   'driver_id': scene['driver_id'], 'vehicle_id': scene['vehicle_id'],
                   'flagger_id': scene['flagger_id'], 'designated': case.designated,
                   'marked_construction': case.marked_construction, 'authorized': case.authorized,
                   'signal': case.signal, 'signal_visible': True,
                   'intended_vehicle_id': scene['vehicle_id'], 'vehicle_speed_mps': speed,
                   'vehicle_xy': [frame['position']['x'], frame['position']['y']]}
            row.update({name + '_source_sha256': scene[name + '_source_sha256']
                        for name in SOURCES})
            rows.append(row)
        (folder / 'original-ticks.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n' for row in rows))
        sources = []
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(HERE)
            target = 'original-flagger-source/' + path.name
            sources.append({'path': target, 'source': str(Path('work') / ASSIGNMENT / relative),
                            'sha256': sha(path)})
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                  'generator': {'source': 'runtime/fixtures/example.json', 'sha256': sha(BASE)}}
        write(HERE / 'cases' / case.name / 'fixture-recipe.json', recipe)
        requirements = []
        for index, disposition in enumerate(dispositions):
            if case_id not in disposition.get('case_ids', []):
                continue
            key = KEYS[index]
            inputs = [(name if name in ('trace.jsonl', 'video_frames.jsonl') else
                       'original-flagger-source/' + name) for name in INPUTS[key]]
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': key, 'method': 'analyze',
                                 'kind': 'measured' if key in ('applicable_flagger_signal',
                                                                'original_driver_response') else 'sourced_context',
                                 'value_type': 'object', 'inputs': inputs})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': requirements,
                    'negative': {'remove': ['original-flagger-source/original-ticks.jsonl'],
                                 'error_contains': 'Missing required source: original-flagger-source/original-ticks.jsonl'}}
        write(HERE / 'cases' / case.name / 'measurement-contract.json', contract)
        count += 1
    return count


if __name__ == '__main__':
    print(build())
