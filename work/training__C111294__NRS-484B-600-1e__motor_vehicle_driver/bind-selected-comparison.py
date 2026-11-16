"""Prove the final selected four-speed comparison stays diagnostic."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ('below_80_mph', 'inside_80_mph', 'at_80_mph', 'above_80_mph')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(source_tag, tag):
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    expected = {HERE.name + '__' + suffix for suffix in SUFFIXES}
    if {case['case_id'] for case in manifest['cases']} != expected:
        raise ValueError('Four selected comparison members differ')
    base = ROOT / '.runtime-work' / f'c111294-{source_tag}-selected'
    command = [sys.executable, str(HERE / 'comparison_audit.py'),
               '--attempt-root', str(base)]
    diagnostic = HERE / f'{tag}-selected-comparison-diagnostic.json'
    negative = HERE / f'{tag}-selected-comparison-original.json'
    log = HERE / f'{tag}-selected-comparison-diagnostic.log'
    negative_log = HERE / f'{tag}-selected-comparison-original-negative.log'
    for output, logfile, args in ((diagnostic, log, ['--diagnostic']),
                                  (negative, negative_log, [])):
        if output.exists() or logfile.exists():
            raise ValueError('Retain prior comparison proof; choose fresh tag')
        run = subprocess.run(command + ['--output', str(output)] + args, cwd=ROOT,
                             text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=180)
        logfile.write_text(run.stdout)
        if output == diagnostic and run.returncode:
            raise ValueError('Comparison diagnostic failed: ' + run.stdout)
        if output == negative and (run.returncode == 0 or
                                   'Original Native speed source required' not in run.stdout):
            raise ValueError('Synthetic original comparison was not rejected')
    result = json.loads(diagnostic.read_text())
    if result.get('passed') is not False or result.get('diagnostic_source_shape_passed') is not True:
        raise ValueError('Comparison diagnostic claimed original acceptance')
    rows = []
    for suffix in SUFFIXES:
        receipt = base / suffix / 'primary/processed/v0001/processing.json'
        if not receipt.is_file():
            raise ValueError('Final selected processing receipt missing: ' + suffix)
        rows.append({'case_id': HERE.name + '__' + suffix,
                     'processing_receipt': receipt.relative_to(ROOT).as_posix(),
                     'processing_sha256': sha(receipt)})
    binding = HERE / f'{tag}-selected-comparison-binding.json'
    binding.write_text(json.dumps({
        'format': 'c111294-selected-comparison-binding-v1',
        'comparison_id': HERE.name + '__comparison_main',
        'manifest_sha256': sha(manifest_path),
        'case_plan_sha256': sha(HERE / 'case-plan.json'),
        'comparison_script_sha256': sha(HERE / 'comparison_audit.py'),
        'diagnostic_comparison_sha256': sha(diagnostic),
        'diagnostic_log_sha256': sha(log),
        'original_rejection_log_sha256': sha(negative_log),
        'rows': rows, 'diagnostic_source_shape_passed': True,
        'original_comparison_accepted': False,
        'exact_80_legal_relation': 'unresolved_with_0.2_mph_interval',
    }, indent=2) + '\n')
    print(json.dumps({'comparison_binding_sha256': sha(binding),
                      'members': len(rows), 'original_comparison_accepted': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-tag', required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    main(args.source_tag, args.tag)
