"""Bind current C125751 CPU proofs to the exact selected constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = REPO / 'work/testing__C125697__NRS-484B-250-1__motor_vehicle_driver'
NAMES = {
    'source_verified_signal_exclusion': 'operative_signal_exclusion',
    'source_verified_off_subsection_4': 'off_other_enters_first',
    'source_verified_opposite_intends_left': 'opposite_left_exception',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy_text(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(Path(source).read_text())
    return str(destination.relative_to(ROOT))


def bind():
    manifest = json.loads((ROOT / 'review-draft-manifest.json').read_text())
    prior = json.loads((OLD / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].split('__')[-1]
        previous = next(c for c in prior['cases'] if c['case_id'].endswith('__' + NAMES[name]))
        folder = ROOT if name == 'source_verified_signal_exclusion' else ROOT / 'cases' / name
        proof = folder / 'proofs'
        compat_scratch = REPO / '.runtime-work' / ('c125751-compat-v3-' + name)
        fallback_scratch = REPO / '.runtime-work' / ('c125751-fallback-compat-' + name)
        primary_log = ROOT / (name + '-primary-offline.log')
        compatibility_log = ROOT / (name + '-cpu-compatibility-proof.log')
        saved_log = ROOT / (name + '-process-saved-proof.log')
        fallback_log = ROOT / (name + '-fallback1-offline.log')
        fallback_compat_log = ROOT / (name + '-fallback1-cpu-compatibility.log')
        fallback_saved_log = ROOT / (name + '-fallback1-process-saved.log')
        analysis = copy_text(compat_scratch / 'compatibility-analysis.log', proof / 'analysis.log')
        negative = copy_text(compat_scratch / 'negative-analysis.log', proof / 'negative-analysis.log')
        receipt = copy_text(compat_scratch / 'compatibility.json', proof / 'receipt.json')
        saved = copy_text(saved_log, proof / 'saved-receipt.json')
        fallback_analysis = copy_text(fallback_scratch / 'compatibility-analysis.log', proof / 'fallback-analysis.log')
        fallback_negative = copy_text(fallback_scratch / 'negative-analysis.log', proof / 'fallback-negative-analysis.log')
        fallback_receipt = copy_text(fallback_scratch / 'compatibility.json', proof / 'fallback-receipt.json')
        fallback_saved = copy_text(fallback_saved_log, proof / 'fallback-saved-receipt.json')
        entry['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/' + ('c125751-offline-v3-opposite' if name == 'source_verified_opposite_intends_left' else 'c125751-offline-v2-' + name) + ' --python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': str(primary_log.relative_to(ROOT)), 'log_sha256': sha(primary_log),
        }
        entry['compatibility'] = {'receipt': receipt, 'sha256': sha(ROOT / receipt),
                                  'log': analysis, 'negative_log': negative,
                                  'replay_command': '.venv-cpu/bin/python runtime.py compatibility --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/c125751-compat-v3-' + name + ' --library runtime/library --validator .runtime-work/c376646-validator/.lake/build/bin/adapterCheck'}
        entry['negative'] = {'log': negative}
        entry['saved_processing_diagnostic'] = {
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --attempt .runtime-work/c125751-compat-v3-' + name + ' --output .runtime-work/c125751-saved-v3-' + name + ' --library runtime/library --validator .runtime-work/c376646-validator/.lake/build/bin/adapterCheck',
            'exit_code': 0, 'receipt': saved, 'sha256': sha(ROOT / saved),
            'recorded_only': True, 'scope': 'synthetic fixture; physical review pending',
        }
        entry['post_capture'] = {
            'recorded_only': True,
            'command': entry['saved_processing_diagnostic']['command'],
            'feedback_command': 'cat .runtime-work/c125751-saved-v3-' + name + '/v0001/feedback.json',
            'test_log': str(saved_log.relative_to(ROOT)),
            'test_log_sha256': sha(saved_log),
            'test_exit_code': 0,
        }
        entry['native_handoff'] = previous['native_handoff']
        entry['acquisition'] = previous['acquisition']
        fallback = entry['candidates'][0]
        fallback['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --candidate fallback1 --output .runtime-work/c125751-fallback-offline-' + name + ' --python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': fallback['construction_sha256'],
            'log': str(fallback_log.relative_to(ROOT)), 'log_sha256': sha(fallback_log),
        }
        fallback['compatibility'] = {'receipt': fallback_receipt,
                                     'sha256': sha(ROOT / fallback_receipt),
                                     'log': fallback_analysis, 'negative_log': fallback_negative,
                                     'replay_command': '.venv-cpu/bin/python runtime.py compatibility --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --candidate fallback1 --output .runtime-work/c125751-fallback-compat-' + name + ' --library runtime/library --validator .runtime-work/c376646-validator/.lake/build/bin/adapterCheck'}
        fallback['saved_processing_diagnostic'] = {'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ROOT.name + '/review-draft-manifest.json --case ' + entry['case_id'] + ' --attempt .runtime-work/c125751-fallback-compat-' + name + ' --output .runtime-work/c125751-fallback-saved-' + name + ' --library runtime/library --validator .runtime-work/c376646-validator/.lake/build/bin/adapterCheck',
                                                   'receipt': fallback_saved,
                                                   'sha256': sha(ROOT / fallback_saved),
                                                   'recorded_only': True, 'exit_code': 0}
        fixture_folder = ROOT / 'physical-proofs' / name
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result_path = fixture_folder / (kind + '.json')
            log_path = fixture_folder / (kind + '.log')
            fixtures.append({
                'kind': kind,
                'command': '.venv-cpu/bin/python work/' + ROOT.name + '/physical_motion_fixture.py --case ' + entry['case_id'] + ' --kind ' + kind + ' --output work/' + ROOT.name + '/physical-proofs/' + name + '/' + kind + '.json',
                'exit_code': 0,
                'log': str(log_path.relative_to(ROOT)), 'log_sha256': sha(log_path),
                'result': str(result_path.relative_to(ROOT)), 'result_sha256': sha(result_path),
            })
        lifecycle_log = fixture_folder / 'lifecycle.log'
        lifecycle = json.loads((fixture_folder / 'lifecycle.json').read_text())
        physical = {
            'format': 'worker-c125751-physical-preparation',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture_only': True,
            'fixture_script': 'physical_motion_fixture.py',
            'fixture_script_sha256': sha(ROOT / 'physical_motion_fixture.py'),
            'fixtures': fixtures,
            'lifecycle': {
                'kind': 'lifecycle',
                'command': '.venv-cpu/bin/python work/' + ROOT.name + '/physical_motion_fixture.py --case ' + entry['case_id'] + ' --kind lifecycle --output work/' + ROOT.name + '/physical-proofs/' + name + '/lifecycle.json',
                'exit_code': 0,
                'log': str(lifecycle_log.relative_to(ROOT)), 'log_sha256': sha(lifecycle_log),
                'result': str((fixture_folder / 'lifecycle.json').relative_to(ROOT)),
                'result_sha256': sha(fixture_folder / 'lifecycle.json'),
                'events': lifecycle['events'],
            },
            'physical_acceptance_claimed': False,
        }
        physical_path = fixture_folder / 'receipt.json'
        physical_path.write_text(json.dumps(physical, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(physical_path.relative_to(ROOT)),
                                         'sha256': sha(physical_path)}
        delivery_positive = ROOT / (name + '-delivery-positive.log')
        delivery_negative = ROOT / (name + '-delivery-negative.log')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'],
            'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_acceptance.py',
            'script_sha256': sha(ROOT / 'delivery_acceptance.py'),
            'command': '.venv-cpu/bin/python work/' + ROOT.name + '/prove_delivery_acceptance.py --case ' + entry['case_id'] + ' --mode positive',
            'test_log': str(delivery_positive.relative_to(ROOT)),
            'test_log_sha256': sha(delivery_positive), 'test_exit_code': 0,
            'negative_command': '.venv-cpu/bin/python work/' + ROOT.name + '/prove_delivery_acceptance.py --case ' + entry['case_id'] + ' --mode negative',
            'negative_log': str(delivery_negative.relative_to(ROOT)),
            'negative_log_sha256': sha(delivery_negative), 'negative_exit_code': 1,
            'negative_expected_error': 'Physical completion source changed',
            'proof_scope': 'Diagnostic CPU boundary only; Native and pixels require local review',
        }
    manifest['status'] = 'candidate_cpu_proven'
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print('bound', len(bind()['cases']), 'current-runtime cases')
