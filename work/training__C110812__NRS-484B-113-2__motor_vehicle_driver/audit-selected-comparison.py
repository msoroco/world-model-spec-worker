"""Independent CPU audit of the selected straight/corner diagnostic comparison."""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def construction(entry, candidate):
    reference = entry if candidate == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    path = HERE / reference['construction']
    if sha(path) != reference['construction_sha256']:
        raise ValueError('Selected construction hash changed')
    bundle = read(path)
    return json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))


def sources(entry, suffix, remove_source):
    recipe = HERE / Path(entry['fixture_recipe']).name
    spec_path = HERE / f"selected-diagnostic-condition_{'a' if suffix == 'false' else 'b'}.json"
    if read(recipe)['generator']['sha256'] != sha(spec_path):
        raise ValueError('Selected diagnostic source changed')
    spec = read(spec_path)
    if remove_source:
        spec['files'].pop('native_samples.jsonl')
    if 'native_samples.jsonl' not in spec['files']:
        raise ValueError('Missing required source: native_samples.jsonl')
    rows = [json.loads(line) for line in spec['files']['native_samples.jsonl'].splitlines()]
    if len(rows) != 840 or [r['native_frame'] for r in rows] != list(range(100, 940)):
        raise ValueError('Selected Native frame continuity differs')
    for index, row in enumerate(rows):
        if row['video_frame'] != index or abs(row['time_s'] - (index + 1) / 20) > 1e-6:
            raise ValueError('Selected source time join differs')
    return spec, rows, hashlib.sha256(spec['files']['native_samples.jsonl'].encode()).hexdigest()


def overlap_box(body, polygon):
    bx, by = [p[0] for p in body], [p[1] for p in body]
    px, py = [p[0] for p in polygon], [p[1] for p in polygon]
    return max(0, min(max(bx), max(px)) - max(min(bx), min(px))) * max(
        0, min(max(by), max(py)) - max(min(by), min(py)))


def audit(reject_drift=False, remove_source=False):
    manifest = read(HERE / 'current-runtime-reproof-manifest.json')
    entries = {e['case_id'].rsplit('__', 1)[-1]: e for e in manifest['cases']
               if e['case_id'].rsplit('__', 1)[-1] in ('false', 'true')}
    if set(entries) != {'false', 'true'}:
        raise ValueError('Selected exact pair missing')
    fixed = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'required_atoms',
             'source_packets', 'mandatory_channels', 'recording_description', 'cameras',
             'engineering_knobs')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a, b = (construction(entries[s], candidate) for s in ('false', 'true'))
        if reject_drift and candidate == 'primary':
            b['duration_s'] = 24
        if any(a[key] != b[key] for key in fixed):
            raise ValueError('Comparison fixed condition changed: ' + candidate)
        if a['case_suffix'] != 'condition_a' or b['case_suffix'] != 'condition_b':
            raise ValueError('Selected route variable missing')
        if candidate != 'primary':
            for suffix, entry in entries.items():
                stem = f'current-runtime-{suffix}-{candidate}'
                compatible = read(HERE / (stem + '-compatibility.json'))
                saved = read(HERE / (stem + '-saved-receipt.json'))
                expected = next(c['construction_sha256'] for c in entry['candidates']
                                if c['id'] == candidate)
                if (compatible['case_id'] != entry['case_id']
                        or compatible['candidate_id'] != candidate
                        or compatible['construction_sha256'] != expected
                        or not compatible['passed']
                        or compatible['negative_error_contains'] != 'Missing required source: native_samples.jsonl'
                        or saved['source']['fixture_sha256'] != compatible['fixture_sha256']
                        or saved['result']['analysis_revision']['construction_sha256'] != expected
                        or saved['result']['candidate_id'] != candidate
                        or not saved['result']['recorded_only']
                        or saved['result']['missing_evidence']
                        or saved['result']['physical_acceptance_claimed']
                        or saved['result']['legal_acceptance_claimed']
                        or saved['result']['final_video_checks']['frames'] != 840):
                    raise ValueError('Selected fallback proof differs: ' + stem)
    observations = {}
    for suffix, entry in entries.items():
        spec, rows, sample_sha = sources(entry, suffix, remove_source and suffix == 'true')
        compat_path = HERE / f'current-runtime-{suffix}-primary-compatibility.json'
        saved_path = HERE / f'current-runtime-{suffix}-primary-saved-receipt.json'
        compat, saved = read(compat_path), read(saved_path)
        selected_sha = entry['construction_sha256']
        if (compat['case_id'] != entry['case_id'] or compat['construction_sha256'] != selected_sha
                or compat['fixture_recipe_sha256'] != sha(HERE / Path(entry['fixture_recipe']).name)
                or compat['fixture_manifest']['native_samples.jsonl'] != sample_sha
                or compat['negative_error_contains'] != 'Missing required source: native_samples.jsonl'
                or not compat['passed']):
            raise ValueError('Selected compatibility/source binding differs')
        if {name + '.mkv' for name in NAMES} - set(compat['fixture_manifest']):
            raise ValueError('Four selected source cameras missing')
        result = saved['result']
        if (saved['source']['fixture_sha256'] != compat['fixture_sha256']
                or result['case_id'] != entry['case_id'] or result['candidate_id'] != 'primary'
                or result['analysis_revision']['construction_sha256'] != selected_sha
                or not result['recorded_only'] or not result['originals_preserved']
                or result['missing_evidence'] or result['physical_acceptance_claimed']
                or result['legal_acceptance_claimed'] or not result['final_video_checks']['passed']
                or result['final_video_checks']['frames'] != 840):
            raise ValueError('Selected recorded-only proof differs')
        start = rows[0]['heading_deg']
        reversing = [row for row in rows if row['signed_forward_velocity_m_s'] < -.05]
        heading = max(abs((row['heading_deg'] - start + 180) % 360 - 180) for row in reversing)
        crosswalk = max(overlap_box(row['body_xy_m'], row['crosswalk_polygon_xy_m']) for row in reversing)
        intersection = max(overlap_box(row['body_xy_m'], row['intersection_polygon_xy_m']) for row in reversing)
        observations[suffix] = {'reverse_frames': len(reversing), 'max_heading_deg': heading,
                                'max_crosswalk_box_overlap_m2': crosswalk,
                                'max_intersection_box_overlap_m2': intersection}
    if (observations['false']['max_heading_deg'] != 0
            or abs(observations['true']['max_heading_deg'] - 90) > 1e-6
            or any(row['max_crosswalk_box_overlap_m2'] != 0 for row in observations.values())
            or any(row['max_intersection_box_overlap_m2'] <= 0 for row in observations.values())):
        raise ValueError('Selected straight/corner diagnostic contrast differs')
    return {'passed': True, 'exact_cases': [entries[s]['case_id'] for s in ('false', 'true')],
            'fixed_candidate_pairs': 4, 'observations': observations,
            'scope': 'synthetic CPU comparison only; no Native physical or legal acceptance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reject-comparison-drift', action='store_true')
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.reject_comparison_drift, args.remove_native_source), indent=2))
