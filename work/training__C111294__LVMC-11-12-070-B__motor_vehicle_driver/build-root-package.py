"""Materialize the first exact Native construction as the package root."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = json.loads((HERE / 'draft-primary/construction.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [case['case_id'] for case in plan['cases']]
    if source['case_id'] != ids[0] or len(ids) != 2:
        raise ValueError('Exact selected pair differs')
    files = []
    for item in source['files']:
        path = item['path']
        content = item['content']
        if path == 'config.json':
            config = json.loads(content)
            config['supported_case_ids'] = ids
            config['status'] = 'selected_delivery_cpu_prepared'
            for camera in config['cameras']:
                camera['fov_deg'] = 85 if camera['name'] != 'driver_reference' else 90
                camera['pose_strategy'] = ('ego' if camera['name'] == 'driver_reference'
                                           else 'world')
                camera['fps'] = 20
            content = json.dumps(config, indent=2) + '\n'
        target = HERE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + '\n')
        files.append({'path': path, 'content': target.read_text()})
    construction = dict(source)
    construction['format'] = 'worker-inline-construction'
    construction['status'] = 'selected_delivery_cpu_prepared'
    construction['files'] = files
    construction['measurement_plan'] = {
        'method': 'Retain original Native two-actor pose, road, lane and frame-source joins; classify requested phases without legal verdict',
        'status': 'cpu_prepared_original_native_unobserved'}
    construction['mechanisms'] = [
        'Authored OpenDRIVE through and entrant roads',
        'Independent through-yield versus through-pass controller requests',
        'Four synchronized Native source cameras']
    construction['static_checks'] = [
        'Exact law, cell and actor identity',
        '600 frames at 20 Hz with original frame and time joins',
        'Through and entrant road/lane roles and source hashes']
    construction['termination_rules'] = [
        'Retain all original 600 frames and four synchronized camera sources',
        'Restore the prior world and preserve failure feedback']
    channels = construction['recording_description']['channels']
    known = {entry['name'] for entry in channels}
    for name in sorted({name for item in plan['source_observation_mapping'].values()
                        for name in item['channels']} | {item['name'] for item in plan['observations']}):
        if name in known:
            continue
        channels.append({'name': name, 'unit': 'source_observation', 'sampling_rate_hz': 20,
                         'method': 'Original Native two-actor pose, road, lane and time source review',
                         'time_window': '600-frame attempt',
                         'reference_frame': 'original Native frame identity',
                         'uncertainty': 'Physical and legal review pending'})
    (HERE / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'both actor bodies and through intersection', 'interval': 'full 30 s'},
            {'view': 'approach', 'subject': 'through driver approach and yield response', 'interval': 'full 30 s'},
            {'view': 'reference_corner', 'subject': 'entrant prior stop and conflict crossing', 'interval': 'full 30 s'},
            {'view': 'driver_reference', 'subject': 'through driver view and entrant timing', 'interval': 'full 30 s'}]}
    (HERE / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'materialized_files': len(files), 'channels': len(channels)}))


if __name__ == '__main__':
    main()
