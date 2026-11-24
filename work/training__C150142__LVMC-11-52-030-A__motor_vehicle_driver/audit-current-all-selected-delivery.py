"""Bind every selected saved case to source rows and full decode receipts."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(WORK / 'native'))
from delivery_audit import lines, read, validate_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def exception_audit():
    script = WORK / 'audit-current-selected-exception-delivery.py'
    spec = importlib.util.spec_from_file_location('selected_exceptions', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit(), sha(script)


def audit():
    exceptional, script_sha = exception_audit()
    require(exceptional['passed'] is True and len(exceptional['rows']) == 27,
            'Selected exception delivery audit incomplete')
    manifest_path = WORK / 'execution-manifest.json'
    manifest_sha = sha(manifest_path)
    require(exceptional['manifest_sha256'] == manifest_sha,
            'Exception delivery manifest differs')
    selected = {item['case_id']: item for item in read(manifest_path)['cases']}
    short = read(WORK / 'current-short-selected-saved-index.json')
    require(short['passed'] is True and short['manifest_sha256'] == manifest_sha,
            'Selected short processing index differs')
    saved = {row['case']: row for row in short['rows']}
    ordinary = []
    for slug, red in (('reference', True), ('contrast', False),
                      ('ordinary_red_signed', True)):
        row = saved[slug]
        case = WORK.name + '__' + slug
        entry = selected[case]
        require(row['manifest_sha256'] == manifest_sha and
                row['construction_sha256'] == entry['construction_sha256'] and
                row['exit_code'] == 0,
                'Ordinary selected processing differs: ' + slug)
        result = Path(row['scratch_result'])
        require(REPO / '.runtime-work' in result.resolve().parents,
                'Ordinary source outside scratch: ' + slug)
        analysis = result / 'v0001/analysis'
        selection = read(analysis / 'candidate-selection.json')
        require(selection['manifest_sha256'] == manifest_sha and
                selection['construction_sha256'] == entry['construction_sha256'] and
                selection['candidate_id'] == 'primary' and
                selection['case_id'] == case,
                'Ordinary selected source differs: ' + slug)
        processing_path = result / 'v0001/processing.json'
        require(sha(processing_path) == row['processing']['processing']['sha256'] and
                read(processing_path)['recorded_only'] is True,
                'Ordinary saved processing differs: ' + slug)
        joined = validate_rows(lines(analysis / 'native-raw-actors.jsonl'),
                               lines(analysis / 'video_frames.jsonl'),
                               lines(analysis / 'trace.jsonl'),
                               read(analysis / 'native-map-readback.json'),
                               case, row['frames'],
                               'synthetic_native_sample',
                               red if slug == 'ordinary_red_signed' else None)
        decoded = []
        mapping_sha = sha(analysis / 'video_frames.jsonl')
        for index in range(4):
            spec = row['processing']['source-' + str(index)]
            path = WORK / spec['path']
            receipt = read(path)
            require(sha(path) == spec['sha256'] and receipt['passed'] is True and
                    receipt['frames'] == row['frames'] and
                    receipt['mapping_sha256'] == mapping_sha and
                    receipt['checks']['frame_count'] == 'all-decoded-frames',
                    'Ordinary full source decode differs: ' + slug)
            decoded.append(spec['sha256'])
        ordinary.append({'case_id': case, 'frames': row['frames'],
                         'red_curb_stop_or_park_observed':
                             joined['red_curb_stop_or_park_observed'],
                         'processing_sha256': sha(processing_path),
                         'source_decode_receipts': decoded})
    all_cases = {row['case_id'] for row in exceptional['rows'] + ordinary}
    require(len(all_cases) == len(selected) == 30 and all_cases == set(selected),
            'Selected delivery coverage incomplete')
    return {'format': 'c150142-current-all-selected-delivery-diagnostic-v1',
            'passed': True, 'manifest_sha256': manifest_sha,
            'exception_audit_script_sha256': script_sha,
            'exception_audit_receipt_sha256':
                sha(WORK / 'current-selected-exception-delivery-diagnostic.json'),
            'selected_cases': 30, 'exception_cases': 27,
            'ordinary_cases': ordinary,
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
