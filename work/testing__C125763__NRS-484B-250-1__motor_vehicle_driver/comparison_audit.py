"""Independent CPU audit of two C125763 entry-order diagnostic constructions.

This verifies source hashes, controlled fixture invariants and body-entry order.
It does not establish Native motion, an official device or a legal conclusion.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def bundle(root, name, construction_path, receipt_path, crossing_path):
    construction = read(construction_path)
    files = {row['path']: row['content'] for row in construction['files']}
    config = json.loads(files['config.json'])
    site = json.loads(files['site.json'])
    receipt = read(receipt_path)
    if receipt.get('passed') is not True or len(receipt.get('checks', [])) != 11:
        raise ValueError(name + ': current compatibility proof missing')
    if receipt.get('construction_sha256') != sha(construction_path):
        raise ValueError(name + ': construction/receipt hash changed')
    if receipt.get('case_id') != construction.get('case_id') or config.get('selected_case_id') != construction.get('case_id'):
        raise ValueError(name + ': exact case identity differs')
    if receipt.get('fixture_manifest', {}).get('crossing_history.jsonl') != sha(crossing_path):
        raise ValueError(name + ': retained crossing source differs from compatibility proof')
    diagnostic_path = root/('diagnostic.json' if name == 'other_first' else 'cases/yield_sign_ego_first/diagnostic.json')
    diagnostic = read(diagnostic_path)
    context_text = diagnostic['files']['junction_context.json']
    context = json.loads(context_text)
    if context['intersection_polygon_xy_m'] != site['crossing_polygon_xy_m']:
        raise ValueError(name + ': diagnostic crossing differs from constructed site')
    if receipt.get('fixture_manifest', {}).get('junction_context.json') != hashlib.sha256(context_text.encode()).hexdigest():
        raise ValueError(name + ': diagnostic context differs from compatibility proof')
    polygon = Polygon(site['crossing_polygon_xy_m'])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(name + ': invalid crossing polygon')
    first = {'ego': None, 'other': None}
    prior = -1
    rows = [json.loads(line) for line in crossing_path.read_text().splitlines() if line.strip()]
    if len(rows) != config['frames'] or config['rate_hz'] != 20 or config['duration_s'] != 45:
        raise ValueError(name + ': source duration/rate changed')
    for row in rows:
        frame = row['frame']
        if frame != prior + 1 and prior != -1:
            raise ValueError(name + ': original frame gap')
        prior = frame
        for role in first:
            body = row[role]
            if body['road_id'] != site['approaches'][role]['road_id']:
                raise ValueError(name + ': road identity changed')
            vertices = body['body_vertices_xy_m']
            if len(vertices) < 4:
                raise ValueError(name + ': incomplete body')
            if first[role] is None and MultiPoint(vertices).convex_hull.intersects(polygon):
                first[role] = {'frame': frame, 'time_s': row['time_s']}
    if any(value is None for value in first.values()):
        raise ValueError(name + ': missing body entry')
    measured = receipt.get('measurement_examples', {}).get('entry_order', {}).get('value')
    if measured != first:
        raise ValueError(name + ': independent entry order differs from compatibility measurement')
    return construction, config, site, receipt, first


def audit(root, ego_source=None):
    base = 'testing__C125763__NRS-484B-250-1__motor_vehicle_driver'
    cases = [
        ('other_first', root/'construction.json', root/'primary-compat-receipt.json', root/'diagnostic-sources/crossing_history.jsonl'),
        ('ego_first', root/'cases/yield_sign_ego_first/construction.json', root/'ego-first-compat-receipt.json', ego_source or root/'cases/yield_sign_ego_first/crossing_history.jsonl'),
    ]
    a = bundle(root, *cases[0])
    b = bundle(root, *cases[1])
    if a[0]['case_id'] != base+'__yield_sign_other_first' or b[0]['case_id'] != base+'__yield_sign_ego_first':
        raise ValueError('Comparison case identities differ')
    if a[0]['law_id'] != b[0]['law_id'] or a[0]['cell_id'] != b[0]['cell_id'] or a[0]['actor'] != b[0]['actor']:
        raise ValueError('Law/cell/actor changed')
    if a[0]['recording_description'] != b[0]['recording_description'] or a[2] != b[2]:
        raise ValueError('Site or recording contract changed')
    for key in ('frames','rate_hz','duration_s','required_atoms'):
        if a[1][key] != b[1][key]:
            raise ValueError('Capture invariant changed: '+key)
    for key in ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
        if a[3]['fixture_manifest'].get(key) != b[3]['fixture_manifest'].get(key):
            raise ValueError('Diagnostic camera source changed: '+key)
    if not (a[4]['other']['time_s'] < a[4]['ego']['time_s'] and b[4]['ego']['time_s'] < b[4]['other']['time_s']):
        raise ValueError('Controlled entry-order contrast missing')
    return {'format':'worker-source-entry-order-comparison','passed':True,
            'case_ids':[a[0]['case_id'],b[0]['case_id']],
            'fixed':['law','cell','actor','site','recording_description','frames','rate','duration','required_atoms','four_diagnostic_camera_streams'],
            'deliberate_difference':'complete-body first-entry order',
            'observed_first_entry':{'other_first':a[4], 'ego_first':b[4]},
            'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--ego-source', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.ego_source), indent=2))
