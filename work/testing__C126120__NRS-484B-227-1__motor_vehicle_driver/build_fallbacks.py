"""Build one exact route adjustment for each U-turn physical risk."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ('source_verified_single_movement_uturn',
            'source_verified_multiple_movement_uturn',
            'divider_encroachment_before_opening_uturn')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def adjust(suffix, plan):
    if suffix == SUFFIXES[0]:
        plan['ego_segments'][0]['waypoints_xy_m'][3] = [17, 0]
        plan['ego_route_xy_m'][3] = [17, 0]
    elif suffix == SUFFIXES[1]:
        for phase, endpoint in ((1, -1), (2, 0)):
            plan['ego_segments'][phase]['waypoints_xy_m'][endpoint] = [14.5, -1.5]
        plan['ego_route_xy_m'][4:6] = [[14.5, -1.5], [14.5, -1.5]]
    else:
        plan['ego_segments'][0]['waypoints_xy_m'][2] = [9.5, -1.6]
        plan['ego_route_xy_m'][2] = [9.5, -1.6]
    return plan


def build():
    manifest = json.loads((ROOT / 'review-compat-all-manifest.json').read_text())
    for entry, suffix in zip(manifest['cases'], SUFFIXES):
        folder = ROOT / 'cases' / suffix
        primary = ROOT / entry['construction']
        construction = json.loads(primary.read_text())
        site = adjust(suffix, json.loads((folder / 'site-plan.json').read_text()))
        route = json.loads((folder / 'route-plan.json').read_text())
        route['segments'] = site['ego_segments']
        for name, value in (('site-plan.json', site), ('route-plan.json', route)):
            source = folder / ('fallback1-' + name)
            write(source, value)
            item = next(item for item in construction['files'] if item['path'] == name)
            item['source'] = source.relative_to(REPO).as_posix()
            item['content'] = source.read_text()
        construction['status'] = 'partial_cpu_diagnostic_fallback_route'
        target = folder / 'fallback1-construction.json'
        write(target, construction)
        entry['candidates'] = [{'id': 'fallback1',
                                'construction': target.relative_to(ROOT).as_posix(),
                                'construction_sha256': digest(target),
                                'trigger': {
                                    'source': 'original Native body history and barrier receipt',
                                    'metric': 'minimum complete-body clearance and route completion',
                                    'failure_condition': 'barrier clearance below 0.4 m or declared movement incomplete'},
                                'changed_knobs': ['ego_route_xy_m', 'ego_segments'],
                                'design_rationale': 'Adjust the exact route point while retaining opening and U-turn branch.'}]
    write(ROOT / 'review-fallback-manifest.json', manifest)


if __name__ == '__main__':
    build()
