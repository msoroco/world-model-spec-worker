"""Add a synthetic slower right-lane target source to the center diagnostic.

This checks data paths only; it does not portray a physically recorded pass.
"""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(center):
    changed = deepcopy(center)
    files = changed['files']
    rows = []
    for line in files['three_lane_frames.jsonl'].splitlines():
        lane = json.loads(line)
        corners = lane['ego_corners_xy']
        ego_x = sum(point[0] for point in corners) / len(corners)
        ego_y = sum(point[1] for point in corners) / len(corners)
        right = lane['lane_polygons_xy']['right']
        middle = lane['lane_polygons_xy']['center']
        right_y = sum(point[1] for point in right) / len(right)
        center_y = sum(point[1] for point in middle) / len(middle)
        target_x = ego_x + 2
        rows.append({'frame': lane['frame'], 'time_s': lane['time_s'],
            'ego_actor_id': lane['ego_actor_id'], 'target_actor_id': 'synthetic-206',
            'ego_center_xy': [ego_x, ego_y], 'target_center_xy': [target_x, right_y],
            'target_corners_xy': [[target_x-1, right_y-.6], [target_x+1, right_y-.6],
                                  [target_x+1, right_y+.6], [target_x-1, right_y+.6]],
            'right_lane_center_xy': [ego_x, right_y],
            'center_lane_center_xy': [ego_x, center_y],
            'other_vehicle_bodies': [{'actor_id': 'synthetic-206',
                                      'center_xy': [target_x, right_y],
                                      'half_length_m': 1, 'half_width_m': .6}],
            'clear_target_m': 65.0})
    files['passing_frames.jsonl'] = ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = HERE.name + '__center_passing_clear'
    files['capture/manifest.json'] = json.dumps(manifest, indent=2)+'\n'
    files['passing-diagnostic-provenance.json'] = json.dumps({
        'format':'worker-diagnostic-source-note',
        'source':'center-default-diagnostic.json',
        'use':'synthetic stationary right-lane target source; tests finalizer and converter only; no actual pass or visible target claimed',
        'builder':'build_center_passing_clear_diagnostic.py'})+'\n'
    return changed


def main():
    source = json.loads((HERE/'center-default-diagnostic.json').read_text())
    target = HERE/'center-passing-clear-diagnostic.json'
    target.write_text(json.dumps(build(source), separators=(',',':'), allow_nan=False)+'\n')
    recipe = {'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
        'source':'work/' + HERE.name + '/' + target.name,
        'sha256':sha256(target.read_bytes()).hexdigest()}],
        'generator':{'source':'work/' + HERE.name + '/' + target.name,
        'sha256':sha256(target.read_bytes()).hexdigest()}}
    (HERE/'center-passing-clear-diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(target, target.stat().st_size)


if __name__ == '__main__':
    main()
