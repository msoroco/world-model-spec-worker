"""Bind physical classifier and capture-lifecycle CPU fixtures for paired cases."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for suffix in ('signal_advance_100_at', 'signal_advance_100_omitted'):
    draft = folder / 'cases' / suffix
    case = folder.name + '__' + suffix
    manifest = json.loads((draft / 'draft-manifest.json').read_text())['cases'][0]
    if manifest['case_id'] != case:
        raise ValueError('Physical fixture case identity differs')
    root = draft / 'physical-proofs'
    fixtures = []
    for kind, expected in (('complete_motion', 'met'),
                           ('incomplete_motion', 'not_met'),
                           ('missing_evidence', 'unverified')):
        path, log = root / (kind + '.json'), root / (kind + '.log')
        result = json.loads(path.read_text())
        if (result['physical_checks']['maneuver']['status'] != expected or
                result.get('diagnostic_fixture') is not True or
                result.get('physical_acceptance_claimed') is not False):
            raise ValueError('Physical classifier fixture incomplete: ' + suffix + '/' + kind)
        command = (f'.venv-cpu/bin/python work/{folder.name}/inside_physical_fixture_proof.py '
                   f'--manifest work/{folder.name}/cases/{suffix}/draft-manifest.json '
                   f'--case {case} --kind {kind} '
                   f'--output work/{folder.name}/cases/{suffix}/physical-proofs/{kind}.json')
        fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                         'log': str(log.relative_to(folder)), 'log_sha256': sha(log),
                         'result': str(path.relative_to(folder)), 'result_sha256': sha(path)})
    lifecycle_path = root / 'lifecycle.json'
    lifecycle_log = root / 'lifecycle.log'
    lifecycle = json.loads(lifecycle_path.read_text())
    expected_events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                       'native_exit', 'owner_released', 'saved_processing_started']
    if lifecycle.get('events') != expected_events or lifecycle.get('diagnostic_fixture') is not True:
        raise ValueError('Capture lifecycle fixture incomplete: ' + suffix)
    command = (f'.venv-cpu/bin/python work/{folder.name}/inside_physical_fixture_proof.py '
               f'--manifest work/{folder.name}/cases/{suffix}/draft-manifest.json '
               f'--case {case} --kind lifecycle '
               f'--output work/{folder.name}/cases/{suffix}/physical-proofs/lifecycle.json')
    receipt = {'format': 'worker-physical-preparation', 'case_id': case,
               'construction_sha256': manifest['construction_sha256'],
               'fixtures': fixtures,
               'lifecycle': {'events': expected_events, 'exit_code': 0,
                             'command': command,
                             'log': str(lifecycle_log.relative_to(folder)),
                             'log_sha256': sha(lifecycle_log),
                             'result': str(lifecycle_path.relative_to(folder)),
                             'result_sha256': sha(lifecycle_path)}}
    (root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'physical_fixture_kinds': len(fixtures),
                      'lifecycle_checked': True, 'physical_acceptance_claimed': False}))
