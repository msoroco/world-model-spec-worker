"""Independent controlled comparison of two versus one right-pass requests."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

BASE = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__repeated_right_pass'
SINGLE = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__single_right_pass'
FIXED_SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'road.xodr',
                 'capture/native_map_facts.json')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def lines(spec, name):
    return [json.loads(x) for x in spec['files'][name].splitlines() if x.strip()]


def audit(folder, *, baseline=None, single=None):
    folder = Path(folder)
    manifest = read(folder / 'execution-manifest.json')
    entries = {x['case_id']: x for x in manifest['cases']}
    if BASE not in entries or SINGLE not in entries:
        raise ValueError('Exact two-versus-one comparison cases missing')
    b, s = entries[BASE], entries[SINGLE]
    constructions = [read(folder / x['construction']) for x in (b, s)]
    if any(digest(folder / x['construction']) != x['construction_sha256']
           for x in (b, s)):
        raise ValueError('Comparison construction hash stale')
    configs = [json.loads(next(f['content'] for f in c['files']
                               if f['path'] == 'config.json')) for c in constructions]
    one, two = configs
    fixed = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
             'required_atoms', 'source_packets', 'cameras')
    if any(one[key] != two[key] for key in fixed):
        raise ValueError('Fixed construction differs')
    if one['case']['recording_description'] != two['case']['recording_description']:
        raise ValueError('Recording description differs')
    if one['engineering'] != two['engineering']:
        raise ValueError('Engineering settings differ')
    baseline = baseline or read(folder / 'diagnostic.json')
    single = single or read(folder / 'cases/single_right_pass/diagnostic.json')
    for name in FIXED_SOURCES:
        if baseline['files'][name] != single['files'][name]:
            raise ValueError('Fixed original source differs: ' + name)
    a = lines(baseline, 'right_pass_sources.jsonl')
    z = lines(single, 'right_pass_sources.jsonl')
    motion_a = lines(baseline, 'driving_trace.jsonl')
    motion_z = lines(single, 'driving_trace.jsonl')
    actors_a = lines(baseline, 'following_sources.jsonl')
    actors_z = lines(single, 'following_sources.jsonl')
    if not a or not (len(a) == len(z) == len(motion_a) == len(motion_z)
                     == len(actors_a) == len(actors_z)):
        raise ValueError('Comparison source frame coverage differs')
    changed = []
    for i, (before, after, mb, ma, ab, aa) in enumerate(
            zip(a, z, motion_a, motion_z, actors_a, actors_z)):
        for key in ('frame', 'time_s', 'ego_actor_id', 'fixed_overtaken_actor_id',
                    'ego_station_m', 'lead_station_m', 'lead_xy_m', 'road_id',
                    'driving_lane_id', 'shoulder_lane_id'):
            if before[key] != after[key]:
                raise ValueError('Fixed participant, time or route differs: ' + key)
        if ab['lead'] != aa['lead'] or ab['ego']['actor_id'] != aa['ego']['actor_id']:
            raise ValueError('Fixed ego or overtaken actor differs')
        if before['frame'] in (38039, 38040):
            if (after['right_of_mapped_road_edge_m'] >= 0 or
                    before['right_of_mapped_road_edge_m'] <= 0 or
                    ma['y_m'] == mb['y_m'] or aa['ego']['position_m'] == ab['ego']['position_m']):
                raise ValueError('Second-pass deliberate lateral difference absent')
            changed.append(before['frame'])
        elif (before['ego_xy_m'] != after['ego_xy_m'] or
              before['right_of_mapped_road_edge_m'] != after['right_of_mapped_road_edge_m'] or
              mb != ma or ab != aa):
            raise ValueError('Unplanned original source difference at frame ' + str(i))
    if changed != [38039, 38040]:
        raise ValueError('Second interval comparison missing')
    values = [read(folder / e['compatibility']['receipt'])['measurement_examples']
              ['two_right_pass_observation']['value'] for e in (b, s)]
    if (values[0]['source_status'] != 'candidate' or len(values[0]['episodes']) != 2 or
            values[1]['source_status'] != 'unverified' or len(values[1]['episodes']) != 1):
        raise ValueError('Two-versus-one source measurement differs')
    return {'format': 'worker-repeated-pass-comparison-audit',
            'comparison_id': 'repeated_right_pass_required',
            'case_ids': [BASE, SINGLE],
            'construction_sha256': [b['construction_sha256'], s['construction_sha256']],
            'fixed_original_frames': len(a), 'deliberately_changed_frames': changed,
            'observed_episode_counts': [2, 1], 'auditor_sha256': digest(__file__),
            'scope': 'synthetic source and construction comparison only; no physical or legal finding',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison audit')
    output.write_text(json.dumps(audit(args.folder), indent=2) + '\n')


if __name__ == '__main__':
    main()
