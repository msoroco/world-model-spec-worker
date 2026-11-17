"""Audit corrected synthetic limousine duration and no-loading comparisons."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = {
    'below': (36120, 1799.95, 'below', 1),
    'at': (36121, 1800, 'at', 1),
    'above': (36122, 1800.05, 'above', 1),
    'no-loading': (36121, 1800, 'at', 0),
}
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
ALLOWED_BOUNDARY_CHANGES = {
    'capture_frames', 'case_id', 'duration_s', 'frames',
    'requested_boundary', 'requested_stationary_duration_s',
    'selected_case_id', 'stationary_frames', 'supported_case_ids',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(loader=read):
    manifest = ROOT / 'execution-manifest-diagnostic-limo_below-draft-v2.json'
    manifest_sha = sha(manifest)
    rows = []
    configs = {}
    for boundary, (frames, duration, relation, activities) in CASES.items():
        audit_path = ROOT / f'update038-limo-{boundary}-fallback-audit-v2.json'
        local = loader(audit_path)
        require(local.get('passed') is True and local.get('manifest_version') == 2 and
                local.get('manifest_sha256') == manifest_sha and
                len(local.get('records', [])) == 4,
                'Boundary fallback audit is incomplete: ' + boundary)
        for candidate in CANDIDATES:
            summary_path = ROOT / f'update038-limo-{boundary}-{candidate}-pinned-saved-v2.json'
            summary = loader(summary_path)
            version = (REPO / '.runtime-work' /
                       f'c150142-limo-{boundary}-{candidate}-result-v2/v0001')
            config = loader(version / 'analysis/config.json')
            require(summary.get('candidate_id') == candidate and
                    summary.get('case_id') == ROOT.name + '__limo_' + boundary.replace('-', '_') and
                    summary.get('processing_passed') is True and
                    summary.get('timestamp_join_frames') == frames and
                    summary.get('final_decode_frames') == frames and
                    summary.get('reported_duration_s') == duration and
                    summary.get('reported_boundary') == relation and
                    summary.get('reported_activity_events') == activities and
                    summary.get('original_native_observed') is False and
                    summary.get('source_kind') == 'synthetic_native_sample',
                    'Statutory boundary observation differs: ' + boundary + '/' + candidate)
            require(any(r.get('candidate_id') == candidate and
                        r.get('processing_sha256') == summary.get('processing_sha256') and
                        r.get('summary_sha256') == sha(summary_path)
                        for r in local['records']),
                    'Boundary fallback audit does not bind summary: ' + boundary + '/' + candidate)
            require(config.get('capture_frames') == frames and
                    config.get('requested_stationary_duration_s') == duration and
                    config.get('requested_boundary') == relation and
                    (config.get('activity_request') is None) == (activities == 0),
                    'Boundary request differs: ' + boundary + '/' + candidate)
            configs[(boundary, candidate)] = config
            rows.append({'boundary': boundary, 'candidate': candidate,
                         'summary_sha256': sha(summary_path),
                         'processing_sha256': summary['processing_sha256']})
    for candidate in CANDIDATES:
        base = configs[('below', candidate)]
        for boundary in ('at', 'above', 'no-loading'):
            other = configs[(boundary, candidate)]
            changed = {key for key in base.keys() | other.keys()
                       if base.get(key) != other.get(key)}
            permitted = ALLOWED_BOUNDARY_CHANGES | ({'activity_request'} if boundary == 'no-loading' else set())
            require(changed <= permitted and
                    {'capture_frames', 'requested_stationary_duration_s'} <= changed,
                    'Cross-boundary fixed conditions differ: ' + boundary + '/' + candidate)
    return {'format': 'c150142-limo-v2-boundary-comparison-audit',
            'passed': True, 'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'manifest_sha256': manifest_sha,
            'candidate_count': len(rows), 'rows': rows,
            'checked_boundaries': list(CASES)}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
