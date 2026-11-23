"""Regenerate two exact draft primary bundles from the reviewed native sources.

This does not select either case for delivery or claim compatibility.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
SOURCE = ('runner.py', 'signal_display.py', 'source_capture.py', 'source_review.py',
          'road_entry_measure.py', 'saved_source_analysis.py',
          'finalize_saved.py', 'test_offline.py')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    template = json.loads((HERE / 'config.json').read_text())
    entries = []
    for suffix in ('reference', 'contrast'):
        case_id = ASSIGNMENT + '__' + suffix
        config = json.loads(json.dumps(template))
        config['case_id'] = case_id
        config['selected_case_id'] = case_id
        config['case']['case_id'] = case_id
        config['case_suffix'] = suffix
        config['pedestrian_enters_highway_requested'] = suffix == 'contrast'
        files = []
        for name in SOURCE:
            path = 'tests/test_offline.py' if name == 'test_offline.py' else name
            files.append({'path': path, 'content': (HERE / name).read_text()})
        files.append({'path': 'config.json',
                      'content': json.dumps(config, indent=2) + '\n'})
        construction = {
            'case_id': case_id, 'cell_id': 'C228133',
            'law_id': 'NRS-484B-307-9c', 'actor': 'pedestrian',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': config['recording_description'],
            'measurement_plan': 'Saved road-entry measurement from source-hashed Native rows; all governing signal, other-device and legal highway facts require independent review.',
            'static_checks': ['full 600-frame duration', 'four source cameras',
                              'exact case identity', 'only entry comparison changes'],
            'termination_rules': ['600 synchronized Native frames or explicit failure'],
            'mechanisms': ['two distinct Native signal actors',
                           '35-segment red-disc and green-right-arrow debug display',
                           'walker start and requested movement',
                           'source-hashed original camera frames'],
            'status': 'draft_cpu_offline_only',
        }
        path = HERE.parent / 'draft-primary' / suffix / 'construction.json'
        write(path, construction)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE.parent)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                           'reason': 'Native signal pair, arrow pixels, pedestrian path and camera framing need physical review'},
                        'measurement_procedure': {
                            'entrypoint': 'finalize_saved.py',
                            'output_schema': 'c228133-saved-analysis-v1'},
                        'candidates': []})
    batch = json.loads((HERE.parents[2] / 'batch.json').read_text())
    manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'draft_cpu_offline_only', 'cases': entries,
    }
    path = HERE.parent / 'draft-primary-manifest.json'
    write(path, manifest)
    return {'manifest': str(path), 'cases': [x['case_id'] for x in entries],
            'construction_sha256': [x['construction_sha256'] for x in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
