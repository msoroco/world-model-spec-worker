"""Construct an unselected physical peak-throttle sweep for C229597.

The sweep samples a controller request, not a legal exhibition threshold.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'sweep-physical'
VALUES = (0.5, 0.7, 0.9)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    original = json.loads((HERE / 'selected-pair-manifest.json').read_text())
    reference = next(e for e in original['cases'] if e['case_id'].endswith('__reference'))
    source = HERE / reference['construction']
    if sha(source) != reference['construction_sha256']:
        raise ValueError('Current selected source construction differs')
    source_construction = json.loads(source.read_text())
    frozen = ROOT / 'inputs' / HERE.name / 'assignment.json'
    if json.loads(frozen.read_text())['assignment_id'] != HERE.name:
        raise ValueError('Frozen assignment identity differs')
    source_files = {row['path']: row['content'] for row in source_construction['files']}
    source_config = json.loads(source_files['config.json'])
    if source_config['duration_s'] != 30 or source_config['rate_hz'] != 20:
        raise ValueError('Source capture timing differs')
    baseline = "'reference': (0.28, 0.75, 0.92, 0.20)"
    if source_files['runner.py'].count(baseline) != 1:
        raise ValueError('Peak-phase controller anchor differs')
    entries = []
    for value in VALUES:
        tag = f'peak-{int(value * 100):02d}'
        construction = json.loads(json.dumps(source_construction))
        files = {row['path']: row for row in construction['files']}
        config = json.loads(files['config.json']['content'])
        if [p['name'] for p in config['control_phases']] != [
                'approach', 'acceleration', 'peak', 'departure']:
            raise ValueError('Physical phase names differ')
        config['control_phases'][2]['throttle'] = value
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        files['runner.py']['content'] = source_files['runner.py'].replace(
            baseline, f"'reference': (0.28, 0.75, {value}, 0.20)")
        construction['status'] = 'unselected_physical_sweep_draft'
        construction['sweep_knob'] = {'name': 'requested_peak_phase_throttle',
                                      'unit': 'normalized_controller_request',
                                      'value': value, 'frames': [320, 439],
                                      'legal_threshold': False}
        path = OUT / tag / 'construction.json'
        write(path, construction)
        manifest = {'format': 'worker-execution-manifest',
                    'assignment_id': HERE.name,
                    'runtime_manifest_sha256': original['runtime_manifest_sha256'],
                    'status': 'unselected_physical_sweep_draft',
                    'cases': [{'case_id': reference['case_id'], 'kind': 'draft_not_selected',
                               'construction': 'construction.json',
                               'construction_sha256': sha(path), 'candidates': []}]}
        manifest_path = OUT / tag / 'manifest.json'
        write(manifest_path, manifest)
        entries.append({'tag': tag, 'value': value, 'manifest': str(manifest_path.relative_to(HERE)),
                        'manifest_sha256': sha(manifest_path),
                        'construction_sha256': sha(path)})
    index = {'format': 'c229597-unselected-peak-throttle-sweep-v1',
             'frozen_assignment_sha256': sha(frozen),
             'source_manifest_sha256': sha(HERE / 'selected-pair-manifest.json'),
             'source_construction_sha256': sha(source),
             'axis': {'name': 'requested_peak_phase_throttle',
                      'unit': 'normalized_controller_request',
                      'values': list(VALUES), 'phase_frames': [320, 439],
                      'range_rationale': 'Samples inside the existing authored reference request from ordinary 0.28 approach to 0.92 peak; Native feasibility is unverified.',
                      'spacing_rationale': '0.2 controller-request increments distinguish three engineering proposals without a legal cutoff.',
                      'observable': 'original ego_speed and ego_acceleration over the full 600-frame capture'},
             'entries': entries, 'original_native_observed': False,
             'legal_exhibition_verdict': None, 'highway_status_reviewed': False,
             'delivery_ready': False}
    write(OUT / 'index.json', index)
    print(json.dumps({'index_sha256': sha(OUT / 'index.json'),
                      'manifest_count': len(entries)}))


if __name__ == '__main__':
    build()
