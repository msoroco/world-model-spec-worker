"""Source-bound CPU proof of commanded opposite-approach left exits.

This checks the intended route only. Observed motion and the statutory turn
judgment require original Native sources and independent review.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from median_route_control import validate_scene
from site_packet import verify_site_packet


HERE = Path(__file__).resolve().parent
SITES = ('fourth-site.json', 'fourth-fallback1-site.json',
         'fourth-fallback2-site.json', 'fourth-fallback3-site.json')


def left_exit_offset(scene):
    other = scene['approaches']['other']
    start, end = other['route_xy_m'][0], other['route_xy_m'][-1]
    ox, oy = other['forward_xy']
    lateral = (ox * (end[1] - start[1]) -
               oy * (end[0] - start[0])) / math.hypot(ox, oy)
    if lateral <= 1:
        raise ValueError('Commanded exit is not left of approach')
    return lateral


def audit():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    case = next(row for row in manifest['cases']
                if row['case_id'].endswith('__stop_opposite_left_turn'))
    candidates = [('primary', case['construction'], case['construction_sha256'])]
    candidates += [(row['id'], row['construction'], row['construction_sha256'])
                   for row in case['candidates']]
    if [row[0] for row in candidates] != ['primary', 'fallback1', 'fallback2', 'fallback3']:
        raise ValueError('Exact opposite-turn candidate set required')
    rows = []
    for name, (candidate, construction_name, construction_hash) in zip(SITES, candidates):
        path = HERE / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        construction_path = HERE / construction_name
        if hashlib.sha256(construction_path.read_bytes()).hexdigest() != construction_hash:
            raise ValueError('Manifest construction hash changed')
        construction = json.loads(construction_path.read_text())
        bundled_site = next(row for row in construction['files']
                            if row['path'] == 'site.json')
        if (bundled_site['content'] != path.read_text() or
                not bundled_site['source'].endswith('/' + name)):
            raise ValueError('Candidate site differs from construction')
        scene = verify_site_packet(
            {'site_packet': {'path': name, 'sha256': digest}}, HERE)
        validate_scene(scene)
        lateral = left_exit_offset(scene)
        for wrong_exit in ([0, 0], [15, 15]):
            wrong = copy.deepcopy(scene)
            wrong['approaches']['other']['route_xy_m'][-1] = wrong_exit
            try:
                validate_scene(wrong)
                left_exit_offset(wrong)
            except ValueError as error:
                if 'not left of approach' not in str(error):
                    raise
            else:
                raise ValueError('Nonleft exit passed route validation')
        rows.append({'candidate': candidate, 'construction_sha256': construction_hash,
                     'site': name, 'sha256': digest,
                     'commanded_left_offset_m': lateral,
                     'straight_and_right_exits_rejected': True})
    return {'format': 'worker-c125745-commanded-turn-route-proof',
            'sites': rows, 'source_bound': True,
            'observed_turn_status': 'unverified',
            'official_device_judgment': 'unresolved',
            'legal_acceptance_claimed': False,
            'physical_acceptance_claimed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
