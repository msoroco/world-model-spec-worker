"""Bind passed current CPU chains to the eleven selected case identities."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    witness = read(HERE / 'current-v2-witness-fallback-manifest.json')
    statutory = read(HERE / 'current-profile-statutory-manifest.json')
    assert witness['runtime_manifest_sha256'] == statutory['runtime_manifest_sha256']
    proofs = {}
    for path in ('current-v3-witness-cpu-proof.json', 'current-v3-statutory-cpu-proof.json'):
        for chain in read(HERE / path)['chains']:
            proofs[(chain['case_id'], chain['candidate_id'])] = chain
    saved = {chain['case_id']: chain for chain in
             read(HERE / 'current-v3-saved-primary-cpu-proof.json')['chains']}
    entries = []
    proposal = read(HERE / 'proposals/cases.json')
    old_cases = {item['case_id']: item for item in proposal['cases']}
    for source in (witness, statutory):
        for original in source['cases']:
            entry = copy.deepcopy(original)
            case_id = entry['case_id']
            suffix = case_id.rsplit('__', 1)[-1]
            entry['kind'] = 'delivery'
            entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                       'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
            construction = read(HERE / entry['construction'])
            old_cases[case_id]['recording_description'] = construction['recording_description']
            config = json.loads(next(f['content'] for f in construction['files']
                                     if f['path'] == 'config.json'))
            atoms = set(config.get('required_atoms', []))
            atoms.update(c['name'] for c in construction['recording_description']['channels'])
            files = {f['path'] for f in construction['files']}
            entry['acquisition'] = {name: {
                'entrypoint': 'finalize.py' if 'finalize.py' in files else 'runner.py',
                'method': 'Source-hashed Native acquisition and time-joined saved processing',
                'evidence': 'Synthetic CPU fixture checks processing; original Native motion and pixels require local capture'}
                for name in sorted(atoms)}
            for candidate in [entry, *entry['candidates']]:
                name = candidate['id']
                row = proofs[(case_id, name)]
                assert row['construction_sha256'] == candidate['construction_sha256']
                files_map = row['files']
                def find(basename):
                    return next(path for path in files_map if path.endswith('/' + basename))
                offline = find('offline.log')
                receipt = find('compatibility.json')
                public_log = find('compatibility-analysis.log')
                negative = find('negative-analysis.log')
                candidate['offline'] = {
                    'command': ('.venv-cpu/bin/python runtime.py offline --manifest '
                                f'work/{HERE.name}/' +
                                ('current-v2-witness-fallback-manifest.json' if source is witness
                                 else 'current-profile-statutory-manifest.json') +
                                f' --case {case_id} --candidate {name} --output .runtime-work/c110454-selected-offline/{suffix}/{name}'),
                    'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                    'log': offline, 'log_sha256': sha(HERE / offline)}
                candidate['compatibility'] = {'receipt': receipt, 'sha256': sha(HERE / receipt),
                                               'log': public_log, 'negative_log': negative}
                if name == 'primary':
                    candidate['negative'] = {'log': negative, 'log_sha256': sha(HERE / negative)}
                    saved_row = saved[case_id]
                    assert saved_row['construction_sha256'] == candidate['construction_sha256']
                    candidate['saved_cpu_proof'] = {
                        'processing': saved_row['receipt'],
                        'processing_sha256': saved_row['receipt_sha256'],
                        'recorded_only': True, 'originals_preserved': True,
                        'selected_construction_sha256': candidate['construction_sha256']}
            entries.append(entry)
    assert len(entries) == 11 and len(proofs) == 33
    proposal['cases'] = [old_cases[item['case_id']] for item in entries]
    proposal['sweep_specs'] = proposal.get('sweep_specs', [])
    proposal['sweeps_expanded'] = True
    write(HERE / 'proposals/cases.json', proposal)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': witness['runtime_manifest_sha256'],
                'status': 'draft_physical_and_delivery_proof_pending', 'cases': entries}
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'cases': len(entries), 'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'proposal_sha256': sha(HERE / 'proposals/cases.json')}))


if __name__ == '__main__':
    main()
