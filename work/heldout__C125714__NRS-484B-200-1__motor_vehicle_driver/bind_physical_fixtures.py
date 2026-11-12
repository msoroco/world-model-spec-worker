"""Bind eight synthetic outcome triplets and tested capture closure to source hashes."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / 'physical'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def execute(command, log):
    with log.open('w') as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)


def main():
    OUTPUT.mkdir(exist_ok=True)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        stem = case.rsplit('__', 1)[-1]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            baseline = stem.startswith('baseline_')
            offsets = [.4, .3, .2] if baseline else [.4, .1, -.2]
            rows = [{'frame': i+1, 'route_progress_m': float(i)/2,
                     'minimum_body_right_offset_m': offsets[i]} for i in range(3)]
            if kind == 'incomplete_motion':
                for row in rows: row['route_progress_m'] = 0.0
            if kind == 'missing_evidence': rows = None
            source = OUTPUT / (stem + '-' + kind + '-source.json')
            source.write_text(json.dumps({'case_id': case, 'kind': kind,
                                          'diagnostic_fixture': True, 'rows': rows}, indent=2) + '\n')
            result = OUTPUT / (stem + '-' + kind + '.json')
            log = OUTPUT / (stem + '-' + kind + '.log')
            command = [sys.executable, str(HERE / 'physical_fixture.py'),
                       '--case', case, '--kind', kind, '--source', str(source),
                       '--output', str(result)]
            execute(command, log)
            value = json.loads(result.read_text())
            if (value.get('case_id') != case or value.get('fixture_kind') != kind
                    or value.get('actual_native_capture') is not False
                    or value.get('physical_acceptance_claimed') is not False):
                raise ValueError('Physical fixture identity or scope changed')
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': digest(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': digest(result)})
        life_log = OUTPUT / (stem + '-lifecycle.log')
        life_command = [sys.executable, str(HERE / 'lifecycle_fixture.py'), '--case', case]
        execute(life_command, life_log)
        if ' '.join(EVENTS) not in life_log.read_text():
            raise ValueError('Capture closure events missing or unordered')
        proof = {'construction_sha256': entry['construction_sha256'],
                 'fixture_scope': 'Synthetic source and ownership protocol only; no actual Native capture',
                 'fixtures': fixtures,
                 'lifecycle': {'events': EVENTS, 'exit_code': 0,
                               'command': ' '.join(life_command),
                               'log': str(life_log.relative_to(HERE)),
                               'log_sha256': digest(life_log)}}
        receipt = OUTPUT / (stem + '-proof.json')
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': digest(receipt)}
        print(stem, 'physical outcome triplet and lifecycle passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
