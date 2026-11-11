"""Bind one pinned physical-preparation receipt per exact C10364 alley case."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from physical_probe import SUFFIXES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / 'physical_case_probe.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    (ROOT / 'physical').mkdir(exist_ok=True)
    index = {'format': 'worker-alley-physical-preparation-cpu-proofs',
             'scope': 'synthetic original-shaped CPU protocol only; no actual Native motion',
             'probe_script': SCRIPT.name, 'probe_script_sha256': digest(SCRIPT),
             'cases': []}
    for suffix in SUFFIXES:
        case_id = ROOT.name + '__' + suffix
        construction = ROOT / 'cases' / f'construction-{suffix}.json'
        receipt = {'format': 'worker-physical-preparation-proof',
                   'case_id': case_id, 'construction_sha256': digest(construction),
                   'fixture_scope': 'synthetic original-shaped CPU protocol',
                   'fixtures': []}
        for kind in KINDS:
            output = REPO / '.runtime-work' / f'c10364-{suffix}-physical-{kind}-gate'
            if suffix == 'person_3mps' and kind == 'complete_motion':
                output = REPO / '.runtime-work/c10364-person_3mps-physical-complete'
            log = ROOT / 'physical' / f'{suffix}-{kind}.log'
            result = ROOT / 'physical' / f'{suffix}-{kind}-result.json'
            args = [sys.executable, str(SCRIPT), '--case', case_id,
                    '--kind', kind, '--output', str(output)]
            if not log.is_file():
                if output.exists():
                    raise ValueError('Unbound prior physical fixture output: ' + str(output))
                process = subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                                         env={**__import__('os').environ,
                                              'PYTHONPATH': str(REPO / 'runtime/scenario_pipeline')})
                log.write_text(process.stdout + process.stderr)
                if process.returncode:
                    raise ValueError('Exact physical fixture failed: ' + log.name)
            if kind == 'lifecycle':
                life = json.loads(log.read_text())
                if (life.get('case_id') != case_id or not life.get('premature_seal_rejected')
                        or life.get('events') != ['capture_finished', 'encoders_closed',
                                                   'restoration_verified', 'native_exit',
                                                   'owner_released', 'saved_processing_started']):
                    raise ValueError('Exact physical lifecycle proof differs')
                receipt['lifecycle'] = {'events': life['events'], 'command': ' '.join(args),
                    'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                    'log_sha256': digest(log), 'premature_seal_rejected': True}
            else:
                observed = json.loads(result.read_text())
                expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                            'missing_evidence': 'unverified'}[kind]
                if (observed.get('case_id') != case_id or
                        observed.get('physical_checks', {}).get('maneuver', {}).get('status') != expected):
                    raise ValueError('Exact physical result differs: ' + result.name)
                receipt['fixtures'].append({'kind': kind, 'command': ' '.join(args),
                    'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                    'log_sha256': digest(log), 'result': str(result.relative_to(ROOT)),
                    'result_sha256': digest(result)})
        path = ROOT / 'physical' / f'{suffix}-proof.json'
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        index['cases'].append({'case_id': case_id,
                               'receipt': str(path.relative_to(ROOT)),
                               'sha256': digest(path)})
        print('physical ' + suffix, flush=True)
    (ROOT / 'physical-preparation-proofs.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Nine exact alley gate-shaped physical and lifecycle receipts pass', flush=True)


if __name__ == '__main__':
    main()
