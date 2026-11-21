"""Independent source audit of the current selected JSON adapter CPU matrix."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overlap(body, crossing):
    x, y = [point[0] for point in body], [point[1] for point in body]
    cx, cy = [point[0] for point in crossing], [point[1] for point in crossing]
    return max(0, min(max(x), max(cx))-max(min(x), min(cx))) * \
           max(0, min(max(y), max(cy))-max(min(y), min(cy)))


def audit(inject_missing=False, inject_drift=False):
    manifest = read(HERE/'execution-manifest.json')
    if len(manifest['cases']) != 2:
        raise ValueError('Selected crosswalk pair differs')
    fixed = {}
    areas = {}
    saved_hashes = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        if suffix not in ('a', 'b'):
            raise ValueError('Unknown selected crosswalk condition')
        recipe_path = ROOT/entry['fixture_recipe']
        recipe = read(recipe_path)
        graph_spec = ROOT/recipe['generator']['source']
        if sha(graph_spec) != recipe['generator']['sha256']:
            raise ValueError('Diagnostic graph specification changed')
        graphs = read(graph_spec)['graphs']
        frames_path = HERE/'diagnostic-sources'/('condition_'+suffix)/'capture/native/frames.jsonl'
        if inject_missing and suffix == 'a':
            raise ValueError('Required graph frame source absent')
        frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
        if len(frames) != 480 or len(graphs) != 480:
            raise ValueError('Required graph frame source absent')
        for frame, graph in zip(frames, graphs):
            target = 'capture/native/' + frame['adapter_graph']
            if (graph['path'] != target or not target.endswith('.adapter.json')
                    or frame['base'] != frame['adapter_graph']
                    or frame['abstract'] != frame['adapter_graph']
                    or graph['attributes']['frame'] != frame['frame']):
                raise ValueError('Graph source and adapter frame differ')
        for source in recipe['sources']:
            if sha(ROOT/source['source']) != source['sha256']:
                raise ValueError('Retained source hash changed')
        rows_path = HERE/'diagnostic-sources'/('condition_'+suffix)/'native_samples.jsonl'
        rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
        if len(rows) != 480 or [row['native_frame'] for row in rows] != list(range(100, 580)):
            raise ValueError('Native source frame history incomplete')
        area = max((overlap(row['body_xy_m'], row['crosswalk_polygon_xy_m'])
                    for row in rows if row['signed_forward_velocity_m_s'] < -0.05), default=0)
        if (suffix == 'a' and area != 0) or (suffix == 'b' and not 3 < area < 4):
            raise ValueError('Measured path contrast differs')
        areas[suffix] = area
        refs = [('primary', entry)] + [(candidate['id'], candidate) for candidate in entry['candidates']]
        if [name for name, _ in refs] != ['primary', 'fallback1', 'fallback2', 'fallback3']:
            raise ValueError('Selected candidate inventory differs')
        for name, ref in refs:
            if sha(HERE/ref['construction']) != ref['construction_sha256']:
                raise ValueError('Selected construction hash changed')
            proof = read(HERE/ref['compatibility']['receipt'])
            report = read(HERE/f'update162-{suffix}-{name}-report.json')
            decode = read(HERE/f'update162-{suffix}-{name}-decode.json')
            if (sha(HERE/ref['compatibility']['receipt']) != ref['compatibility']['sha256']
                    or proof.get('passed') is not True or proof['case_id'] != entry['case_id']
                    or proof['candidate_id'] != name
                    or proof['construction_sha256'] != ref['construction_sha256']
                    or proof['fixture_recipe_sha256'] != sha(recipe_path)
                    or proof['analysis_report_sha256'] != sha(HERE/f'update162-{suffix}-{name}-report.json')
                    or proof['log_sha256'] != sha(HERE/ref['compatibility']['log'])
                    or proof['negative_log_sha256'] != sha(HERE/ref['compatibility']['negative_log'])):
                raise ValueError('Current compatibility proof changed')
            if (proof['negative_error_contains'] not in (HERE/ref['compatibility']['negative_log']).read_text()
                    or proof['negative_removed'] != 'native_samples.jsonl'):
                raise ValueError('Missing-source negative not proved')
            if {camera+'.mkv' for camera in CAMERAS} - set(proof['fixture_manifest']):
                raise ValueError('Four camera sources missing')
            if decode.get('passed') is not True or decode.get('frames') != 480:
                raise ValueError('Full decoded video missing')
            measured = report['measurements']['backing_crosswalk_relation']['value']
            if (report['original_joins']['frames'] != 480
                    or measured['source_sha256'] != sha(rows_path)
                    or abs(measured['max_backing_crosswalk_overlap_m2'] - area) > 1e-6):
                raise ValueError('Independent source overlap disagrees with selected analysis')
            saved_log = HERE/(f'update162-{suffix}-primary-saved-audited.log' if name == 'primary'
                              else f'update162-{suffix}-{name}-saved.log')
            saved = read(saved_log)
            attempt = ROOT/'.runtime-work'/(
                f'c110741-update162-{suffix}-saved-audited' if name == 'primary'
                else f'c110741-update162-{suffix}-{name}-saved-matrix')/'attempt'
            selection = read(attempt/'candidate-selection.json')
            if (selection['manifest_sha256'] != sha(HERE/'execution-manifest.json')
                    or selection['construction_sha256'] != ref['construction_sha256']
                    or selection['candidate_id'] != name
                    or saved.get('passed') is not True
                    or saved.get('recorded_only') is not True
                    or saved.get('candidate_id') != name
                    or saved.get('originals_preserved') is not True
                    or saved.get('timestamp_joins', {}).get('frames') != 480
                    or saved.get('physical_acceptance_claimed') is not False
                    or saved.get('legal_acceptance_claimed') is not False):
                raise ValueError('Saved-only selected candidate proof differs')
            saved_hashes[suffix+'/'+name] = sha(saved_log)
            construction = read(HERE/ref['construction'])
            config = json.loads(next(item['content'] for item in construction['files']
                                     if item['path'] == 'config.json'))
            fixed[(suffix, name)] = config
    keys = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'required_atoms',
            'source_packets', 'mandatory_channels', 'recording_description',
            'cameras', 'engineering_knobs')
    for name in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a, b = fixed[('a', name)], fixed[('b', name)]
        if inject_drift and name == 'primary':
            b = dict(b, duration_s=25)
        if any(a[key] != b[key] for key in keys):
            raise ValueError('Comparison fixed condition changed')
    return {'format': 'c110741-update162-selected-cpu-matrix-audit-v1',
            'manifest_sha256': sha(HERE/'execution-manifest.json'),
            'candidates_checked': 8, 'source_frames_per_case': 480,
            'saved_only_candidates_checked': len(saved_hashes),
            'saved_log_sha256': saved_hashes,
            'measured_overlap_m2': areas, 'negative_source_rejections_checked': 8,
            'source_kind': 'synthetic_native_sample', 'original_native_claimed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inject-missing', action='store_true')
    parser.add_argument('--inject-drift', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.inject_missing, args.inject_drift), indent=2))
