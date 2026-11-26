"""Run three synthetic physical outcomes and owner-release lifecycle per case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE/'physical_preparation_full.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for name in ('draft-device-full-manifest.json', 'draft-boundary-manifest.json',
                 'draft-parked-manifest.json'):
        entries.extend(json.loads((HERE/name).read_text())['cases'])
    environment = os.environ.copy()
    scratch = ROOT/'.runtime-work/c179824'
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch)
    environment['TMPDIR'] = str(scratch)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    outputs = []
    for entry in entries:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(HERE.name+'__')
        if suffix.startswith('controlled_'):
            source = HERE/'cases'/('full_'+suffix)/'source/vehicle-lamps.jsonl'
        elif suffix.startswith('parked_lamps_'):
            source = HERE/'cases'/suffix/'source/parked-trace.jsonl'
        else:
            source = HERE/'cases'/suffix/'source/visibility-trace.jsonl'
        assert source.is_file(), source
        directory = HERE/'physical-proof'/suffix
        directory.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence',
                     'lifecycle'):
            result = directory/(kind+'.json')
            log = directory/(kind+'.log')
            command = [str(ROOT/'.venv-cpu/bin/python'), '-B', str(SCRIPT),
                       '--case', case_id, '--kind', kind, '--output', str(result)]
            if kind != 'lifecycle':
                command.extend(['--source', str(source)])
            completed = subprocess.run(command, cwd=ROOT, env=environment,
                                       capture_output=True, text=True)
            log.write_text((completed.stdout+completed.stderr).rstrip()+'\n')
            if completed.returncode:
                raise RuntimeError(f'{suffix}/{kind} physical CPU fixture failed: {log.read_text()}')
            row = {'command': ' '.join(command), 'exit_code': 0,
                   'log': log.relative_to(HERE).as_posix(),
                   'log_sha256': sha(log),
                   'result': result.relative_to(HERE).as_posix(),
                   'result_sha256': sha(result)}
            if kind == 'lifecycle':
                life = json.loads(result.read_text())
                row['events'] = life['events']
            else:
                row['kind'] = kind
                fixtures.append(row)
        proof = {'format': 'c179824-physical-preparation-v1',
                 'case_id': case_id,
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': row,
                 'physical_acceptance_claimed': False}
        proof_path = directory/'proof.json'
        proof_path.write_text(json.dumps(proof, indent=2)+'\n')
        outputs.append({'case_id': case_id,
                        'proof': proof_path.relative_to(HERE).as_posix(),
                        'sha256': sha(proof_path)})
        print(json.dumps(outputs[-1], sort_keys=True), flush=True)
    summary = {'format': 'c179824-physical-proof-index-v1',
               'cases': outputs, 'all_passed': len(outputs) == 13,
               'physical_acceptance_claimed': False}
    (HERE/'physical-proof/index.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
