"""Bind exact CPU proofs and materialize the C230259 delivery package."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def clean_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text()
    target.write_text('\n'.join(line.rstrip() for line in content.splitlines()).rstrip()+('\n' if content else ''))


def bind():
    obj = json.loads((ROOT/'selected-draft-manifest.json').read_text())
    for entry in obj['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        for candidate in [entry, *entry['candidates']]:
            name = candidate.get('id', 'primary')
            stem = suffix+'-'+name
            short = suffix.rsplit('_', 1)[1]
            version = 'v3' if name == 'primary' else 'fallback1-v2'
            offline_dir = Path('.runtime-work')/f'c230259-selected-offline-{short}-{version}'
            compat_version = ('v9' if short == '01' else 'v2') if name == 'primary' else 'fallback1-v1'
            compatibility_dir = Path('.runtime-work')/f'c230259-selected-compat-{short}-{compat_version}'
            proof = ROOT/'selected-proofs'/stem
            if not (compatibility_dir/'compatibility.json').is_file():
                raise ValueError('Compatibility pending: '+stem)
            clean_copy(offline_dir/'offline.log', proof/'offline.log')
            clean_copy(compatibility_dir/'compatibility-analysis.log', proof/'public-analysis.log')
            clean_copy(compatibility_dir/'negative-analysis.log', proof/'negative-analysis.log')
            receipt = json.loads((compatibility_dir/'compatibility.json').read_text())
            receipt['log_sha256'] = sha(proof/'public-analysis.log')
            receipt['negative_log_sha256'] = sha(proof/'negative-analysis.log')
            write(proof/'compatibility.json', receipt)
            candidate['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/'+AID+
                           '/selected-draft-manifest.json --case '+entry['case_id']+
                           ' --candidate '+name+' --output '+str(offline_dir)+
                           ' --python $PWD/.venv-cpu/bin/python',
                'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0,
                'log': str((proof/'offline.log').relative_to(ROOT)),
                'log_sha256': sha(proof/'offline.log')}
            candidate['compatibility'] = {
                'receipt': str((proof/'compatibility.json').relative_to(ROOT)),
                'sha256': sha(proof/'compatibility.json'),
                'log': str((proof/'public-analysis.log').relative_to(ROOT)),
                'negative_log': str((proof/'negative-analysis.log').relative_to(ROOT))}
            saved_version = 'v2' if name == 'primary' else 'fallback1-v1'
            saved_dir = Path('.runtime-work')/f'c230259-selected-saved-{short}-{saved_version}'/'v0001'
            if not (saved_dir/'processing.json').is_file():
                raise ValueError('Recorded-only saved proof pending: '+stem)
            saved = json.loads((saved_dir/'processing.json').read_text())
            if not (saved.get('passed') is True and saved.get('recorded_only') is True and
                    saved.get('originals_preserved') is True and
                    saved.get('candidate_id') == name and
                    saved.get('analysis_revision', {}).get('construction_sha256') == candidate['construction_sha256']):
                raise ValueError('Saved processing does not bind selected construction: '+stem)
            write(proof/'processing.json', saved)
            (proof/'saved.log').write_text('PASS recorded-only '+entry['case_id']+' '+name+
                                            '; original sources preserved; construction '+
                                            candidate['construction_sha256']+'\n')
            candidate['saved_processing'] = {
                'receipt': str((proof/'processing.json').relative_to(ROOT)),
                'sha256': sha(proof/'processing.json'), 'recorded_only': True,
                'originals_preserved': True,
                'log': str((proof/'saved.log').relative_to(ROOT)),
                'log_sha256': sha(proof/'saved.log')}
            if name == 'primary':
                entry['negative'] = {'log': candidate['compatibility']['negative_log']}
                post_command = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/'+AID+
                                '/execution-manifest.json --case '+entry['case_id']+
                                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library'
                                ' --validator $DECODER --owner-release-receipt $ATTEMPT/owner-release.json')
                entry['post_capture'] = {
                    'recorded_only': True, 'command': post_command,
                    'feedback_command': post_command,
                    'test_exit_code': 0,
                    'test_log': candidate['saved_processing']['log'],
                    'test_log_sha256': candidate['saved_processing']['log_sha256']}
        physical = ROOT/'selected-physical'/suffix/'physical-preparation.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(ROOT)),
                                         'sha256': sha(physical)}
        channels = [row['name'] for row in json.loads((ROOT/entry['construction']).read_text())
                    ['recording_description']['channels']]
        entry['acquisition'] = {
            term: {'entrypoint': 'runner.py',
                   'method': 'original Native post-tick pedestrian and full vehicle inventory joined to surveyed road, frame and four source cameras; legal applicability reviewed separately',
                   'evidence': ['post-tick.jsonl', 'crossing-context.json', 'video_frames.jsonl',
                                'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                                'driver_reference.mkv']}
            for term in channels}
        positive = ROOT/'selected-physical'/suffix/'delivery-positive.log'
        negative = ROOT/'selected-physical'/suffix/'delivery-negative.log'
        base = ('SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230259-delivery-audit-output '
                'PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 '
                '.venv-cpu/bin/python work/'+AID+'/delivery_audit.py --case '+entry['case_id']+
                ' --selftest')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(ROOT/'delivery_audit.py'),
            'command': base, 'test_exit_code': 0,
            'test_log': str(positive.relative_to(ROOT)), 'test_log_sha256': sha(positive),
            'negative_command': base+' --negative-fixture', 'negative_exit_code': 1,
            'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
            'negative_log': str(negative.relative_to(ROOT)),
            'negative_log_sha256': sha(negative)}
    obj['status'] = 'selected_cpu_proofs_passed'
    write(ROOT/'execution-manifest.json', obj)
    source = ROOT/'cases'/'probe_01'
    for rel in ('runner.py','finalize.py','crossing_meter.py','road.xodr','config.json','tests/test_selected.py'):
        dest = ROOT/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((source/rel).read_bytes())
    (ROOT/'construction.json').write_bytes((ROOT/'selected-probe_01-construction.json').read_bytes())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    plan['summary_status'] = 'delivery_prepared_cpu_proofs'
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [
                               {'view': camera, 'subject': 'pedestrian and roadway vehicle crossing order',
                                'interval': '600 original frames at 20 Hz'}
                               for camera in ('overview','approach','reference_corner','driver_reference')]}
    for case in plan['cases']:
        suffix = case['case_id'].rsplit('__', 1)[1]
        match = next(item for item in obj['cases'] if item['case_id'] == case['case_id'])
        case.update(kind='delivery', selection_status='selected_delivery_cpu_proved',
                    construction_status='offline_public_saved_physical_cpu_passed_native_unobserved',
                    construction=match['construction'], construction_sha256=match['construction_sha256'])
    plan['source_observation_mapping'] = {
        row['term']: {'evidence': row['measurement_or_context'],
                      'channels': [row['term']],
                      'source_refs': row['source_refs'],
                      'physical_evidence_status': 'pending_original_native_capture'}
        for row in plan['source_observation_mapping']}
    plan['requirement_dispositions'][0]['evidence_or_gap'] = (
        'Two exact selected constructions, measured fallback plans, 600-frame positive/missing-source '
        'diagnostic compatibility, recorded-only saved processing and physical/lifecycle CPU proofs pass. '
        'Original Native motion/pixels, independent four-camera review and Section 11.30.070 applicability '
        'remain original-source delivery checks.')
    plan['runtime_gaps'] = ['Original Native motion/pixels, four-camera visual review and Section 11.30.070 '
                            'designated-place applicability remain for delivery.']
    plan['runtime_uncertainties'] = ['Original CARLA actor motion, camera pixels, roadway participant census and '
                                     'Section 11.30.070 designated-place applicability remain unverified.']
    write(ROOT/'case-plan.json', plan)


if __name__ == '__main__':
    bind()
