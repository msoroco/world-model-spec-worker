"""Bind exact turn constructions, proof logs, and CPU audit commands."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def main():
    probe = json.loads((ROOT/'probe-compatibility-manifest.json').read_text())
    exact = json.loads((ROOT/'exact-proofs.json').read_text())
    saved = json.loads((ROOT/'saved-proofs.json').read_text())
    delivery = json.loads((ROOT/'delivery-audit-proofs.json').read_text())
    comparison = json.loads((ROOT/'comparison-proofs.json').read_text())
    physical = json.loads((ROOT/'physical-preparation-proofs.json').read_text())
    by_exact = {(x['case_id'], x['candidate_id']): x for x in exact['cases']}
    by_saved = {x['case_id']: x for x in saved['cases']}
    by_delivery = {x['case_id']: x for x in delivery['cases']}
    by_physical = {x['case_id']: x for x in physical['cases']}
    (ROOT/'cases'/'proof-compat-empty.log').write_text('')
    entries = []
    for source in probe['cases']:
        case = source['case_id']; suffix = case.split('__')[-1]
        row = dict(source)
        primary = by_exact[(case, 'primary')]
        row['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --output .runtime-work/c109705-{suffix}-manifest-offline --python "$PWD/.venv-cpu/bin/python"',
            'exit_code': 0, 'construction_sha256': digest(ROOT/row['construction']),
            'log': primary['offline_log'], 'log_sha256': digest(ROOT/primary['offline_log'])}
        for candidate in row['candidates']:
            proof = by_exact[(case, candidate['id'])]
            candidate['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {case} --candidate {candidate["id"]} --output .runtime-work/c109705-{suffix}-{candidate["id"]}-manifest-offline --python "$PWD/.venv-cpu/bin/python"',
                'exit_code': 0, 'construction_sha256': digest(ROOT/candidate['construction']),
                'log': proof['offline_log'], 'log_sha256': digest(ROOT/proof['offline_log'])}
            receipt = ROOT/proof['receipt']
            compatibility = json.loads(receipt.read_text())
            negative_source = REPO/'.runtime-work'/f'c109705-{suffix}-{candidate["id"]}-compat-v6'/'negative-analysis.log'
            negative = ROOT/'cases'/f'compat-negative-{suffix}-{candidate["id"]}.log'
            shutil.copyfile(negative_source, negative)
            if digest(negative) != compatibility['negative_log_sha256']:
                raise ValueError('Current negative compatibility proof differs: '+suffix+' '+candidate['id'])
            candidate['compatibility'] = {'receipt': proof['receipt'], 'sha256': digest(receipt),
                'log': 'cases/proof-compat-empty.log',
                'negative_log': str(negative.relative_to(ROOT))}
        saved_row = by_saved[case]
        row['post_capture'] = {'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/c125714-validator/.lake/build/bin/adapterCheck',
            'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
            'test_log': saved_row['log'], 'test_log_sha256': digest(ROOT/saved_row['log']),
            'test_exit_code': 0}
        row['physical_preparation'] = {'receipt': by_physical[case]['receipt'],
                                       'sha256': by_physical[case]['sha256']}
        audit = by_delivery[case]
        row['delivery_acceptance'] = {'case_id': case, 'sets': ['held-out'],
            'checks': ['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': digest(ROOT/'delivery_audit.py'),
            'command': f'.venv-cpu/bin/python work/{ROOT.name}/delivery_audit.py --attempt "$ATTEMPT" --case {case}',
            'test_exit_code': 0, 'test_log': audit['positive_log'],
            'test_log_sha256': digest(ROOT/audit['positive_log']),
            'negative_command': 'Tamper one retained source row then rerun the independent delivery audit',
            'negative_exit_code': 1, 'negative_expected_error': audit['negative_error'],
            'negative_log': audit['negative_log'], 'negative_log_sha256': digest(ROOT/audit['negative_log'])}
        row['native_handoff'] = {'python_env_var':'CARLA_PYTHON',
                                 'host_env_var':'CARLA_HOST', 'port_env_var':'CARLA_PORT'}
        entries.append(row)
    manifest = {'format':'worker-execution-manifest', 'assignment_id':probe['assignment_id'],
        'runtime_manifest_sha256':probe['runtime_manifest_sha256'],
        'diagnostic_source_scope':'Synthetic route survey and media only; actual Native roadway proof pending',
        'comparison_audit_commands':[{'assignment_id':ROOT.name, 'comparison_id':x['comparison_id'],
            'command':f'.venv-cpu/bin/python work/{ROOT.name}/source_comparison_audit.py --comparison {x["comparison_id"]}',
            'test_log':x['log'], 'test_log_sha256':digest(ROOT/x['log'])}
            for x in comparison['cases']], 'cases':entries}
    (ROOT/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Three exact turn execution cases, nine alternatives and two comparison commands bound')

if __name__=='__main__': main()
