"""Exercise the exact school-bus source audit as a CPU delivery acceptance check.

The fixture is synthetic. This check never declares Native or legal acceptance.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

root = next(p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file())
package = root / 'work/heldout__C230281__NRS-484B-353-1__motor_vehicle_driver'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--negative-missing-pupil', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((package / 'execution-manifest.json').read_text())
    matches = [e for e in manifest['cases'] if e['case_id'] == args.case]
    if len(matches) != 1:
        raise ValueError('Unknown exact selected case')
    entry = matches[0]
    construction_path = package / entry['construction']
    if hashlib.sha256(construction_path.read_bytes()).hexdigest() != entry['construction_sha256']:
        raise ValueError('Changed exact construction')
    construction = json.loads(construction_path.read_text())
    scripts = [item['content'] for item in construction['files'] if item['path'] == 'delivery_audit.py']
    if len(scripts) != 1:
        raise ValueError('Missing exact independent audit')
    namespace = {'__file__': str(package / 'delivery_audit.py'), '__name__': '_exact_delivery_audit'}
    exec(compile(scripts[0], namespace['__file__'], 'exec'), namespace)
    if namespace['CASE_ID'] != args.case:
        raise ValueError('Audit selects another case')
    attempt = Path(args.attempt).resolve()
    report = Path(args.analysis).resolve()
    if not attempt.is_dir() or report != attempt / 'analysis-report.json':
        raise ValueError('Expected exact saved analysis attempt and report')
    contract = package / entry['measurement_contract']
    if args.negative_missing_pupil:
        with tempfile.TemporaryDirectory(prefix='c230281-delivery-negative-') as temp:
            missing = Path(temp) / 'analysis'
            shutil.copytree(attempt, missing)
            (missing / 'pupil_original.jsonl').unlink()
            namespace['audit'](missing, report, contract)
        raise ValueError('Negative missing-pupil fixture was not rejected')
    checked = namespace['audit'](attempt, report, contract)
    if checked.get('case_id') != args.case or checked.get('frame_count') != 160:
        raise ValueError('Exact full-frame source audit differs')
    if set(checked.get('source_decode', {})) != {
        'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'
    } or not checked.get('software_source_join_passed'):
        raise ValueError('Four source cameras or frame join missing')
    if checked.get('physical_acceptance_claimed') or checked.get('legal_conclusion') is not None:
        raise ValueError('Synthetic fixture asserted physical or legal acceptance')
    print(json.dumps({
        'case_id': args.case, 'cpu_delivery_audit_passed': True,
        'native_source': 'synthetic_fixture', 'all_participants': 'source_joined',
        'time_join': True, 'full_video_decode': True, 'actual_pixels': 'decoded_fixture_pixels',
        'physical_completion': 'unverified', 'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False, 'frame_count': checked['frame_count'],
        'source_decode': checked['source_decode'],
    }, sort_keys=True))

if __name__ == '__main__':
    main()
