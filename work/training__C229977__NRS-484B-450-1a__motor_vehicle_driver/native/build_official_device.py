"""Build a device-candidate pair; official status is deliberately unverified."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parent.parent
ASSIGNMENT = FOLDER.name
SUFFIXES = ('official_device_absent', 'official_device_present')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    base = json.loads((FOLDER / 'selected-probe-2' / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in base['files']
                             if item['path'] == 'config.json'))
    description = json.loads(json.dumps(base['recording_description']))
    description['context_inputs'].append({
        'name': 'device_candidate_trajectory', 'unit': 'structured',
        'method': 'original post-tick separate traffic-control-device candidate frame/time/pose; official status and direction require independent review'})
    source = 'NRS 484B.450(1)(a); with 484B.450(3)'
    contract = {'format': 'worker-measurement-contract', 'requirements': [
        {'disposition_index': 0, 'requirement': 'NRS-484B-450-1a',
         'source': source, 'output_key': 'sidewalk_stop_occupancy',
         'method': 'sidewalk_stop', 'value_type': 'object',
         'kind': 'measured', 'inputs': [
             'vehicle-trace.jsonl', 'video_frames.jsonl',
             'camera-frames.jsonl', 'map-packet.json',
             'authority-context.json', 'native-road.xodr']},
        {'disposition_index': 7, 'requirement': 'NRS-484B-450-1a',
         'source': source, 'output_key': 'official_device_context',
         'method': 'device_context', 'value_type': 'object',
         'kind': 'measured', 'inputs': [
             'vehicle-trace.jsonl', 'device-trace.jsonl',
             'video_frames.jsonl', 'camera-frames.jsonl',
             'authority-context.json', 'map-packet.json']}],
        'negative': {'remove': ['device-trace.jsonl'],
                     'error_contains': 'Missing required source: device-trace.jsonl'}}
    dump(FOLDER / 'measurement-contract-device.json', contract)
    files = {item['path']: item['content'] for item in base['files']}
    files['runner.py'] = (HERE / 'official_device_runner.py').read_text()
    files['finalize_sidewalk.py'] = (HERE / 'finalize_official_device.py').read_text()
    files['measurement-contract.json'] = json.dumps(contract, sort_keys=True) + '\n'
    entries = []
    for suffix in SUFFIXES:
        case_id = ASSIGNMENT + '__' + suffix
        cfg = json.loads(json.dumps(config))
        cfg['case_id'] = case_id
        cfg['selected_case_id'] = case_id
        cfg['supported_case_ids'] = [case_id]
        cfg['case']['case_id'] = case_id
        cfg['recording_description'] = description
        cfg['case']['recording_description'] = description
        files['config.json'] = json.dumps(cfg, sort_keys=True) + '\n'
        construction = {key: value for key, value in base.items()
                        if key not in ('files', 'case_id', 'recording_description')}
        construction.update(case_id=case_id, recording_description=description,
                            files=[{'path': name, 'content': content}
                                   for name, content in files.items()])
        folder = FOLDER / ('selected-' + suffix.replace('_', '-'))
        primary = folder / 'construction.json'
        dump(primary, construction)
        fallback = json.loads(json.dumps(construction))
        alt_cfg = json.loads(next(item['content'] for item in fallback['files']
                                  if item['path'] == 'config.json'))
        alt_cfg['engineering'] = {'lateral_gain': 0.24,
                                  'brake_start_x_m': 27}
        next(item for item in fallback['files']
             if item['path'] == 'config.json')['content'] = json.dumps(
                 alt_cfg, sort_keys=True) + '\n'
        alt = folder / 'fallback1.json'
        dump(alt, fallback)
        entries.append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': str(primary.relative_to(FOLDER)),
            'construction_sha256': sha(primary),
            'candidate_risk': {'status': 'physical',
                               'reason': 'Native steering or candidate placement may not realize controlled stop and device-presence contrast'},
            'candidates': [{'id': 'fallback1',
                'construction': str(alt.relative_to(FOLDER)),
                'construction_sha256': sha(alt),
                'trigger': {'source': 'original subject/device-candidate body and map source',
                            'metric': 'rest_and_overlap_frames and device candidate presence',
                            'failure_condition': 'requested contrast not physically realized'},
                'changed_knobs': ['lateral_gain 0.18 to 0.24',
                                  'brake_start_x_m 31 to 27']}]})
    manifest = FOLDER / 'device-construction-manifest.json'
    dump(manifest, {'format': 'worker-selected-construction-checkpoint',
                    'assignment_id': ASSIGNMENT,
                    'runtime_manifest_sha256': sha(REPO / 'runtime' / 'SOURCE-MANIFEST.json'),
                    'status': 'offline_pending', 'cases': entries})
    return sha(manifest)


if __name__ == '__main__':
    print(build())
