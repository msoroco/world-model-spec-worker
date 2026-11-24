"""Bind tested exact-case delivery contracts in an unselected draft manifest."""
import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work' / 'owner150142' / 'binding'))
sys.path.insert(0, str(REPO / 'runtime'))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.physical_preparation import validate as validate_physical


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    index = json.loads((HERE / 'current-exact-case-delivery-cpu-index.json').read_text())
    if index['passed'] is not True or index['script_sha256'] != sha(HERE / index['script']):
        raise ValueError('Exact-case delivery proof index changed')
    rows = {row['case_id']: row for row in index['cases']}
    physical_index = json.loads((HERE / 'current-physical-preparation-cpu-index.json').read_text())
    if physical_index['passed'] is not True:
        raise ValueError('Physical CPU index incomplete')
    physical_rows = {row['case_id']: row for row in physical_index['cases']}
    short_index = json.loads((HERE / 'current-short-selected-saved-index.json').read_text())
    if short_index['passed'] is not True or short_index['manifest_sha256'] != sha(HERE / 'execution-manifest.json'):
        raise ValueError('Selected short recorded-only index changed')
    short_rows = {HERE.name + '__' + row['case']: row for row in short_index['rows']}
    short_manifest = json.loads((HERE / 'current-short-bound-draft-manifest.json').read_text())
    short_bindings = {row['case_id']: row for row in short_manifest['cases']
                      if row.get('compatibility')}
    if set(short_bindings) != set(short_rows):
        raise ValueError('Short public compatibility coverage differs from saved coverage')
    if len(rows) != len(manifest['cases']) == 30:
        raise ValueError('Exact-case delivery rows incomplete')
    if set(physical_rows) != set(rows):
        raise ValueError('Exact-case physical rows incomplete')
    for entry in manifest['cases']:
        case = entry['case_id']
        row = rows[case]
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': index['script'], 'script_sha256': index['script_sha256'],
            'command': row['positive']['command'],
            'test_exit_code': row['positive']['exit_code'],
            'test_log': row['positive']['log'],
            'test_log_sha256': row['positive']['log_sha256'],
            'negative_command': row['negative']['command'],
            'negative_exit_code': row['negative']['exit_code'],
            'negative_expected_error':
                'Missing independent original Native and physical acceptance source',
            'negative_log': row['negative']['log'],
            'negative_log_sha256': row['negative']['log_sha256']}
        validate_case(HERE, entry, ('full-train',))
        physical = physical_rows[case]
        entry['physical_preparation'] = {'receipt': physical['receipt'],
                                         'sha256': physical['sha256']}
        validate_physical(REPO, HERE, entry)
        construction = json.loads((HERE / entry['construction']).read_text())
        files = {item['path'] for item in construction['files']}
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        if 'runner.py' not in files:
            raise ValueError('Native acquisition runner missing: ' + case)
        methods = {
            'ego_pose': ('Native ego transform and body readback at each world tick',
                         'native-raw-actors.jsonl, trace.jsonl, video_frames.jsonl'),
            'ego_speed': ('Native ego velocity readback at each world tick',
                          'native-raw-actors.jsonl, trace.jsonl'),
            'red_curb_stop_or_park': (
                'Original ego body and velocity joined to Native red-paint map readback',
                'native-raw-actors.jsonl, native-map-readback.json, video_frames.jsonl'),
            'four_source_views': (
                'Four Native RGB sensors frame joined to each world tick and encoded separately',
                'overview.mkv, approach.mkv, reference_corner.mkv, '
                'driver_reference.mkv, video_frames.jsonl')}
        required = set(config.get('required_atoms', [])) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        if not required <= set(methods):
            raise ValueError('Unknown selected acquisition atom: ' + case)
        entry['acquisition'] = {
            atom: {'entrypoint': 'runner.py', 'method': methods[atom][0],
                   'evidence': methods[atom][1]} for atom in sorted(required)}
        if case in short_rows:
            prior = short_bindings[case]
            if prior['construction_sha256'] != entry['construction_sha256']:
                raise ValueError('Short public construction differs: ' + case)
            for key in ('compatibility', 'negative'):
                entry[key] = prior[key]
            if sha(HERE / entry['compatibility']['receipt']) != entry['compatibility']['sha256']:
                raise ValueError('Short primary public receipt changed: ' + case)
            prior_candidates = {item['id']: item for item in prior['candidates']}
            for candidate in entry['candidates']:
                old = prior_candidates[candidate['id']]
                if old['construction_sha256'] != candidate['construction_sha256']:
                    raise ValueError('Short fallback construction differs: ' + case)
                candidate['compatibility'] = old['compatibility']
                if sha(HERE / candidate['compatibility']['receipt']) != candidate['compatibility']['sha256']:
                    raise ValueError('Short fallback public receipt changed: ' + case)
            saved = short_rows[case]
            if (saved['exit_code'] != 0 or
                    saved['construction_sha256'] != entry['construction_sha256'] or
                    saved['manifest_sha256'] != sha(HERE / 'execution-manifest.json')):
                raise ValueError('Short saved proof differs: ' + case)
            entry['post_capture'] = {
                'recorded_only': True,
                'command': '.venv-cpu/bin/python runtime.py process-saved '
                    '--manifest work/' + HERE.name + '/execution-manifest.json '
                    '--case ' + case + ' --attempt "$SEALED_ATTEMPT" '
                    '--output "$PROCESSED_OUT" --library runtime/library '
                    '--validator "$LEAN_VALIDATOR"',
                'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                'test_exit_code': 0,
                'test_log': 'current-short-selected-saved-batch.log',
                'test_log_sha256': sha(HERE / 'current-short-selected-saved-batch.log')}
    path = HERE / 'current-delivery-bound-draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'cases': len(rows), 'draft_sha256': sha(path),
            'main_manifest_sha256': sha(HERE / 'execution-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
