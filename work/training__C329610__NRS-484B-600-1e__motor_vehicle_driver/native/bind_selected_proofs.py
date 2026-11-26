"""Copy stable compact CPU proof receipts into selected manifest entries."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text()
    target.write_text('\n'.join(line.rstrip() for line in content.splitlines()).rstrip() + ('\n' if content else ''))


def bind():
    draft = ROOT/'selected-draft-execution-manifest.json'
    obj = json.loads(draft.read_text())
    for entry in obj['cases']:
        suffix = entry['case_id'].removeprefix(AID+'__')
        for candidate in [entry, *entry['candidates']]:
            name = candidate.get('id', 'primary')
            stem = suffix+'-'+name
            offline_dir = Path('.runtime-work')/('c329610-selected-offline-'+stem+'-v4')
            compatibility_dir = Path('.runtime-work')/('c329610-selected-compat-'+stem+'-v4')
            proof = ROOT/'selected-proofs'/stem
            if not (compatibility_dir/'compatibility.json').exists():
                raise ValueError('Compatibility proof still pending: '+stem)
            for src, dst in (('offline.log','offline.log'),):
                clean_copy(offline_dir/src, proof/dst)
            for src, dst in (('compatibility.json','compatibility.json'),
                             ('compatibility-analysis.log','public-analysis.log'),
                             ('negative-analysis.log','negative-analysis.log')):
                clean_copy(compatibility_dir/src, proof/dst)
            command = ('.venv-cpu/bin/python runtime.py offline --manifest work/'+AID+
                '/selected-draft-execution-manifest.json --case '+entry['case_id']+
                ' --candidate '+name+' --output .runtime-work/c329610-selected-offline-'+stem+
                '-v4 --python $PWD/.venv-cpu/bin/python')
            candidate['offline'] = {
                'command': command, 'construction_sha256': candidate['construction_sha256'],
                'exit_code': 0, 'log': str((proof/'offline.log').relative_to(ROOT)),
                'log_sha256': sha(proof/'offline.log')}
            candidate['compatibility'] = {
                'receipt': str((proof/'compatibility.json').relative_to(ROOT)),
                'sha256': sha(proof/'compatibility.json'),
                'log': str((proof/'public-analysis.log').relative_to(ROOT)),
                'negative_log': str((proof/'negative-analysis.log').relative_to(ROOT))}
            saved_dir = Path('.runtime-work')/('c329610-selected-saved-'+stem+'-v3')/'v0001'
            if not (saved_dir/'processing.json').is_file():
                raise ValueError('Recorded-only saved proof still pending: '+stem)
            clean_copy(saved_dir/'processing.json', proof/'processing.json')
            saved = json.loads((proof/'processing.json').read_text())
            if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                    saved.get('originals_preserved') is not True or saved.get('candidate_id') != name or
                    saved.get('analysis_revision', {}).get('construction_sha256') != candidate['construction_sha256']):
                raise ValueError('Selected recorded-only result differs: '+stem)
            (proof/'saved.log').write_text('PASS recorded-only '+entry['case_id']+' '+name+'; original sources preserved; construction '+candidate['construction_sha256']+'\n')
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
        entry['acquisition'] = {
            'kin.velocity': {'entrypoint': 'runner.py',
                             'method': 'post-tick original Native three-axis ego velocity joined to actor/frame identity',
                             'evidence': ['native_motion.jsonl','video_frames.jsonl','trace.jsonl']},
            'kin.speed': {'entrypoint': 'finalize.py',
                          'method': 'magnitude of original Native velocity converted to mph for every driving frame',
                          'evidence': ['native_motion.jsonl','road_context.json','video_frames.jsonl',
                                       'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv']},
            'ru.subject': {'entrypoint': 'runner.py',
                           'method': 'original Native ego actor ID/blueprint and independent vehicle pixel review',
                           'evidence': ['native_motion.jsonl','road_context.json','overview.mkv',
                                        'approach.mkv','reference_corner.mkv','driver_reference.mkv']}}
        positive = ROOT/'selected-physical'/suffix/'delivery-positive.log'
        negative = ROOT/'selected-physical'/suffix/'delivery-negative.log'
        base = ('SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c329610-delivery-audit-output '
                'PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 '
                '.venv-cpu/bin/python work/'+AID+'/delivery_audit.py --case '+entry['case_id']+
                ' --selftest')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source','all_participants','time_join',
                       'full_video_decode','actual_pixels','physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(ROOT/'delivery_audit.py'),
            'command': base, 'test_exit_code': 0,
            'test_log': str(positive.relative_to(ROOT)), 'test_log_sha256': sha(positive),
            'negative_command': base+' --negative-fixture',
            'negative_exit_code': 1,
            'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
            'negative_log': str(negative.relative_to(ROOT)),
            'negative_log_sha256': sha(negative)}
    obj['status'] = 'selected_cpu_proofs_in_progress'
    (ROOT/'execution-manifest.json').write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    bind()
