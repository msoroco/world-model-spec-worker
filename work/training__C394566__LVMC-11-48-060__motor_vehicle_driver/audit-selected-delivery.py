"""Independent source and receipt audit of selected synthetic delivery diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case, remove_native_source=False):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    probe = case.rsplit('__', 1)[-1]
    short = 'p01' if probe == 'probe_01' else 'p02'
    spec_path = HERE / ('diagnostic-' + probe + '.json')
    recipe_path = HERE / ('fixture-recipe-' + probe + '.json')
    recipe = read(recipe_path)
    if recipe['generator']['sha256'] != sha(spec_path):
        raise ValueError('Selected diagnostic source hash changed')
    files = read(spec_path)['files']
    if remove_native_source:
        files.pop('native_route_trace.jsonl', None)
    required = ('native_route_trace.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                'route_context.json', 'capture/evidence.jsonl', 'capture/manifest.json')
    for name in required:
        if name not in files:
            raise ValueError('Missing required source: ' + name)
    rows = {name: [json.loads(line) for line in files[name].splitlines()]
            for name in required if name.endswith('.jsonl')}
    if any(len(items) != 600 for items in rows.values()):
        raise ValueError('Original frame or participant count differs')
    context = json.loads(files['route_context.json'])
    if context['case_id'] != case or not context['vehicle_is_truck']:
        raise ValueError('Reviewed route or truck identity differs')
    roads = []
    for i, (native, trace, mapping, evidence) in enumerate(zip(
            rows['native_route_trace.jsonl'], rows['trace.jsonl'],
            rows['video_frames.jsonl'], rows['capture/evidence.jsonl'])):
        frame = 1000 + i
        if (native['native_frame'] != frame or trace['frame'] != frame
                or mapping['carla_frame'] != frame or mapping['video_frame'] != i
                or evidence['original_frame'] != frame or native['ego_actor_id'] != context['ego_actor_id']):
            raise ValueError('Original frame, actor or participant join differs')
        time = (i + 1) / 20
        if abs(trace['time_s'] - time) > 1e-6 or abs(mapping['time_s'] - time) > 1e-6:
            raise ValueError('Original time join differs')
        if not roads or roads[-1] != native['road_id']:
            roads.append(native['road_id'])
    expected = [context['entry_truck_route_id'], context['intervening_street_id'],
                context['exit_truck_route_id']]
    if roads != expected:
        raise ValueError('Original passage over selected roads differs')
    compat = read(HERE / f'compat-{short}-pr/receipt.json')
    saved = read(HERE / f'saved-{short}-processing.json')
    if (not compat['passed'] or compat['case_id'] != case
            or compat['construction_sha256'] != entry['construction_sha256']
            or compat['fixture_recipe_sha256'] != sha(recipe_path)
            or compat['fixture_manifest']['native_route_trace.jsonl'] !=
            hashlib.sha256(files['native_route_trace.jsonl'].encode()).hexdigest()
            or compat['negative_error_contains'] != 'Missing required source: route_context.json'):
        raise ValueError('Compatibility source binding differs')
    if {name + '.mkv' for name in CAMERAS} - set(compat['fixture_manifest']):
        raise ValueError('Four camera source hashes missing')
    if (not saved['passed'] or saved['case_id'] != case or saved['candidate_id'] != 'primary'
            or not saved['recorded_only'] or not saved['originals_preserved']
            or saved['missing_evidence'] or saved['timestamp_joins']['frames'] != 600
            or not saved['timestamp_joins']['passed'] or not saved['final_video_checks']['passed']
            or saved['analysis_revision']['construction_sha256'] != entry['construction_sha256']
            or saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
        raise ValueError('Saved source, conversion or full decode binding differs')
    if saved['original_source_hashes']['native_route_trace.jsonl'] != compat['fixture_manifest']['native_route_trace.jsonl']:
        raise ValueError('Saved original Native route source changed')
    return {'passed': True, 'case_id': case, 'source_frames': 600,
            'road_sequence': roads, 'four_camera_source_hashes': True,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'scope': 'synthetic software source/receipt audit; actual physical pixels and completion remain for local review',
            'accepted': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_native_source), indent=2))


if __name__ == '__main__':
    main()
