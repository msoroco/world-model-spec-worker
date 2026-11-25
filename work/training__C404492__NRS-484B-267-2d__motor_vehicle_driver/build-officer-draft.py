"""Materialize exact directed-officer CPU construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CASE = AID + '__officer_directed'
SOURCE = AID + '__controlled_2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    candidates = []
    contract = json.loads((HERE / 'measurement-contracts' / 'controlled_2.json').read_text())
    contract['case_id'] = CASE
    write(HERE / 'measurement-contracts' / 'officer_directed.json', contract)
    for candidate in ('primary', 'fallback1', 'fallback2'):
        source = HERE / 'draft-emergency' / 'controlled_2' / candidate / 'construction.json'
        construction = json.loads(source.read_text())
        construction['case_id'] = CASE
        construction['mechanisms'].append(
            'independently reviewed directed-officer instruction paired with identical controlled_2 motion')
        files = []
        for entry in construction['files']:
            if entry['path'] == 'runner.py':
                files.extend([
                    {'path': 'base_runner.py', 'content': (HERE / 'native' / 'runner.py').read_text()},
                    {'path': 'runner.py', 'content': (HERE / 'native' / 'officer_runner.py').read_text()},
                ])
            elif entry['path'] == 'finalize.py':
                files.extend([
                    {'path': 'base_finalize.py', 'content': (HERE / 'finalize.py').read_text()},
                    {'path': 'finalize.py', 'content': (HERE / 'native' / 'officer_finalize.py').read_text()},
                ])
            elif entry['path'] == 'measure_emergency.py':
                files.append({'path': 'measure_emergency.py',
                              'content': (HERE / 'measure_emergency.py').read_text()})
            elif entry['path'] == 'config.json':
                cfg = json.loads(entry['content'])
                cfg.update(case_id=CASE, selected_case_id=CASE,
                           case_suffix='officer_directed')
                files.append({'path': 'config.json',
                              'content': json.dumps(cfg, indent=2, sort_keys=True) + '\n'})
            elif entry['path'] == 'measurement-contract.json':
                contract = json.loads(entry['content'])
                contract['case_id'] = CASE
                files.append({'path': entry['path'],
                              'content': json.dumps(contract, indent=2, sort_keys=True) + '\n'})
            else:
                files.append(entry)
        construction['files'] = files
        target = HERE / 'draft-officer' / candidate / 'construction.json'
        write(target, construction)
        candidates.append({'candidate_id': candidate, 'case_id': CASE,
                           'construction': str(target.relative_to(HERE)),
                           'construction_sha256': sha(target)})
    source_manifest = json.loads((HERE / 'draft-emergency-manifest.json').read_text())
    source_entry = next(entry for entry in source_manifest['cases']
                        if entry['case_id'] == SOURCE)
    source_entry['case_id'] = CASE
    source_entry['construction'] = candidates[0]['construction']
    source_entry['construction_sha256'] = candidates[0]['construction_sha256']
    source_entry['measurement_contract'] = 'measurement-contracts/officer_directed.json'
    source_entry['candidate_risk']['reason'] = (
        'Original officer identity, instruction, recipient and timing need independent review')
    for fallback, construction in zip(source_entry['candidates'], candidates[1:]):
        fallback['construction'] = construction['construction']
        fallback['construction_sha256'] = construction['construction_sha256']
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': AID, 'status': 'partial', 'cases': [source_entry],
                'selected_delivery': False,
                'reason': 'Officer instruction original-source and comparison proof chain pending'}
    write(HERE / 'draft-officer-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'manifest_sha256': sha(HERE / 'draft-officer-manifest.json'),
                      'candidates': candidates}, sort_keys=True))


if __name__ == '__main__':
    main()
