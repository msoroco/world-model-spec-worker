"""Bind current inside-branch physical classifier and lifecycle CPU fixtures."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for name in ('inside_yield', 'inside_no_yield'):
    case = folder.name + '__' + name
    draft = folder / 'cases' / name
    entry = json.loads((draft / 'draft-manifest.json').read_text())['cases'][0]
    base = draft / 'physical-proofs'
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        relative = Path('cases') / name / 'physical-proofs' / (kind + '.json')
        log = relative.with_suffix('.log')
        command = (f'.venv-cpu/bin/python work/{folder.name}/inside_physical_fixture_proof.py '
                   f'--manifest work/{folder.name}/cases/{name}/draft-manifest.json '
                   f'--case {case} --kind {kind} --output work/{folder.name}/{relative}')
        assert json.loads((folder / relative).read_text())['physical_checks']['maneuver']['status'] == {
            'complete_motion': 'met', 'incomplete_motion': 'not_met',
            'missing_evidence': 'unverified'}[kind]
        fixtures.append({'kind': kind, 'command': command, 'exit_code': 0,
                         'log': str(log), 'log_sha256': sha(folder / log),
                         'result': str(relative), 'result_sha256': sha(folder / relative)})
    lifecycle = Path('cases') / name / 'physical-proofs/lifecycle.json'
    life_log = lifecycle.with_suffix('.log')
    life = json.loads((folder / lifecycle).read_text())
    events = life['events']
    receipt = {'format': 'worker-physical-preparation', 'case_id': case,
               'construction_sha256': entry['construction_sha256'],
               'fixtures': fixtures,
               'lifecycle': {'events': events, 'exit_code': 0,
                             'command': (f'.venv-cpu/bin/python work/{folder.name}/inside_physical_fixture_proof.py '
                                         f'--manifest work/{folder.name}/cases/{name}/draft-manifest.json '
                                         f'--case {case} --kind lifecycle --output work/{folder.name}/{lifecycle}'),
                             'log': str(life_log), 'log_sha256': sha(folder / life_log),
                             'result': str(lifecycle), 'result_sha256': sha(folder / lifecycle)}}
    output = base / 'receipt.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'receipt': str(output.relative_to(folder)),
                      'sha256': sha(output)}))
