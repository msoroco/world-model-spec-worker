"""Create authored software-only sources for the 299 ft upper-beam proof."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASE = ASSIGNMENT + '__night_299_upper'


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def box(left, right, y):
    return [[left, y - 1], [right, y - 1], [right, y + 1], [left, y + 1]]


def build():
    spec = json.loads((ROOT / 'runtime/fixtures/example.json').read_text())
    files = spec['files']
    mapping = [json.loads(s) for s in files['video_frames.jsonl'].splitlines()]
    trace = [json.loads(s) for s in files['trace.jsonl'].splitlines()]
    if len(mapping) != len(trace) or len(trace) != 9:
        raise ValueError('Pinned schema seed changed')
    bodies, lamps, roadway = [], [], []
    for video, motion in zip(mapping, trace):
        frame, time_s = motion['frame'], motion['time_s']
        if (video['carla_frame'], video['time_s']) != (frame, time_s):
            raise ValueError('Schema seed frame identity changed')
        x, y = motion['position']['x'], motion['position']['y']
        bodies.append({'frame': frame, 'time_s': time_s,
                       'ego_id': 'ego-1', 'lead_id': 'lead-2',
                       'ego_corners_xy': box(x - 2, x + 2, y),
                       'lead_corners_xy': box(x + 2 + 299 * .3048,
                                              x + 7 + 299 * .3048, y),
                       'ego_heading_xy': [1, 0], 'lead_heading_xy': [1, 0]})
        lamps.append({'frame': frame, 'time_s': time_s,
                      'uppermost_distribution': True, 'low_beam_readback': True})
        roadway.append({'frame': frame, 'time_s': time_s, 'ego_id': 'ego-1',
                        'sun_altitude_angle_deg': -10,
                        'waypoint_present': True, 'road_id': 4, 'lane_id': 1,
                        'lane_type_readback': 'Driving'})
    files['following_footprints.jsonl'] = lines(bodies)
    files['headlamp_readbacks.jsonl'] = lines(lamps)
    files['roadway_environment.jsonl'] = lines(roadway)
    files['lighting_context.json'] = json.dumps({
        'lighting_time_applies': True,
        'time_source': 'authored synthetic NRS 484D.100 lighting-time premise for CPU software diagnostic; physical civil time unverified',
    }, indent=2) + '\n'
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = CASE
    manifest['source_run'] = 'synthetic-headlamp-following-software-diagnostic'
    manifest['required_observations'] = []
    files['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    files['fixture-provenance.json'] = json.dumps({
        'scope': 'Authored synthetic body/lamp/roadway/time inputs on pinned graph/trace schema',
        'case_id': CASE, 'physical_evidence': False,
    }, indent=2) + '\n'
    for name in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
        files.pop(name, None)
    source = HERE / 'night-probes/night_299_upper-diagnostic-input.json'
    source.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    rel = source.relative_to(ROOT).as_posix()
    checksum = sha256(source.read_bytes()).hexdigest()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'night_299_upper-diagnostic-input.json',
                           'source': rel, 'sha256': checksum}],
              'generator': {'source': rel, 'sha256': checksum}}
    (HERE / 'night-probes/night_299_upper-diagnostic-recipe.json').write_text(
        json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    build()
