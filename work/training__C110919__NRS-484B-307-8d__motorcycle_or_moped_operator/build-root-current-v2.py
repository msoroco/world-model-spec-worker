"""Materialize the current four-view root package and source observation plan."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    source = json.loads((HERE / 'saved-diagnostic/condition_a/construction.json').read_text())
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    ids = [entry['case_id'] for entry in manifest['cases']]
    bundle = json.loads(json.dumps(source))
    bundle['status'] = 'root_cpu_delivery_interface_original_unverified'
    bundle['measurement_plan'] = source.get('measurement_plan', [])
    bundle['static_checks'] = source.get('static_checks', [])
    for item in bundle['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['status'] = 'root_cpu_delivery_interface_original_unverified'
            config['supported_case_ids'] = ids
            for camera in config['cameras']:
                camera['pose_strategy'] = {
                    'overview': 'fixed_world_intersection',
                    'approach': 'fixed_world_stop_line',
                    'reference_corner': 'fixed_world_signal_corner',
                    'driver_reference': 'motorcycle_attachment',
                }[camera['name']]
                camera['fov_deg'] = {
                    'overview': 90, 'approach': 90,
                    'reference_corner': 85, 'driver_reference': 90,
                }[camera['name']]
            item['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(HERE / 'construction.json', bundle)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'signal, motorcycle body, pedestrians and right turn', 'interval': '0-30 s'},
            {'view': 'approach', 'subject': 'stop line and first crosswalk', 'interval': '0-30 s'},
            {'view': 'reference_corner', 'subject': 'governing red signal and turn context', 'interval': '0-30 s'},
            {'view': 'driver_reference', 'subject': 'motorcycle driver view of pedestrians and traffic', 'interval': '0-30 s'}]}
    channels = {row['name'] for row in bundle['recording_description']['channels']}
    plan['observations'] = [
        {'name': name, 'mandatory': True,
         'purpose': 'Original frame-joined Native source and derived law observation; synthetic CPU proof is diagnostic'}
        for name in sorted(channels)]
    input_ref = f'inputs/{HERE.name}/assignment.json'
    mapping = plan['source_observation_mapping']
    channel_map = {
        'dev.traffic_signal': ['dev.traffic_signal'],
        'drv.signal_cycles': ['dev.traffic_signal', 'motorcycle_detector_request'],
        'ru.motorcycle': ['native_body_pose_control'],
        'ru.moped': [], 'ru.bicycle': [], 'ru.electric_bicycle': [],
        'ru.electric_scooter': [],
        'drv.stopped': ['drv.stopped', 'native_body_pose_control'],
        'kin.time': ['camera_frame_join'],
        'dev.regulatory_sign': [],
        'drv.yields_to': ['drv.yields_to', 'native_body_pose_control'],
        'drv.turning': ['native_body_pose_control'],
    }
    if set(mapping) != set(channel_map):
        raise ValueError('Frozen source observation inventory changed')
    for term, row in mapping.items():
        row['channels'] = channel_map[term]
        row['source_refs'] = [input_ref] if not channel_map[term] else []
        row['evidence'] = ('Selected motorcycle Native source and 600-frame CPU diagnostic; '
                           'original physical observation and independent pixel review remain required.')
    plan['readiness'] = 'selected_cpu_preparation_original_native_pending'
    write(plan_path, plan)
    review_path = HERE / 'native/selection-review.json'
    review = json.loads(review_path.read_text())
    for ref in review['sources']:
        if ref['path'] == f'work/{HERE.name}/case-plan.json':
            ref['sha256'] = sha(plan_path)
    write(review_path, review)
    manifest['selection_review']['sha256'] = sha(review_path)
    write(manifest_path, manifest)
    print(json.dumps({'root_construction_sha256': sha(HERE / 'construction.json'),
                      'case_plan_sha256': sha(plan_path),
                      'execution_manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    build()
