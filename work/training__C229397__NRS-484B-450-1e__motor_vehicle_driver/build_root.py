"""Materialize the canonical root package from the selected witness construction."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    bundle = json.loads((FOLDER / 'native/bundles/witness_1/construction.json').read_text())
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    files = {item['path']: item['content'] for item in bundle['files']}
    files['runner.py'] = (FOLDER / 'native/runner.py').read_text()
    config = json.loads(files['config.json'])
    description = json.loads(json.dumps(bundle['recording_description']))
    description['channels'].extend([
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': method, 'time_window': '600 original frames',
         'reference_frame': 'Native world and reviewed source context',
         'uncertainty': 'Original source and authority review required'}
        for name, method in (
            ('drv.standing_or_parked', 'same-tick speed and rest interval'),
            ('st.crosswalk', 'source-reviewed crosswalk polygon'),
            ('rel.occupies', 'vehicle footprint versus crosswalk polygon'),
            ('drv.forced_halt', 'original traffic-conflict context and pixel review'),
            ('dev.human_direction', 'original police-direction context and pixel review'),
            ('dev.traffic_signal', 'original official-device direction and pixel review'))])
    config['recording_description'] = description
    config['supported_case_ids'] = [e['case_id'] for e in manifest['cases']]
    config['cameras'] = [
        {'name': name, 'width': width, 'height': height,
         'pose_strategy': strategy, 'fov_deg': fov}
        for name, width, height, strategy, fov in (
            ('overview', 1920, 1080, 'crosswalk overhead with full approach', 70),
            ('approach', 1280, 720, 'along roadway toward crosswalk', 70),
            ('reference_corner', 1280, 720, 'crosswalk corner and marking', 70),
            ('driver_reference', 1280, 720, 'subject and driver perspective', 70))]
    files['config.json'] = json.dumps(config, indent=2) + '\n'
    for name, content in files.items():
        if name == 'case-plan.json':
            continue
        target = FOLDER / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + '\n')
    root = {key: bundle[key] for key in ('case_id', 'law_id', 'cell_id', 'actor')}
    root['recording_description'] = description
    root.update(entrypoint='runner.py',
                files=[{'path': name, 'content': content.rstrip() + '\n'}
                       for name, content in files.items() if name != 'case-plan.json'],
                measurement_plan={'entrypoint': 'finalize.py',
                    'required_sources': ['crosswalk-source.json',
                        'actor-sources.jsonl', 'camera-frames.jsonl',
                        'exception-context.json', 'road.xodr',
                        'video_frames.jsonl'],
                    'source_review_required': True},
                static_checks=['exact NRS 484B.450(1)(e) source and crosswalk geometry',
                    '600 original frames at 20 Hz with four synchronized cameras'],
                mechanisms=['Native crosswalk polygon and vehicle footprint readback',
                    'stop, stand and park target variants',
                    'source-bound exception authority recorded for later review'],
                termination_rules=['600 original frames',
                    'restore Native world and release owned actors'],
                status='selected_native_cpu_draft_original_capture_pending')
    write(FOLDER / 'construction.json', root)


if __name__ == '__main__':
    build()
