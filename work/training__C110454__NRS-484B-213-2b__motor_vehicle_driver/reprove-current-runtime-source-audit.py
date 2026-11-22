"""Independently check all retained current diagnostic camera/source chains."""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
if not output_root or ROOT / '.runtime-work' not in Path(output_root).resolve().parents:
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
sys.path.insert(0, str(HERE))
from camera_lifecycle_audit import audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = HERE / 'current-runtime-reproof-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    rows = []
    case_filter = set(os.environ.get('C110454_CASE_FILTER', '').split(',')) - {''}
    candidate_filter = set(os.environ.get('C110454_CANDIDATE_FILTER', '').split(',')) - {''}
    for entry in entries:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if case_filter and suffix not in case_filter:
            continue
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            if candidate_filter and candidate not in candidate_filter:
                continue
            selected = entry if candidate == 'primary' else next(
                c for c in entry['candidates'] if c['id'] == candidate)
            proof_dir = HERE / 'current-runtime-selected-proof' / suffix / candidate
            receipt = proof_dir / 'compatibility.json'
            if not receipt.is_file():
                raise ValueError('Current compatibility proof missing: ' + suffix + '/' + candidate)
            attempts = [p for p in (ROOT / '.runtime-work').glob(
                f'c110454-current-{suffix}-{candidate}-*-compat')
                if (p / 'compatibility.json').is_file() and
                sha(p / 'compatibility.json') == sha(receipt)]
            if not attempts:
                raise ValueError('Retained attempt missing: ' + suffix + '/' + candidate)
            attempt = max(attempts, key=lambda p: p.stat().st_mtime_ns)
            saved_log = proof_dir / 'saved-command.log'
            source = audit(attempt, saved_log, entry['case_id'], candidate,
                           selected['construction_sha256'], diagnostic=True)
            if not source['camera_source_shape_passed'] or source['passed'] or source['delivery_accepted']:
                raise ValueError('Diagnostic source audit differs: ' + suffix + '/' + candidate)
            try:
                audit(attempt, saved_log, entry['case_id'], candidate,
                      selected['construction_sha256'], diagnostic=False)
            except ValueError:
                pass
            else:
                raise AssertionError('Synthetic source accepted as original')
            output = proof_dir / 'source-camera-audit.json'
            output.write_text(json.dumps(source, indent=2) + '\n')
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'receipt': str(output.relative_to(HERE)), 'sha256': sha(output),
                         'original_acceptance_rejected': True})
            print(suffix, candidate, 'diagnostic source passed', flush=True)
    if case_filter or candidate_filter:
        return
    if len(rows) != 36:
        raise ValueError('Thirty-six source audits required')
    index = {'format': 'c110454-current-runtime-source-audit-v1',
             'manifest_sha256': sha(manifest), 'candidate_count': len(rows),
             'rows': rows, 'original_native_or_delivery_acceptance_claimed': False}
    output = HERE / 'current-runtime-selected-source-audit.json'
    output.write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    main()
