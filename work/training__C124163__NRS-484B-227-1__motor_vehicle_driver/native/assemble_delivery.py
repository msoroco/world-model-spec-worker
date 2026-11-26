"""Bind exact CPU receipts to the selected NRS 484B.227(1) package."""
import hashlib
import json
import shutil
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
SCRATCH = REPO / '.runtime-work/c124163-median'
PROOFS = PACKAGE / 'native/proofs'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def rel(path):
    return str(Path(path).relative_to(PACKAGE))


def copied(source, name):
    target = PROOFS / name
    shutil.copyfile(source, target)
    return target


def bind_candidate(entry, candidate, suffix, candidate_id):
    selected = entry if candidate_id == 'primary' else candidate
    output = SCRATCH / f'compat-{suffix}-{candidate_id}-v4'
    offline = SCRATCH / f'offline-{suffix}-{candidate_id}-v4/offline.log'
    receipt = copied(output / 'compatibility.json',
                     f'{suffix}-{candidate_id}-compatibility.json')
    analysis = copied(output / 'compatibility-analysis.log',
                      f'{suffix}-{candidate_id}-analysis.log')
    negative = copied(output / 'negative-analysis.log',
                      f'{suffix}-{candidate_id}-negative.log')
    offline_log = copied(offline, f'{suffix}-{candidate_id}-offline.log')
    selected['compatibility'] = {
        'receipt': rel(receipt), 'sha256': sha(receipt),
        'log': rel(analysis), 'negative_log': rel(negative)}
    command = ('.venv-cpu/bin/python runtime.py offline --manifest '
               f'work/{PACKAGE.name}/draft-native-manifest.json --case '
               f'{entry["case_id"]} --output '
               f'.runtime-work/c124163-median/offline-{suffix}-{candidate_id}-v4 '
               '--python $PWD/.venv-cpu/bin/python')
    if candidate_id != 'primary':
        command += f' --candidate {candidate_id}'
    selected['offline'] = {'exit_code': 0,
        'construction_sha256': selected['construction_sha256'],
        'command': command, 'log': rel(offline_log),
        'log_sha256': sha(offline_log)}
    return negative


def main():
    manifest = json.loads((PACKAGE / 'draft-native-manifest.json').read_text())
    manifest['status'] = 'delivery_prepared'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(PACKAGE.name + '__')
        negative = bind_candidate(entry, None, suffix, 'primary')
        entry['negative'] = {'log': rel(negative)}
        for candidate in entry.get('candidates', []):
            bind_candidate(entry, candidate, suffix, candidate['id'])
        physical = PROOFS / f'{case}-physical-preparation.json'
        entry['physical_preparation'] = {'receipt': rel(physical),
                                         'sha256': sha(physical)}
        saved = SCRATCH / f'saved-{suffix}-primary-v4/v0001/processing.json'
        saved_proof = copied(saved, f'{suffix}-saved-processing.json')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': ('.venv-cpu/bin/python runtime.py process-saved --manifest '
                        f'work/{PACKAGE.name}/draft-native-manifest.json --case '
                        f'{case} --attempt $CAPTURE_OUTPUT --output '
                        '$POSTPROCESS_OUTPUT --library runtime/library '
                        '--validator $VALIDATOR'),
            'feedback_command': 'cat $POSTPROCESS_OUTPUT/v0001/processing.json',
            'test_exit_code': 0, 'test_log': rel(saved_proof),
            'test_log_sha256': sha(saved_proof), 'diagnostic_fixture': True}
        positive = PROOFS / f'{suffix}-delivery-positive.log'
        rejected = PROOFS / f'{suffix}-delivery-negative.log'
        audit = PACKAGE / 'delivery_audit.py'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(audit),
            'command': (f'.venv-cpu/bin/python work/{PACKAGE.name}/delivery_audit.py '
                        f'--case {case} --self-test'),
            'test_exit_code': 0, 'test_log': rel(positive),
            'test_log_sha256': sha(positive),
            'negative_command': (f'.venv-cpu/bin/python work/{PACKAGE.name}/delivery_audit.py '
                                 f'--case {case} --self-test --negative'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Exact original Native result missing',
            'negative_log': rel(rejected),
            'negative_log_sha256': sha(rejected)}
        entry['acquisition'] = {
            'ego_pose': {'entrypoint': 'runner.py',
                         'method': 'original Native transform and full-body vertices',
                         'evidence': 'native-median.jsonl and body_history.jsonl'},
            'median_geometry': {'entrypoint': 'runner.py',
                         'method': 'original roadway and median object readback',
                         'evidence': 'median-context.json'},
            'roadway_occupancy': {'entrypoint': 'finalize.py',
                         'method': 'saved full-body overlap with both original roadway polygons',
                         'evidence': 'native-median.jsonl and channels/roadway_occupancy.jsonl'},
            'turn_history': {'entrypoint': 'runner.py',
                         'method': 'original body, heading, speed and route history',
                         'evidence': 'native-median.jsonl and body_history.jsonl'},
            'administrative_context': {'entrypoint': 'runner.py',
                         'method': 'pending original public-authority source review',
                         'evidence': 'median-context.json and source-review.json'},
            'median_crossing_measurement': {'entrypoint': 'finalize.py',
                         'method': 'source-bound full-body overlap with median sections',
                         'evidence': 'native-median.jsonl and channels/median_crossing_measurement.jsonl'}}
        entry['delivery_readiness'] = 'selected_cpu_prepared_original_review_pending'
    put(PACKAGE / 'execution-manifest.json', manifest)
    primary = json.loads((PACKAGE / manifest['cases'][0]['construction']).read_text())
    for item in primary['files']:
        if not item.get('source'):
            target = PACKAGE / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
    shutil.copyfile(PACKAGE / 'native/runner.py', PACKAGE / 'runner.py')
    put(PACKAGE / 'construction.json', primary)
    return {'cases': len(manifest['cases']),
            'manifest_sha256': sha(PACKAGE / 'execution-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
