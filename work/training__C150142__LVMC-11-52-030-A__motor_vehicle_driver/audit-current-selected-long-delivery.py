"""Recheck current-manifest selected long saved sources without legal claims."""
import hashlib
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(WORK / 'native'))
from delivery_audit import (lines, read, validate_exception_measurement,
                            validate_rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest = read(WORK / 'execution-manifest.json')
    manifest_sha = sha(WORK / 'execution-manifest.json')
    selected = {entry['case_id']: entry for entry in manifest['cases']}
    plan = read(WORK / 'case-plan.json')
    rows = []
    for path in sorted(WORK.glob('current-*-primary-saved-summary.json')):
        summary = read(path)
        if summary['frames'] < 36000:
            continue
        case_id = summary['case_id']
        entry = selected[case_id]
        slug = case_id.rsplit('__', 1)[-1]
        audit_path = path.with_name(path.name.replace('-summary.json', '-audit.json'))
        require(audit_path.is_file(), 'Missing selected audit: ' + slug)
        prior = read(audit_path)
        require(prior['passed'] is True and prior['manifest_sha256'] == manifest_sha and
                prior['construction_sha256'] == entry['construction_sha256'] and
                prior['processing_sha256'] == summary['processing_sha256'],
                'Saved audit differs from current selection: ' + slug)
        processing_path = REPO / summary['processing_ignored_path']
        require(processing_path.is_file() and sha(processing_path) == summary['processing_sha256'],
                'Processing source differs: ' + slug)
        result = processing_path.parent
        analysis = result / 'analysis'
        selection = read(analysis / 'candidate-selection.json')
        require(selection['case_id'] == case_id and selection['candidate_id'] == 'primary' and
                selection['manifest_sha256'] == manifest_sha and
                selection['construction_sha256'] == entry['construction_sha256'],
                'Selected Native source differs: ' + slug)
        checked = validate_exception_measurement(
            analysis, plan, case_id, 'synthetic_native_sample')
        require(checked['frames'] == summary['frames'], 'Measured frame count differs: ' + slug)
        joined = validate_rows(lines(analysis / 'native-raw-actors.jsonl'),
                               lines(analysis / 'video_frames.jsonl'),
                               lines(analysis / 'trace.jsonl'),
                               read(analysis / 'native-map-readback.json'),
                               case_id, checked['frames'],
                               'synthetic_native_sample', True)
        require(joined['red_curb_stop_or_park_observed'] is True,
                'Missing source-observed red curb relation: ' + slug)
        rows.append({'case_id': case_id, 'frames': checked['frames'],
                     'processing_sha256': summary['processing_sha256'],
                     'audit_sha256': sha(audit_path)})
    require(len(rows) == 16, 'Expected all 16 selected long primary cases')
    return {'format': 'c150142-current-long-selected-delivery-diagnostic-v1',
            'passed': True, 'manifest_sha256': manifest_sha, 'rows': rows,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
