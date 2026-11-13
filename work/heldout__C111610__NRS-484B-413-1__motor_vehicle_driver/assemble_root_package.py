"""Assemble the assignment entrypoint from the proved first exact construction."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIRST = ROOT.name + '__pedestrian_horn_before_turn'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def assemble():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    first = next(item for item in manifest['cases'] if item['case_id'] == FIRST)
    exact = json.loads((ROOT / first['construction']).read_text())
    files = []
    for item in exact['files']:
        if item['path'].startswith('tests/'):
            continue
        copied = dict(item)
        # The exact primary embeds the source version proved for that case.
        # Root files are materialized copies; later prospective Native helpers
        # must not silently alter the already proved primary construction.
        copied.pop('source', None)
        current = ROOT / 'native_horn' / copied['path']
        if current.is_file() and copied['path'] != 'config.json':
            copied['content'] = current.read_text()
        if copied['path'] == 'config.json':
            config = json.loads(copied['content'])
            config['supported_case_ids'] = [item['case_id'] for item in manifest['cases']]
            copied['content'] = json.dumps(config, indent=2) + '\n'
        target = ROOT / copied['path']
        target.write_text(copied['content'])
        files.append(copied)
    root = {key: exact[key] for key in ('format', 'case_id', 'law_id', 'cell_id', 'actor',
                                       'entrypoint', 'recording_description')}
    root['files'] = files
    root['measurement_plan'] = {
        'finalizer': 'turn_finalizer.py',
        'retained_sources': ['ego_turn_motion.jsonl', 'ego_signal_audio.jsonl',
                             'affected_participants.json', 'participant_bodies.jsonl',
                             'listener_audio_original.jsonl', 'horn_actuation.jsonl',
                             'video_frames.jsonl', 'trace.jsonl'],
        'reported_boundary': 'Original turn, conditional signal and sampled body/audio observations; no legal cutoff'}
    root['static_checks'] = ['runner --check', 'exact offline and missing-original compatibility for every manifest case',
                             'saved-only processing and independent physical/delivery/comparison audits']
    root['termination_rules'] = ['160 original 20 Hz frames',
                                  'reject missing turn, participant, signal or frame source']
    root['mechanisms'] = ['Native connected turn and affected pedestrian/vehicle',
                          'original horn relay request, listener PCM and indicator readback',
                          'four synchronized original RGB streams', 'saved-only finalizer']
    write(ROOT / 'construction.json', root)
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 8,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [
                               {'view': 'overview', 'subject': 'turn, pedestrian, affected vehicle and horn context',
                                'interval': 'all 8 s'},
                               {'view': 'approach', 'subject': 'direct approach, turn onset and other vehicle',
                                'interval': 'all 8 s'},
                               {'view': 'reference_corner', 'subject': 'pedestrian route and turn body clearance',
                                'interval': 'all 8 s'},
                               {'view': 'driver_reference', 'subject': 'ego indicator and turn direction',
                                'interval': 'all 8 s'}]}
    write(plan_path, plan)
    return {'root_files': len(files), 'supported_cases': len(manifest['cases'])}


if __name__ == '__main__':
    print(assemble())
