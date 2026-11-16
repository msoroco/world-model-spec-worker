"""Independent audit of current exact-case diagnostic receipts and raw contrast.

This verifies software sources and comparison isolation, never physical acceptance.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def overlap(body, crosswalk):
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    cx = [point[0] for point in crosswalk]
    cy = [point[1] for point in crosswalk]
    return max(0, min(max(xs), max(cx)) - max(min(xs), min(cx))) * \
        max(0, min(max(ys), max(cy)) - max(min(ys), min(cy)))


def main():
    manifest = read(HERE / 'draft-execution-manifest.json')
    batch = read(ROOT / 'batch.json')
    entries = {e['case_id'].split('__')[-1]: e for e in manifest['cases']}
    if set(entries) != {'condition_a', 'condition_b'}:
        raise ValueError('Exact comparison cases differ')
    measurements = {}
    fixed_configs = {}
    for letter, suffix in (('a', 'condition_a'), ('b', 'condition_b')):
        entry = entries[suffix]
        recipe = read(ROOT / entry['fixture_recipe'])
        spec_path = ROOT / recipe['generator']['source']
        if sha(spec_path) != recipe['generator']['sha256']:
            raise ValueError('Diagnostic generator source changed')
        spec = read(spec_path)
        if len(spec['graphs']) != 480 or {v['path'] for v in spec['videos']} != \
                {name + '.mkv' for name in NAMES}:
            raise ValueError('Four-camera or graph cardinality differs')
        if [g['attributes']['frame'] for g in spec['graphs']] != list(range(100, 580)):
            raise ValueError('Diagnostic graph frame sequence differs')
        for item in recipe['sources']:
            if sha(ROOT / item['source']) != item['sha256']:
                raise ValueError('Retained diagnostic source changed: ' + item['source'])
        source = HERE / 'diagnostic-sources' / suffix
        rows = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
        if len(rows) != 480:
            raise ValueError('Raw Native sample cardinality differs')
        events = [overlap(row['body_xy_m'], row['crosswalk_polygon_xy_m'])
                  for row in rows if row['signed_forward_velocity_m_s'] < -.05]
        area = max(events, default=0)
        if (letter == 'a' and area != 0) or (letter == 'b' and not 3 < area < 4):
            raise ValueError('Raw crosswalk contrast differs')
        refs = [{'id': entry['id'], 'construction': entry['construction'],
                 'construction_sha256': entry['construction_sha256']}] + entry['candidates']
        for ref in refs:
            candidate = ref['id']
            construction_path = HERE / ref['construction']
            if sha(construction_path) != ref['construction_sha256']:
                raise ValueError('Construction differs: ' + suffix + '/' + candidate)
            construction = read(construction_path)
            config = json.loads(next(f['content'] for f in construction['files']
                                     if f['path'] == 'config.json'))
            fixed_configs[(letter, candidate)] = config
            proof = read(HERE / f'v2-proof-{letter}-{candidate}.json')
            if proof.get('format') != 'worker-package-compatibility' or proof.get('passed') is not True or \
                    not CHECKS <= set(proof.get('checks', [])):
                raise ValueError('Incomplete v2 compatibility: ' + suffix + '/' + candidate)
            for key, expected in (
                    ('case_id', entry['case_id']), ('candidate_id', candidate),
                    ('construction_sha256', ref['construction_sha256']),
                    ('runtime_manifest_sha256', batch['runtime']['source_manifest_sha256']),
                    ('fixture_recipe_sha256', sha(ROOT / entry['fixture_recipe'])),
                    ('measurement_contract_sha256', sha(HERE / entry['measurement_contract'])),
                    ('analysis_report_sha256', sha(HERE / f'v2-report-{letter}-{candidate}.json')),
                    ('log_sha256', sha(HERE / f'v2-analysis-{letter}-{candidate}.log')),
                    ('negative_log_sha256', sha(HERE / f'v2-negative-{letter}-{candidate}.log'))):
                if proof.get(key) != expected:
                    raise ValueError('Stale v2 binding ' + key + ': ' + suffix + '/' + candidate)
            if proof.get('negative_removed') != 'native_samples.jsonl' or \
                    proof.get('negative_error_contains') not in \
                    (HERE / f'v2-negative-{letter}-{candidate}.log').read_text():
                raise ValueError('Missing-source negative differs')
            for item in recipe['sources']:
                if proof['fixture_manifest'].get(item['path']) != item['sha256']:
                    raise ValueError('Fixture omitted source: ' + item['path'])
            for name in NAMES:
                if name + '.mkv' not in proof['fixture_manifest']:
                    raise ValueError('Fixture omitted source camera')
            decode = read(HERE / f'v2-decode-{letter}-{candidate}.json')
            if decode.get('passed') is not True or decode.get('frames') != 480:
                raise ValueError('Final full decode differs')
            report = read(HERE / f'v2-report-{letter}-{candidate}.json')
            measured = report['measurements']['backing_crosswalk_relation']['value']
            if abs(measured['max_backing_crosswalk_overlap_m2'] - area) > 1e-6:
                raise ValueError('Saved report differs from independent raw overlap')
            measurements[suffix + '/' + candidate] = area
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = fixed_configs[('a', candidate)]
        b = fixed_configs[('b', candidate)]
        for key in ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz',
                    'required_atoms', 'source_packets', 'mandatory_channels',
                    'recording_description', 'cameras', 'engineering_knobs'):
            if a[key] != b[key]:
                raise ValueError('Comparison fixed condition differs: ' + key)
    print(json.dumps({'passed': True, 'scope': 'strict v2 synthetic diagnostic only',
                      'exact_bundles': len(measurements),
                      'raw_overlap_m2': measurements, 'physical_acceptance': False}))


if __name__ == '__main__':
    main()
