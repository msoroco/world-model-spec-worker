"""Independent source comparison of the two C190631 walking surfaces."""
import argparse
import hashlib
import json
from pathlib import Path

from native.measure import measure

AID = 'training__C190631__LVMC-11-30-090__pedestrian'
CASES = (AID + '__probe_01', AID + '__probe_02')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(locations, diagnostic=False):
    require(len(locations) == 2, 'Two exact walking-surface attempts required')
    fixed = None
    findings = []
    for case, location, surface in zip(CASES, locations, ('sidewalk', 'roadway')):
        root = Path(location)
        for name in ('config.json', 'road.xodr', 'surface-geometry.json',
                     'pedestrian-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                     *(camera + '.mkv' for camera in CAMERAS)):
            require((root / name).is_file(), 'Missing comparison source: ' + name)
        config = read(root / 'config.json')
        geometry = read(root / 'surface-geometry.json')
        require(config.get('case_id') == case and config.get('actor') == 'pedestrian'
                and config.get('cell_id') == 'C190631'
                and config.get('law_id') == 'LVMC-11-30-090'
                and config.get('walking_surface') == surface,
                'Exact walking-surface case or frozen identity differs')
        require(geometry.get('sidewalk_provided') is True and
                geometry.get('adjacent') is True and
                set(geometry.get('native_readback', {})) == {'roadway', 'sidewalk', 'lower_road'},
                'Provided adjacent sidewalk or Native survey source missing')
        if not diagnostic:
            require((root / 'acquisition-provenance.json').is_file(),
                    'Original Native walking-surface source absent')
            provenance = read(root / 'acquisition-provenance.json')
            require(provenance.get('provenance_kind') == 'native' and
                    provenance.get('diagnostic_fixture') is False and
                    geometry.get('source_status') == 'original_native_map_readback',
                    'Original Native walking-surface source absent')
        samples = [json.loads(row) for row in (root / 'pedestrian-poses.jsonl').read_text().splitlines()]
        trace = [json.loads(row) for row in (root / 'trace.jsonl').read_text().splitlines()]
        mapping = [json.loads(row) for row in (root / 'video_frames.jsonl').read_text().splitlines()]
        require(len(samples) == len(trace) == len(mapping) == 600,
                'Full original pedestrian comparison history missing')
        for index, (pose, state, frame) in enumerate(zip(samples, trace, mapping)):
            require(pose.get('video_frame') == frame.get('video_frame') == index
                    and pose.get('native_frame') == state.get('frame') == frame.get('carla_frame')
                    and abs(pose['time_s'] - state['time_s']) < 1e-4
                    and abs(pose['time_s'] - frame['time_s']) < 1e-4,
                    'Original pedestrian comparison frame/time join differs')
        measurement = measure(root / 'pedestrian-poses.jsonl', root / 'surface-geometry.json')
        require(measurement['frames'] == 600 and
                measurement[surface + '_occupied_frames'] == 600 and
                measurement[('roadway' if surface == 'sidewalk' else 'sidewalk') + '_occupied_frames'] == 0,
                'Deliberate walking-surface occupancy contrast absent')
        camera = tuple((row['name'], row['width'], row['height'], row['fov_deg'])
                       for row in config['cameras'])
        common = (sha(root / 'road.xodr'), geometry['roadway_xy_m'],
                  geometry['sidewalk_xy_m'], geometry['native_readback'],
                  camera, config['rate_hz'], config['duration_s'],
                  samples[0]['walker_blueprint_id'],
                  round(measurement['path_length_m'], 3))
        if fixed is None:
            fixed = common
        else:
            require(common == fixed, 'Fixed road, surveyed surfaces, walker, route, cameras or timing differ')
        findings.append({'case_id': case, 'surface': surface,
                         'measurement': measurement,
                         'poses_sha256': sha(root / 'pedestrian-poses.jsonl'),
                         'geometry_sha256': sha(root / 'surface-geometry.json')})
    require(findings[0]['poses_sha256'] != findings[1]['poses_sha256'],
            'Comparison cases reuse one original pedestrian pose source')
    return {'format': 'worker-walking-surface-comparison-audit',
            'comparison_id': AID + '__planned_comparison',
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_source_review',
            'fixed_conditions_checked': True, 'walking_surface_difference_checked': True,
            'cases': findings, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dirs', nargs=2, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.source_dirs, args.diagnostic)
    output = Path(args.output)
    require(not output.exists(), 'Retain previous comparison audit output')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS exact comparison source, fixed controls and walking-surface contrast')
