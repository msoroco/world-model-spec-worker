"""Independent CPU comparison of upstream reverse control and corner attempt."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_overlap(body, polygon):
    bx, by = [p[0] for p in body], [p[1] for p in body]
    px, py = [p[0] for p in polygon], [p[1] for p in polygon]
    return max(0, min(max(bx), max(px)) - max(min(bx), min(px))) * max(
        0, min(max(by), max(py)) - max(min(by), min(py)))


def source(suffix, remove_native=False):
    letter = {'control': 'c', 'true': 'b'}[suffix]
    spec_path = HERE / f'selected-diagnostic-condition_{letter}.json'
    recipe = read(HERE / f'selected-diagnostic-condition_{letter}-recipe.json')
    if recipe['generator']['sha256'] != sha(spec_path):
        raise ValueError('Comparison source recipe changed')
    files = read(spec_path)['files']
    if remove_native:
        files.pop('native_samples.jsonl', None)
    if 'native_samples.jsonl' not in files:
        raise ValueError('Missing required source: native_samples.jsonl')
    rows = [json.loads(line) for line in files['native_samples.jsonl'].splitlines()]
    if len(rows) != 840 or any(r['native_frame'] != 100 + i or r['video_frame'] != i or
                               abs(r['time_s'] - (i + 1) / 20) > 1e-6 for i, r in enumerate(rows)):
        raise ValueError('Comparison Native frame/time join differs')
    reverse = [r for r in rows if r['signed_forward_velocity_m_s'] < -0.05]
    heading = max(abs((r['heading_deg'] - rows[0]['heading_deg'] + 180) % 360 - 180)
                  for r in reverse)
    intersection = max(body_overlap(r['native_body_xy_m'], r['intersection_polygon_xy_m'])
                       for r in reverse)
    crosswalk = max(body_overlap(r['native_body_xy_m'], r['crosswalk_polygon_xy_m'])
                    for r in reverse)
    return {'frames': len(rows), 'reverse_frames': len(reverse), 'max_heading_deg': heading,
            'max_intersection_box_overlap_m2': intersection, 'max_crosswalk_box_overlap_m2': crosswalk}


def candidate(entry, ident):
    ref = entry if ident == 'primary' else next(x for x in entry['candidates'] if x['id'] == ident)
    path = HERE / ref['construction']
    if sha(path) != ref['construction_sha256']:
        raise ValueError('Comparison construction hash changed')
    bundle = read(path)
    config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
    return ref, config


def proof(suffix, case, ident, construction_sha):
    compat = HERE / f'atom-fixed-{suffix}-{ident}-compatibility-receipt.json'
    saved = HERE / f'atom-fixed-{suffix}-{ident}-saved-receipt.json'
    a, b = read(compat), read(saved)['result']
    if (not a['passed'] or a['case_id'] != case or a['construction_sha256'] != construction_sha
            or not b['passed'] or not b['recorded_only'] or b['missing_evidence']
            or b['case_id'] != case or b['candidate_id'] != ident
            or b['analysis_revision']['construction_sha256'] != construction_sha
            or not b['final_video_checks']['passed'] or b['final_video_checks']['frames'] != 840
            or b['physical_acceptance_claimed'] or b['legal_acceptance_claimed']):
        raise ValueError('Comparison current-runtime receipt differs')


def audit(reject_drift=False, remove_native=False):
    manifest = read(HERE / 'control-proof-manifest.json')
    entries = {e['case_id'].rsplit('__', 1)[-1]: e for e in manifest['cases']}
    if set(entries) != {'false', 'true', 'control'}:
        raise ValueError('Comparison exact cases missing')
    fixed = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'required_atoms',
             'source_packets', 'mandatory_channels', 'recording_description',
             'cameras', 'engineering_knobs')
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        refs = {s: candidate(entries[s], ident) for s in ('control', 'true')}
        a, b = refs['control'][1], refs['true'][1]
        if reject_drift and ident == 'primary':
            b['duration_s'] = 24
        if any(a[key] != b[key] for key in fixed):
            raise ValueError('Comparison fixed condition changed: ' + ident)
        if a['case_suffix'] != 'condition_c' or b['case_suffix'] != 'condition_b':
            raise ValueError('Comparison declared route difference absent')
        for suffix in ('control', 'true'):
            proof(suffix, entries[suffix]['case_id'], ident, refs[suffix][0]['construction_sha256'])
    observations = {s: source(s, remove_native and s == 'control') for s in ('control', 'true')}
    if (observations['control']['max_intersection_box_overlap_m2'] != 0
            or observations['control']['max_crosswalk_box_overlap_m2'] != 0
            or observations['control']['max_heading_deg'] != 0
            or observations['true']['max_intersection_box_overlap_m2'] <= 0
            or abs(observations['true']['max_heading_deg'] - 90) > 1e-6
            or observations['true']['max_crosswalk_box_overlap_m2'] != 0):
        raise ValueError('Comparison prohibited-location contrast differs')
    return {'passed': True, 'fixed_candidate_pairs': 4, 'observations': observations,
            'declared_differences': ['upstream initial position', 'reverse route', 'corner heading'],
            'scope': 'synthetic CPU comparison only; physical/visual/legal outcome unverified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reject-comparison-drift', action='store_true')
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.reject_comparison_drift, args.remove_native_source), indent=2))
