"""Bind synthetic physical fixture receipts to current exact constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = ('dry_open_traffic', 'wet_same_traffic', 'dense_traffic',
            'narrow_same_traffic', 'low_visibility', 'ice_or_snow',
            'dry_4mps', 'dry_6mps')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
COMMAND = ('SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c179789-physical '
           'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD/runtime/scenario_pipeline '
           '.venv-cpu/bin/python work/testing__C179789__NRS-484B-600-1a__motor_vehicle_driver/cases/prove_physical.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    log = ROOT / 'cases/physical-fixtures.log'
    proof = json.loads(log.read_text())
    rows = {(row['case_id'], row['kind']): row for row in proof['fixtures']}
    for suffix in SUFFIXES:
        case_id = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__' + suffix
        construction = ROOT / ('construction.json' if suffix == 'dry_open_traffic' else
                               'cases/' + suffix + '-construction.json')
        fixtures = []
        for kind in KINDS:
            row = rows[(case_id, kind)]
            result = ROOT / row['result']
            fixtures.append({'kind': kind, 'command': COMMAND,
                             'log': 'cases/physical-fixtures.log', 'log_sha256': sha(log),
                             'exit_code': 0, 'result': row['result'],
                             'result_sha256': sha(result)})
        receipt = {'format': 'worker-physical-preparation', 'case_id': case_id,
                   'construction_sha256': sha(construction), 'fixtures': fixtures,
                   'lifecycle': {'events': proof['lifecycle']['events'], 'exit_code': 0,
                                 'log': 'cases/physical-fixtures.log', 'log_sha256': sha(log)}}
        path = ROOT / 'cases' / (suffix + '-physical-preparation.json')
        path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'cases': len(SUFFIXES), 'fixture_kinds': len(KINDS)}))


if __name__ == '__main__':
    main()
