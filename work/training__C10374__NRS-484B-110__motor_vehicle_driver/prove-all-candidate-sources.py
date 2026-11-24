"""Exercise the six retained fallback routes through current fixture and saved source paths.

These are synthetic software diagnostics. They do not establish official zone
designation, CARLA motion, source camera pixels, or statutory outcome.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / 'native' / 'zone'
sys.path.insert(0, str(ZONE))
from finalize_source import finalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                             env=os.environ.copy())
    log.write_text(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(f'{command[2]} failed ({process.returncode}): {log}')
    return sha(log)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-work', type=Path, required=True)
    args = parser.parse_args()
    runtime_work = args.runtime_work.resolve()
    if not runtime_work.is_relative_to((ROOT / '.runtime-work').resolve()):
        raise ValueError('scratch must be under .runtime-work')
    runtime_work.mkdir(parents=True, exist_ok=True)
    report_dir = HERE / 'current-graph-fixture'
    rows = []
    for condition in ('a', 'b'):
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            label = f'condition_{condition}-{candidate}'
            suffix = f'selected_c5852cfd__condition_{condition}'
            bundle = ZONE / 'offline/bundles' / suffix / candidate
            recipe = report_dir / f'{label}-recipe.json'
            raw = runtime_work / f'{label}-raw'
            saved = runtime_work / f'{label}-saved'
            if raw.exists() or saved.exists():
                raise ValueError(f'fresh output required: {label}')
            fixture_log = report_dir / f'{label}-materialize.log'
            fixture_sha = run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                               '--recipe', str(recipe), '--output', str(raw)], fixture_log)
            saved_log = report_dir / f'{label}-saved.log'
            saved_sha = run([sys.executable, str(ZONE / 'saved.py'), '--bundle', str(bundle),
                             '--raw-folder', str(raw), '--saved-folder', str(saved),
                             '--synthetic-cpu'], saved_log)
            result = finalize(bundle, saved, raw)
            expected = 0 if condition == 'b' else None
            measured = result['target_check']['measured']
            if expected is not None and measured != expected:
                raise ValueError(f'outside route overlaps: {label}')
            if condition == 'a' and candidate != 'fallback3' and measured <= 0:
                raise ValueError(f'through route lacks measured overlap: {label}')
            if result['source_kind'] != 'synthetic_cpu' or result['physical_acceptance_claimed']:
                raise ValueError(f'synthetic fixture promoted: {label}')
            rows.append({'condition': condition, 'candidate': candidate,
                         'recipe_sha256': sha(recipe), 'materialize_log_sha256': fixture_sha,
                         'saved_log_sha256': saved_sha, 'overlap_frames': measured,
                         'preparation_receipt_sha256': result['source_bindings']['preparation_receipt_sha256'],
                         'raw_source_reverified': result['source_bindings']['raw_source_reverified'],
                         'frames': 600, 'source_cameras': 4})
    receipt = {'format': 'c10374-all-fallback-source-proof-v1', 'passed': True,
               'finalizer_sha256': sha(ZONE / 'finalize_source.py'),
               'diagnostic_source_kind': 'synthetic_cpu', 'conditions': rows,
               'original_native_observed': False, 'official_zone_designation_verified': False,
               'physical_acceptance_claimed': False, 'legal_outcome_claimed': False}
    out = report_dir / 'all-fallback-source-proof.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'candidates': len(rows), 'receipt_sha256': sha(out)}))


if __name__ == '__main__':
    main()
