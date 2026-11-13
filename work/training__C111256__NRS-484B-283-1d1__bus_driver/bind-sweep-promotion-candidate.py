"""Bind staged sweep proofs into a reviewable delivery-manifest candidate."""
import hashlib
import json
from pathlib import Path
import sys
import copy

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate as validate_candidates


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matrix(name):
    rows = read(HERE / name)['rows']
    index = {(row['case_id'], row['candidate_id']): row for row in rows}
    if len(index) != 16 or len(rows) != 16:
        raise ValueError('Incomplete sweep proof matrix: ' + name)
    return index


def main():
    staged = read(HERE / 'sweep-execution-candidate.json')
    selected = read(HERE / 'execution-manifest.json')
    reference = next(item for item in selected['cases'] if item['case_id'].endswith('__reference'))
    offline = matrix('update029-sweep-runtime-offline-matrix.json')
    compat = matrix('update028-sweep-staged-compat-matrix.json')
    cases = []
    for source in staged['cases']:
        entry = {key: value for key, value in source.items()
                 if key not in ('status', 'setpoint_margin_m', 'candidates')}
        entry['kind'] = 'delivery'
        entry['candidate_risk'] = source['candidate_risk']
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['preparation_status'] = 'promotion_candidate; staged diagnostic proofs only'
        entry['acquisition'] = copy.deepcopy(reference['acquisition'])
        entry['acquisition']['crosswalk_hold_margin_m'] = {
            'entrypoint': 'physical_sweep.py',
            'method': ('Derive the first requested hold bus-front distance to the marked '
                       'crosswalk from all 480 original Native body/control rows'),
            'evidence': ('Original Native pose/control, map readback and source camera '
                         'review required; diagnostic rows retain synthetic_native_sample')}
        entry['candidates'] = []
        for candidate in [{'id': 'primary', 'construction': source['construction'],
                           'construction_sha256': source['construction_sha256']},
                          *source['candidates']]:
            key = (source['case_id'], candidate['id'])
            off = offline[key]
            pos = compat[key]
            if (off['construction_sha256'] != candidate['construction_sha256'] or
                    pos['construction_sha256'] != candidate['construction_sha256']):
                raise ValueError('Candidate proof source changed')
            command = (f'{REPO / ".venv-cpu/bin/python"} {REPO / "runtime.py"} offline '
                       f'--manifest {HERE / "sweep-execution-candidate.json"} '
                       f'--case {source["case_id"]} --candidate {candidate["id"]} '
                       f'--python {REPO / ".venv-cpu/bin/python"}')
            binding = {'offline': {'command': command, 'exit_code': off['exit_code'],
                                   'construction_sha256': off['construction_sha256'],
                                   'log': off['log'], 'log_sha256': off['log_sha256']},
                       'compatibility': {'receipt': pos['receipt'],
                                         'sha256': pos['receipt_sha256'],
                                         'log': str(Path(pos['receipt']).parent / 'positive-analysis.log'),
                                         'negative_log': str(Path(pos['receipt']).parent / 'negative-analysis.log')}}
            if candidate['id'] == 'primary':
                entry.update(binding)
                entry['negative'] = {'log': binding['compatibility']['negative_log']}
            else:
                target = {key: value for key, value in candidate.items()
                          if key != 'setpoint_margin_m'}
                target.update(binding)
                entry['candidates'].append(target)
        validate_candidates(HERE, entry, 'NRS-484B-283-1d1', 'C111256',
                            required=True, require_alternate=True, candidate_count=4)
        construction = read(HERE / entry['construction'])
        files = {item['path'] for item in construction['files']}
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        required = set(config.get('required_atoms', [])) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        if (not required <= set(entry['acquisition']) or
                any(entry['acquisition'][name]['entrypoint'] not in files
                    for name in required)):
            raise ValueError('Sweep acquisition does not cover bundled sources')
        cases.append(entry)
    out = {'format': 'worker-execution-manifest',
           'assignment_id': staged['assignment_id'],
           'runtime_manifest_sha256': staged['runtime_manifest_sha256'],
           'status': 'promotion_candidate_not_selected',
           'source_staged_manifest_sha256': sha(HERE / 'sweep-execution-candidate.json'),
           'source_offline_matrix_sha256': sha(HERE / 'update029-sweep-runtime-offline-matrix.json'),
           'source_compatibility_matrix_sha256': sha(HERE / 'update028-sweep-staged-compat-matrix.json'),
           'cases': cases}
    path = HERE / 'sweep-proof-bound-promotion-candidate.json'
    if path.exists():
        prior = read(path)
        old = {entry['case_id']: entry for entry in prior.get('cases', [])}
        for entry in cases:
            retained = old.get(entry['case_id'], {})
            if retained.get('physical_preparation'):
                if retained.get('construction_sha256') != entry['construction_sha256']:
                    raise ValueError('Cannot retain physical proof after construction change')
                entry['physical_preparation'] = retained['physical_preparation']
    path.write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'candidate_bindings': len(cases) * 4,
                      'pinned_fallback_validator': 'passed', 'selected': False,
                      'sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
