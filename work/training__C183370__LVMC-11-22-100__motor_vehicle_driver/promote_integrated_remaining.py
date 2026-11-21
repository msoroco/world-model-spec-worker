"""Select the remaining source-derived bundles without claiming CPU readiness."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
DRAFT = HERE / 'update153-integrated-all-text1-manifest.json'
PLAN = HERE / 'case-plan.json'
PROPOSAL = HERE / 'proposals/cases.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
REQUIRED_SOURCES = 'native-actors.jsonl, video_frames.jsonl and live-readback.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def relative(path):
    return str(path.relative_to(HERE))


def physical(entry, short):
    target = HERE / 'selected-physical-preparation' / (short + '-integrated')
    target.mkdir(parents=True, exist_ok=True)
    fixtures, lifecycle = [], None
    for kind in KINDS:
        result, log = target / (kind + '.json'), target / (kind + '.log')
        if result.exists() or log.exists():
            raise ValueError('Retain prior physical fixture: ' + short + '/' + kind)
        command = [sys.executable, str(HERE / 'run_physical_fixture.py'),
                   '--manifest', str(DRAFT), '--case', entry['case_id'],
                   '--kind', kind, '--output', str(result)]
        completed = subprocess.run(command, cwd=REPO, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write_text(completed.stdout)
        if completed.returncode:
            raise RuntimeError(f'{short}/{kind}: {completed.stdout}')
        row = {'command': ' '.join(command), 'exit_code': 0,
               'log': relative(log), 'log_sha256': sha(log),
               'result': relative(result), 'result_sha256': sha(result)}
        if kind == 'lifecycle':
            lifecycle = dict(row, events=EVENTS)
        else:
            fixtures.append(dict(row, kind=kind))
    receipt = target / 'proof.json'
    write(receipt, {'format': 'c183370-selected-physical-cpu-fixtures-v1',
                    'case_id': entry['case_id'],
                    'construction_sha256': entry['construction_sha256'],
                    'fixtures': fixtures, 'lifecycle': lifecycle,
                    'fixtures_are_cpu_mocks': True,
                    'original_native_motion_verified': False})
    return {'receipt': relative(receipt), 'sha256': sha(receipt)}


def acquisition_for_integrated(old):
    result = copy.deepcopy(old)
    result['ego_speed'] = {
        'entrypoint': 'native/mandatory_channels.py',
        'method': 'derive per-frame ego speed from retained Native velocity and verify reported speed consistency',
        'evidence': 'native-actors.jsonl velocity and speed joined to video_frames.jsonl and live-readback.json'}
    result['newly_laid_footprint_contact'] = {
        'entrypoint': 'native/mandatory_channels.py',
        'method': 'intersect retained eight-vertex ego body hull with surveyed pavement polygon; retain surface status as unverified',
        'evidence': 'native-actors.jsonl body vertices and live-readback.json surveyed polygon joined to video_frames.jsonl'}
    result['drive_over_warned_new_pavement'] = {
        'entrypoint': 'native/mandatory_channels.py',
        'method': 'derive structured body-contact and warning-person source evidence while leaving warning act, surface age and legal condition unverified',
        'evidence': REQUIRED_SOURCES + ' with source hashes'}
    return result


def main():
    if sha(MANIFEST) != '753dff4c40751af99c5da01e82aec6596ed39d23c15a6ed563cb81974d1593fc':
        raise ValueError('Selected manifest changed; review selection again')
    if sha(DRAFT) != '093a0fa3511b2b7e50827b823180765098b4b63c3d3247ab5ae44802137da365':
        raise ValueError('Integrated draft changed; review selection again')
    current, draft = read(MANIFEST), read(DRAFT)
    plan, proposal = read(PLAN), read(PROPOSAL)
    old = {'manifest': current, 'plan': plan, 'proposal': proposal,
           'manifest_sha256': sha(MANIFEST), 'plan_sha256': sha(PLAN),
           'proposal_sha256': sha(PROPOSAL)}
    snapshot = HERE / 'update155-before-remaining-integration.json'
    if snapshot.exists():
        raise ValueError('Retain prior selected snapshot')
    by_case = {row['case_id']: row for row in draft['cases']}
    promoted = []
    for entry in current['cases']:
        short = entry['case_id'].removeprefix(HERE.name + '__')
        if short == 'reference':
            continue
        source = by_case[entry['case_id']]
        entry['construction'] = source['construction']
        entry['construction_sha256'] = source['construction_sha256']
        entry['candidates'] = copy.deepcopy(source['candidates'])
        if 'employee_exception_' in short:
            entry['measurement_contract'] = source['measurement_contract']
        entry['acquisition'] = acquisition_for_integrated(entry['acquisition'])
        entry['physical_preparation'] = physical(entry, short)
        entry['offline'] = {'exit_code': None,
                            'construction_sha256': entry['construction_sha256'],
                            'status': 'pending_exact_selected_manifest_proof'}
        entry['compatibility'] = {'status': 'pending_exact_selected_manifest_proof'}
        entry['negative'] = {'status': 'pending_exact_selected_manifest_proof'}
        entry['post_capture']['test_exit_code'] = None
        entry['post_capture'].pop('test_log', None)
        entry['post_capture'].pop('test_log_sha256', None)
        entry['delivery_acceptance'] = {'case_id': entry['case_id'],
                                        'status': 'pending_integrated_selected_audit'}
        entry['candidate_offline_status'] = 'pending_exact_selected_manifest_proof'
        for candidate in entry['candidates']:
            candidate['offline'] = {'exit_code': None,
                                    'construction_sha256': candidate['construction_sha256'],
                                    'status': 'pending_exact_selected_manifest_proof'}
            candidate['compatibility'] = {'status': 'pending_exact_selected_manifest_proof'}
        description = read(HERE / entry['construction'])['recording_description']
        target = next(c for c in proposal['cases'] if c['case_id'] == entry['case_id'])
        target['recording_description'] = description
        promoted.append(short)
    if len(promoted) != 11:
        raise ValueError('Expected eleven remaining exact cases')
    text_one = next(d for d in plan['requirement_dispositions']
                    if d['requirement'].startswith('text-1'))
    if text_one['status'] != 'exception_pending':
        raise ValueError('Text-1 selection changed')
    text_one['status'] = 'selected_required'
    text_one['evidence_or_gap'] = (
        'Selected source-bound employee activity context is measured from retained actor identity and distinct route references; '
        'actual employment, active paving and legal exception applicability remain unverified pending original Native review.')
    write(snapshot, old)
    write(PLAN, plan)
    write(PROPOSAL, proposal)
    write(MANIFEST, current)
    print(json.dumps({'promoted': promoted,
                      'manifest_sha256': sha(MANIFEST),
                      'plan_sha256': sha(PLAN),
                      'proposal_sha256': sha(PROPOSAL),
                      'ready': False}, sort_keys=True))


if __name__ == '__main__':
    main()
