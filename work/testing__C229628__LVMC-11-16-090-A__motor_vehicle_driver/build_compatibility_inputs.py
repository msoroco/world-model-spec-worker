"""Build compact nine-frame diagnostic packets for four exact aid cases."""
import hashlib
import json
from pathlib import Path

from contest_aid import CASES, SOURCE_FIELDS
from package_spec import AID, CAMERA_NAMES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / 'runtime/fixtures/example.json'
DRAFT = HERE / 'execution-manifest.selected-draft.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(exist_ok=True)
    kwargs = {'separators': (',', ':')} if compact else {'indent': 2}
    path.write_text(json.dumps(value, ensure_ascii=False, **kwargs) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic input exceeds return size limit')


def build():
    manifest = json.loads(DRAFT.read_text())
    base = json.loads(EXAMPLE.read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    trace = [json.loads(line) for line in base['files']['trace.jsonl'].splitlines()]
    if len(mapping) != 9 or len(trace) != 9:
        raise ValueError('expected nine-frame pinned diagnostic')
    for item, entry in zip(CASES, manifest['cases']):
        case_id = AID + '__' + item.name
        if entry['case_id'] != case_id:
            raise ValueError('manifest case order differs')
        fixture = json.loads(json.dumps(base))
        for video, name in zip(fixture['videos'], CAMERA_NAMES):
            video['path'] = name + '.mkv'
        scene = {'cell_id': 'C229628', 'actor': 'motor_vehicle_driver',
                 'municipal_jurisdiction': True, 'highway': item.highway,
                 'candidate_contest': item.candidate_contest, 'cue': item.cue,
                 'ego_person_id': 'fixture-ego-person',
                 'other_person_id': 'fixture-other-person',
                 'ego_vehicle_id': 'fixture-ego-vehicle',
                 'other_vehicle_id': 'fixture-other-vehicle',
                 'ego_route_xy': [[0., 0.], [50., 0.]],
                 'other_route_xy': [[0., 3.], [50., 3.]],
                 'lane_marking_xy': [[0., 1.5], [50., 1.5]],
                 'cue_frame': 2, 'other_start_frame': 3}
        scene.update({name + '_source_sha256': hashlib.sha256(name.encode()).hexdigest()
                      for name in SOURCE_FIELDS})
        rows = []
        for i, mapped in enumerate(mapping):
            position = trace[i]['position_m']
            row = {'original_frame': i, 'native_frame': mapped['native_frame'],
                   'time_s': i / 20, 'native_time_s': mapped['time_s'],
                   'ego_xy': position[:2],
                   'other_xy': [position[0], position[1] + 3],
                   'ego_speed_mps': 2.0,
                   'other_speed_mps': 0.0 if i < 3 else 2.0,
                   'ego_accel_mps2': 0.0, 'other_accel_mps2': 0.0,
                   'cue_observed': bool(item.cue and i == 2),
                   'highway': item.highway,
                   'candidate_contest': item.candidate_contest}
            row.update({key: scene[key] for key in
                        ('ego_person_id', 'other_person_id', 'ego_vehicle_id',
                         'other_vehicle_id')})
            row.update({key: scene[key] for key in scene if key.endswith('_source_sha256')})
            rows.append(row)
        packet = {'assignment_id': AID, 'case_id': case_id,
                  'reviewed_site_sha256': 'a' * 64,
                  'scene': scene, 'frames': rows}
        packet_text = json.dumps(packet, sort_keys=True) + '\n'
        trace_text = base['files']['trace.jsonl']
        frame_text = base['files']['video_frames.jsonl']
        receipt = {'source_kind': 'synthetic_diagnostic_fixture',
                   'diagnostic_fixture': True, 'case_id': case_id,
                   'packet_sha256': hashlib.sha256(packet_text.encode()).hexdigest(),
                   'trace_sha256': hashlib.sha256(trace_text.encode()).hexdigest(),
                   'frame_map_sha256': hashlib.sha256(frame_text.encode()).hexdigest(),
                   'physical_acceptance': False, 'legal_verdict': None}
        fixture['files'].update({'contest-packet.json': packet_text,
                                 'original-source-receipt.json':
                                 json.dumps(receipt, sort_keys=True) + '\n'})
        generator = HERE / 'diagnostics' / (item.name + '-generator.json')
        put(generator, fixture, compact=True)
        recipe = HERE / 'diagnostics' / (item.name + '-recipe.json')
        put(recipe, {'format': 'worker-fixture-recipe',
                     'sources': [{'path': 'diagnostic-input.json',
                                  'source': 'runtime/fixtures/example.json',
                                  'sha256': sha(EXAMPLE)}],
                     'generator': {'source': str(generator.relative_to(ROOT)),
                                   'sha256': sha(generator)}})
        output_keys = ('participants', 'cue_and_episode', 'two_vehicle_motion',
                       'highway_jurisdiction')
        requirements = [{'disposition_index': d['disposition_index'],
                         'requirement': d['requirement'], 'source': d['source'],
                         'output_key': output_keys[d['disposition_index']],
                         'method': 'source_sealed_contest_measurement',
                         'value_type': 'object', 'kind': 'measured',
                         'inputs': ['contest-packet.json',
                                    'original-source-receipt.json', 'trace.jsonl',
                                    'video_frames.jsonl']}
                        for d in json.loads((HERE / 'case-plan.json').read_text())['requirement_dispositions']]
        contract = HERE / 'diagnostics' / (item.name + '-measurement-contract.json')
        put(contract, {'format': 'worker-measurement-contract', 'case_id': case_id,
                       'requirements': requirements,
                       'negative': {'remove': ['contest-packet.json'],
                                    'error_contains': 'Missing required source: contest-packet.json'}})
        entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
        entry['measurement_contract'] = str(contract.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py',
             'method': 'source-sealed original cue, participants and two-vehicle motion'}
    put(DRAFT, manifest)
    return len(CASES)


if __name__ == '__main__':
    print('aid diagnostic inputs:', build())
