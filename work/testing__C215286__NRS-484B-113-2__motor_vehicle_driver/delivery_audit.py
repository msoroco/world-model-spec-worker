"""Exact reverse-case software delivery audit boundary; no Native acceptance."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(REPO / '.runtime-work' / 'c215286-delivery-audit'))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report
from delivery_source_audit import audit as audit_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_delivery(attempt, case_id):
    attempt = Path(attempt)
    source = audit_sources(attempt, case_id, diagnostic=True)
    if source['frames'] != 900 or not source['full_duration_observed']:
        raise ValueError('Full original 900-frame duration required')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unselected exact reverse case')
    construction = HERE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction source changed')
    contract = json.loads((HERE / entry['measurement_contract']).read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    code = next(item['content'] for item in json.loads(construction.read_text())['files']
                if item['path'] == entry['measurement_procedure']['entrypoint'])
    validate(contract, plan['requirement_dispositions'], code, case_id)
    report = json.loads((attempt / 'analysis-report.json').read_text())
    measured = verify_report(contract, report, attempt)
    result = json.loads((attempt / 'result.json').read_text())
    if any(result.get('physical_checks', {}).get(key, {}).get('status') != 'met'
           for key in ('setup', 'target', 'maneuver', 'attempt')):
        raise ValueError('Full-duration physical checker fixture did not complete')
    return {'format': 'worker-c215286-delivery-cpu-boundary', 'case_id': case_id,
            'source_audit_sha256': sha(HERE / 'delivery_source_audit.py'),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'result_sha256': sha(attempt / 'result.json'),
            'measurement_keys': sorted(measured), 'frames': 900,
            'software_audit_passed': True, 'native_source_accepted': False,
            'actual_pixels_reviewed': False, 'physical_acceptance_claimed': False,
            'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    kind = 'over' if args.case.endswith('__reverse_over_crosswalk') else 'short'
    if kind == 'short' and not args.case.endswith('__reverse_stops_before_crosswalk'):
        raise ValueError('Unselected reverse case')
    attempt = REPO / '.runtime-work' / 'c215286-full-stage' / '.runtime-work' / (kind + '-primary')
    if args.mode == 'positive':
        print(json.dumps(audit_delivery(attempt, args.case), sort_keys=True))
    else:
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c215286-audit-negative-') as tmp:
            altered = Path(tmp) / 'attempt'
            shutil.copytree(attempt, altered, copy_function=os.link)
            path = altered / 'video_frames.jsonl'
            original = path.read_bytes()
            path.unlink()
            path.write_bytes(original.replace(b'"video_frame":0', b'"video_frame":1', 1))
            audit_delivery(altered, args.case)
        raise AssertionError('Changed original video frame map was accepted')


if __name__ == '__main__':
    main()
