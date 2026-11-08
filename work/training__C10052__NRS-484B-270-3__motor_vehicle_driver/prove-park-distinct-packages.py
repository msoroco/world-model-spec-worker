"""Full synthetic v1 package positives and changed-control negatives for park cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

SOURCE = ROOT / '.runtime-work/c10052-park-contrast-4hzeucne'
MANIFEST = HERE / 'draft-park-execution-manifest.json'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', choices=NAMES, required=True)
    args = parser.parse_args()
    decoder = ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'
    results = []
    for suffix, source_name, expected in (
            ('probe_park_released', 'released-source', False),
            ('probe_park_held', 'held-source', True)):
        case_id = HERE.name + '__' + suffix
        source = SOURCE / source_name
        output = SOURCE / ('distinct2-' + suffix + '-' + args.candidate)
        receipt = run(MANIFEST, case_id, source, output,
                      ROOT / 'runtime/pipeline/library', decoder, args.candidate)
        analysis = json.loads((output / 'analysis-report.json').read_text())
        result = json.loads((output / 'result.json').read_text())
        observation = analysis['measurements']['parking_control_observation']['value']
        assert observation['park_control_candidate'] is expected
        assert observation['held_duration_s'] == (14.0 if expected else 0)
        assert result['target_checks'][1]['requested'] is expected
        assert result['target_checks'][1]['measured'] is expected
        assert result['target_checks'][1]['matched'] is True
        assert receipt['passed'] is True and result['accepted'] is False
        negative = SOURCE / ('distinct2-negative-' + suffix + '-' + args.candidate)
        materialize_case(MANIFEST, case_id, negative, source, args.candidate)
        lines = (negative / 'native_controls.jsonl').read_text().splitlines()
        changed = json.loads(lines[200])
        changed['hand_brake'] = not changed['hand_brake']
        lines[200] = json.dumps(changed)
        (negative / 'native_controls.jsonl').write_text('\n'.join(lines) + '\n')
        command = [sys.executable, str(negative / 'finalize.py'), '--attempt',
                   str(negative), '--output', str(negative / 'analysis-report.json')]
        failed = subprocess.run(command, cwd=negative, env=execution_env(),
                                text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
        log_path = SOURCE / ('distinct2-negative-' + suffix + '-' + args.candidate + '.log')
        log_path.write_text(failed.stdout)
        assert failed.returncode != 0 and 'Parking source hash differs: native_controls.jsonl' in failed.stdout
        assert not (negative / 'result.json').exists()
        results.append({'case_id': case_id, 'candidate': args.candidate,
                        'source_root': source.relative_to(ROOT).as_posix(),
                        'output_root': output.relative_to(ROOT).as_posix(),
                        'negative_root': negative.relative_to(ROOT).as_posix(),
                        'positive_receipt_sha256': sha(output / 'compatibility.json'),
                        'negative_log_sha256': sha(log_path),
                        'held_duration_s': observation['held_duration_s'],
                        'park_control_candidate': expected})
    print(json.dumps({'format': 'c10052-park-distinct-packages-v1',
                      'passed': True, 'manifest_sha256': sha(MANIFEST),
                      'results': results, 'selected': False, 'accepted': False}, indent=2))


if __name__ == '__main__':
    main()
