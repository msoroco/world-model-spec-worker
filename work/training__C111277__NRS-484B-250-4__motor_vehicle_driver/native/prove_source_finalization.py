"""Positive and missing-source checks for retained-row finalization."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from generate_fixture import make

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_finalize(attempt):
    command = [sys.executable, str(HERE / 'finalize_source.py'), '--attempt', str(attempt),
               '--output', str(attempt / 'analysis-report.json')]
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=120)


def main():
    records = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c111277-source-finalize-') as temp:
        scratch = Path(temp)
        for condition in ('halt', 'roll'):
            original = scratch / (condition + '-source')
            make(original, condition)
            positive = scratch / (condition + '-positive')
            shutil.copytree(original, positive)
            before = {name: sha(positive / name) for name in
                      ('source-index.json', 'geometry.json', 'signal.json', 'native-rows.jsonl')}
            passed = run_finalize(positive)
            if passed.returncode:
                raise RuntimeError(condition + ' finalization failed: ' + passed.stdout)
            if any(sha(positive / name) != digest for name, digest in before.items()):
                raise ValueError('Finalization changed retained source')
            report = json.loads((positive / 'analysis-report.json').read_text())
            if report['frames'] != 600 or len(report['derived_channels_sha256']) != 10:
                raise ValueError('Incomplete source-derived recording evidence')
            for name, digest in report['derived_channels_sha256'].items():
                path = positive / 'channels' / (name + '.jsonl')
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                if len(rows) != 600 or sha(path) != digest:
                    raise ValueError('Incomplete source-derived channel: ' + name)
                if any(row['native_frame'] != i or row['time_s'] != i / 20 or
                       row['source_sha256'] != before for i, row in enumerate(rows)):
                    raise ValueError('Derived channel source join failed: ' + name)
            missing = scratch / (condition + '-missing-signal')
            shutil.copytree(original, missing)
            (missing / 'signal.json').unlink()
            failure = run_finalize(missing)
            if failure.returncode == 0 or 'Missing required source: signal.json' not in failure.stdout:
                raise ValueError('Missing signal source was accepted')
            changed = scratch / (condition + '-changed-source')
            shutil.copytree(original, changed)
            with (changed / 'native-rows.jsonl').open('a') as file:
                file.write('\n')
            tamper = run_finalize(changed)
            if tamper.returncode == 0 or 'source hash mismatch: native-rows.jsonl' not in tamper.stdout:
                raise ValueError('Changed retained row source was accepted')
            records.append({'condition': condition, 'positive_exit_code': passed.returncode,
                            'report_sha256': sha(positive / 'analysis-report.json'),
                            'source_hashes_preserved': True, 'frames': 600,
                            'derived_channels': 10, 'missing_signal_exit_code': failure.returncode,
                            'missing_signal_error': 'Missing required source: signal.json',
                            'changed_source_exit_code': tamper.returncode,
                            'changed_source_error': 'source hash mismatch: native-rows.jsonl',
                            'crosswalk_entry_frame': report['measurements']['crosswalk_entry_frame'],
                            'halt_before_crosswalk': report['measurements']['halt_before_crosswalk'],
                            'yielded_until_other_clear': report['measurements']['yielded_until_other_clear']})
    if ([r['halt_before_crosswalk'] for r in records] != [True, False] or
            any(r['crosswalk_entry_frame'] != 300 for r in records) or
            not all(r['yielded_until_other_clear'] for r in records)):
        raise ValueError('Source finalization did not preserve controlled contrast')
    proof = {'format': 'nrs-484b-250-4-source-finalization-proof-v1', 'passed': True,
             'finalizer_sha256': sha(HERE / 'finalize_source.py'),
             'generator_sha256': sha(HERE / 'generate_fixture.py'), 'cases': records,
             'original_native_observed': False, 'physical_signal_failure_confirmed': False,
             'current_public_compatibility_proved': False,
             'actual_process_saved_proved': False, 'legal_outcome_asserted': False}
    target = HERE / 'source-finalization-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(records), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
