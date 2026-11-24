"""Pinned C111603 original capture entrypoint and source assembly.

A source-shape check never starts CARLA. Original capture remains unaccepted until
independent pixel, physical and legal review is recorded separately.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
NATIVE = HERE / 'work' / 'training__C111603__NRS-484B-307-9a__motor_vehicle_driver' / 'native'
if (HERE / 'native').is_dir():
    NATIVE = HERE / 'native'
sys.path.insert(0, str(NATIVE))
from build import FRAMES, RATE, check
from capture import capture

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in values))


def selected_bundle(root):
    selection = json.loads((root / 'candidate-selection.json').read_text())
    case = selection['case_id']
    candidate = selection['candidate_id']
    suffix = case.rsplit('__', 1)[-1]
    bundle = root / 'work' / 'training__C111603__NRS-484B-307-9a__motor_vehicle_driver' / 'native' / 'drafts' / suffix / candidate
    check(bundle)
    if json.loads((bundle / 'config.json').read_text())['case_id'] != case:
        raise ValueError('Selected case differs from Native bundle')
    return bundle


def assemble(root, bundle):
    """Derive canonical sources only from captured original actor/camera rows."""
    root, bundle = Path(root), Path(bundle)
    raw = rows(root / 'native-raw-actors.jsonl')
    video = rows(root / 'video_frames.jsonl')
    if len(raw) != FRAMES or len(video) != FRAMES:
        raise ValueError('Original capture requires 600 joined frames')
    report = json.loads((root / 'native-capture-report.json').read_text())
    mapping = json.loads((root / 'native-map-readback.json').read_text())
    if report['error'] or report['observed_frames'] != FRAMES or mapping['source_kind'] != 'original_native':
        raise ValueError('Incomplete original Native capture')
    recorder = root / 'capture/recorder_info.txt'
    if not recorder.is_file() or not recorder.read_text().strip():
        raise ValueError('Actual CARLA recorder info required')
    trace, evidence, frame_index = [], [], []
    for index, (observed, image) in enumerate(zip(raw, video)):
        frame = observed['native_frame']
        time_s = observed['time_s']
        if (observed['frame'] != index or image['video_frame'] != index or
                image['native_frame'] != frame or image.get('carla_frame') != frame or
                abs(image['time_s'] - time_s) > 1e-6):
            raise ValueError('Original actor and camera identities differ')
        ego, other = observed['ego'], observed['other_vehicle']
        center = ego['center_native_xyz_m']
        velocity = ego['velocity_native_xyz_mps']
        speed = math.sqrt(sum(component * component for component in velocity))
        weather = observed['weather_readback']
        trace.append({'frame': frame, 'time_s': time_s,
            'position': dict(zip(('x', 'y', 'z'), center)), 'position_m': center,
            'heading_deg': ego['yaw_deg'], 'speed_mps': speed,
            'velocity_mps': velocity, 'speed_mph': speed / .44704,
            'speed_provenance': 'original_native_velocity',
            'control': {'throttle': None, 'brake': None}})
        evidence.append({'original_frame': frame, 'recording_time_s': time_s,
            'replay_frame': frame, 'replay_simulation_time_s': time_s,
            'actor_id': ego['actor_id'],
            'ego': {'position_m': center, 'heading_deg': ego['yaw_deg'],
                'speed_mps': speed, 'speed_provenance': 'original_native_velocity',
                'body_vertices_m': ego['body_native_xyz_m']},
            'world': {'weather': weather}})
        relative = f'graphs/base/{frame:08d}.adapter.json'
        frame_index.append({'frame': frame, 'simulation_time': time_s,
            'adapter_graph': relative, 'base': relative, 'nodes': 2, 'edges': 0})
        nodes = []
        for label, actor in (('ego', ego), ('other', other)):
            yaw = math.radians(actor['yaw_deg'])
            nodes.append({'id': label, 'attributes': {'sem_class': 'car',
                'entity_id': actor['actor_id'], 'vertex': actor['center_native_xyz_m'],
                'forward': [math.cos(yaw), math.sin(yaw), 0],
                'threedbbox': actor['body_native_xyz_m']}})
        graph = {'attributes': {'frame': frame, 'simulation_time_s': time_s,
            'source_kind': 'original_native'}, 'nodes': nodes, 'edges': []}
        graph_path = root / 'capture/native' / relative
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(graph, separators=(',', ':'), allow_nan=False) + '\n')
    write_rows(root / 'trace.jsonl', trace)
    write_rows(root / 'capture/evidence.jsonl', evidence)
    write_rows(root / 'capture/native/frames.jsonl', frame_index)
    road = root / 'road.xodr'
    if not road.is_file() or sha(road) != sha(bundle / 'arrow-intersection.xodr'):
        raise ValueError('Original road source differs from selected bundle')
    (root / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': FRAMES,
        'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(root / 'trace.jsonl'),
            'native-raw-actors.jsonl': sha(root / 'native-raw-actors.jsonl'),
            'video_frames.jsonl': sha(root / 'video_frames.jsonl'),
            'recorder_info.txt': sha(recorder)},
        'source_kind': 'original_native', 'synthetic_diagnostic': False}, indent=2) + '\n')
    cfg = json.loads((root / 'config.json').read_text())
    result = {'case_id': cfg['case_id'],
        'measured_values': {'arrow_movement': {'frames': FRAMES,
            'observed_heading_change_deg': abs((raw[-1]['ego']['yaw_deg'] - raw[0]['ego']['yaw_deg'] + 180) % 360 - 180),
            'directional_arrow_pixels_verified': False, 'governing_direction_verified': False,
            'other_traffic_lawfulness_verified': False}},
        'target_checks': [{'target': 'source_join', 'requested': FRAMES, 'measured': FRAMES,
            'method': 'original actor and camera frame identity join', 'tolerance': 0,
            'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': ['native-raw-actors.jsonl', 'video_frames.jsonl']}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'Full original capture recorded; physical and pixel review pending',
        'physical_failure_flags': ['directional_arrow_pixels_and_governance_unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': [{'name': 'native_actor_signal_samples', 'unit': 'structured',
            'reference': 'native-raw-actors.jsonl'}],
        'realized_observables': {'heading_change_deg': {'value': abs((raw[-1]['ego']['yaw_deg'] - raw[0]['ego']['yaw_deg'] + 180) % 360 - 180),
            'unit': 'deg', 'method': 'original Native actor readback', 'time_window': '30 s',
            'statistic': 'start_to_end', 'reference': 'native-raw-actors.jsonl'}},
        'provenance_kind': 'native', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return {'frames': FRAMES, 'trace_sha256': sha(root / 'trace.jsonl')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    root = Path.cwd()
    bundle = selected_bundle(root)
    if args.check:
        print(json.dumps({'case_id': json.loads((bundle / 'config.json').read_text())['case_id'],
            'bundle_checked': True, 'native_contacted': False}))
        return
    if args.output_dir is None or args.output_dir.resolve() != root.resolve():
        parser.error('--output-dir must be the materialized attempt directory')
    scratch = Path(os.environ.get('TMPDIR', '')).resolve()
    if not scratch.exists() or not any(part.name == '.runtime-work' for part in (scratch, *scratch.parents)):
        raise ValueError('Set TMPDIR to a scratch directory under .runtime-work before Native capture')
    try:
        capture(bundle, root, args.host, args.port)
        print(json.dumps(assemble(root, bundle)))
        from worker_exchange.native_output import seal_capture
        report = json.loads((root / 'native-capture-report.json').read_text())
        seal_capture(root, frames=FRAMES, restoration=report['restoration'], errors=report['error'],
            encoder_exit_codes={name: 0 for name in CAMERAS}, context={'case_id': report['case_id']})
    except BaseException as exc:
        (root / 'native-run-status.json').write_text(json.dumps({'errors': [str(exc)]}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()
