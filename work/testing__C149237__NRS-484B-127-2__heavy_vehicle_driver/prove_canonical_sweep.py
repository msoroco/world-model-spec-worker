"""Run current canonical exact software proofs for selected gap sweep plans."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'execution-manifest.json'
LIBRARY = ROOT/'runtime/library'
VALIDATOR = ROOT/'.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, args):
    log = HERE/(name+'.log')
    with log.open('w') as stream:
        result = subprocess.run([sys.executable, str(ROOT/'runtime.py'), *args],
                                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=600)
    if result.returncode:
        raise ValueError(name+' failed: '+str(log))
    return {'command': ' '.join([str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'), *args]),
            'exit_code': 0, 'log': log.name, 'sha256': sha(log)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    result_path = HERE/'result.json'
    result = json.loads(result_path.read_text())
    new_tests = []
    for meters in (120, 200):
        suffix = f'conditions_gap_{meters}m'
        case_id = HERE.name+'__'+suffix
        entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            tag = suffix+'-'+candidate+'-canonical'
            option = [] if candidate == 'primary' else ['--candidate', candidate]
            case_args = ['--manifest', str(MANIFEST), '--case', case_id]
            output_base = ROOT/'.runtime-work'/('c149237-'+tag)
            offline = output_base.with_name(output_base.name+'-offline-v1')
            compat = output_base.with_name(output_base.name+'-compat-v1')
            saved = output_base.with_name(output_base.name+'-saved-v1')
            offline_proof = run(tag+'-offline', ['offline',*case_args,*option,'--output',str(offline)])
            compat_proof = run(tag+'-compat', ['compatibility',*case_args,*option,'--output',str(compat),
                                               '--library',str(LIBRARY),'--validator',str(VALIDATOR)])
            saved_proof = run(tag+'-saved', ['process-saved',*case_args,'--attempt',str(compat),
                                            '--output',str(saved),'--library',str(LIBRARY),'--validator',str(VALIDATOR)])
            new_tests.extend([offline_proof,compat_proof,saved_proof])
            selected = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            selected['offline'] = {'command':offline_proof['command'],'exit_code':0,
                                   'log':offline_proof['log'],'log_sha256':offline_proof['sha256'],
                                   'construction_sha256':selected['construction_sha256']}
            source = compat
            files = {'receipt': (source/'compatibility.json',HERE/(tag+'-compatibility.json')),
                     'analysis': (source/'compatibility-analysis.log',HERE/(tag+'-analysis.log')),
                     'negative': (source/'negative-analysis.log',HERE/(tag+'-negative.log'))}
            for old,new in files.values():
                shutil.copyfile(old,new)
            selected['compatibility'] = {'receipt':files['receipt'][1].name,
                                         'sha256':sha(files['receipt'][1]),
                                         'log':files['analysis'][1].name}
            if candidate == 'primary':
                entry['negative'] = {'log':files['negative'][1].name,
                                     'log_sha256':sha(files['negative'][1])}
            else:
                selected['compatibility']['negative_log'] = files['negative'][1].name
            if candidate == 'primary':
                processing_source = saved/'v0001/processing.json'
                processing_target = HERE/(tag+'-processing.json')
                shutil.copyfile(processing_source,processing_target)
                analysis_source = saved/'v0001/analysis.log'
                analysis_target = HERE/(tag+'-saved-analysis.log')
                shutil.copyfile(analysis_source,analysis_target)
                entry['post_capture'] = {'recorded_only':True,
                    'command':saved_proof['command'],'test_log':analysis_target.name,
                    'test_log_sha256':sha(analysis_target),'test_exit_code':0,
                    'receipt':processing_target.name,'receipt_sha256':sha(processing_target),
                    'scope':'nine-frame synthetic saved-only software processing'}
            else:
                selected['saved_processing'] = {'command':saved_proof['command'],
                    'log':saved_proof['log'],'log_sha256':saved_proof['sha256'],
                    'recorded_only':True}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    old = {t['log'] for t in new_tests}
    result['tests'] = [t for t in result['tests'] if t['log'] not in old]+new_tests
    result['reason'] += ' Both newly selected conditions-permitting gap cases and all six fallbacks now have fresh canonical-manifest exact offline, compatibility and recorded-only saved-processing proofs. Independent physical-preparation and delivery acceptance contracts and canonical semantic/branch review remain unfinished; Native and legal outcomes unverified.'
    result_path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case_ids':[HERE.name+'__conditions_gap_120m',HERE.name+'__conditions_gap_200m'],
                      'candidate_plans':8,'proof_commands':len(new_tests)},indent=2))


if __name__ == '__main__':
    main()
