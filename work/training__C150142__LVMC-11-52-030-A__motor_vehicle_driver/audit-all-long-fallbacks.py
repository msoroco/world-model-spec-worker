"""Aggregate all 48 independently checked long fallback saved receipts."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASES = ('tour_bus_below', 'tour_bus_at', 'tour_bus_above',
         'tour_bus_no_loading', 'shuttle_bus_below', 'shuttle_bus_at',
         'shuttle_bus_above', 'shuttle_bus_no_loading', 'limo_below',
         'limo_at', 'limo_above', 'limo_no_loading', 'rtc_bus_below',
         'rtc_bus_at', 'rtc_bus_above', 'rtc_bus_no_loading')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prefix(case, candidate):
    if case == 'tour_bus_above' and candidate == 'fallback1':
        return 'update053'
    if case.startswith('tour_bus_'):
        return 'update054'
    if case.startswith('shuttle_bus_'):
        return 'update055'
    if case.startswith('limo_'):
        return 'update056'
    return 'update057'


def frames(case):
    return 36120 if case.endswith('_below') else \
           36122 if case.endswith('_above') else 36121


def audit():
    manifest = ROOT / 'execution-manifest.json'
    manifest_sha = sha(manifest)
    entries = {item['case_id']: item for item in read(manifest)['cases']}
    rows = []
    for case in CASES:
        case_id = ROOT.name + '__' + case
        entry = entries[case_id]
        selected = {item['id']: item for item in entry['candidates']}
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            h = case.replace('_', '-')
            tag = prefix(case, candidate)
            summary_path = ROOT / f'{tag}-{h}-selected-{candidate}-saved.log'
            summary = read(summary_path)
            audit_path = (ROOT / 'update053-first-fallback-audit.json'
                          if tag == 'update053' else
                          ROOT / f'{tag}-{h}-{candidate}-audit.json')
            proof = read(audit_path)
            expected = selected[candidate]['construction_sha256']
            assert proof['passed'] is True
            assert proof['case_id'] == summary['case_id'] == case_id
            assert proof['candidate_id'] == summary['candidate_id'] == candidate
            assert proof['manifest_sha256'] == manifest_sha
            assert proof['construction_sha256'] == expected
            assert proof['processing_sha256'] == summary['processing_sha256']
            assert proof['frames'] == summary['frames'] == frames(case)
            assert summary['passed'] is True
            assert summary['source_decodes'] == 4
            assert summary['final_decode_frames'] == frames(case)
            assert summary['original_native_observed'] is False
            assert summary['physical_acceptance_claimed'] is False
            assert summary['legal_acceptance_claimed'] is False
            rows.append({'case_id': case_id, 'candidate_id': candidate,
                         'frames': frames(case),
                         'construction_sha256': expected,
                         'summary_sha256': sha(summary_path),
                         'audit_sha256': sha(audit_path)})
    assert len(rows) == 48
    return {'format': 'c150142-all-long-fallback-audit-v1',
            'passed': True, 'manifest_sha256': manifest_sha,
            'full_saved_fallbacks': len(rows),
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'rows': rows}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
