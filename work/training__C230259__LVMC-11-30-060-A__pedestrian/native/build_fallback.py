"""Build an exact case fallback for a measured original timing failure."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest_path = ROOT / 'selected-draft-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    source = json.loads((ROOT / entry['construction']).read_text())
    construction = json.loads(json.dumps(source))
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['pedestrian_departure_frame'] += 10
    config['candidate_id'] = 'fallback1'
    config_file['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
    runner_file = next(item for item in construction['files'] if item['path'] == 'runner.py')
    previous = 'depart = 320 if case_id.endswith("probe_01") else 140'
    replacement = ('depart = 330 if case_id.endswith("probe_01") else 140'
                   if entry['case_id'].endswith('probe_01') else
                   'depart = 320 if case_id.endswith("probe_01") else 150')
    assert previous in runner_file['content']
    runner_file['content'] = runner_file['content'].replace(previous, replacement)
    construction['measurement_plan']['depart_frame'] = config['pedestrian_departure_frame']
    suffix = entry['case_id'].rsplit('__', 1)[1]
    path = ROOT / f'selected-{suffix}-fallback1-construction.json'
    path.write_text(json.dumps(construction, indent=2, ensure_ascii=False) + '\n')
    entry['candidates'] = [{'id': 'fallback1', 'construction': path.name,
                            'construction_sha256': sha(path),
                            'trigger': {'source': 'original post-tick.jsonl',
                                        'metric': 'pedestrian roadway entry frame and vehicle conflict frame',
                                        'failure_condition': 'Original walker enters before a safe vehicle passage is source-confirmed or fails roadway occupancy'},
                            'changed_knobs': ['pedestrian_departure_frame +10 frames']}]
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
