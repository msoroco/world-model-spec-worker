"""Bind the three authored right-pass fallback requests into exact CPU bundles."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WITNESS = sys.argv[1] if len(sys.argv)>1 else 'reference'
if WITNESS not in ('reference','contrast'):
    raise ValueError('Unknown selected witness')
SOURCE = ROOT / 'selected-primary' / WITNESS / 'construction.json'
PRIMARY = json.loads(SOURCE.read_text())


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


for candidate in ('fallback1', 'fallback2', 'fallback3'):
    source = ROOT / 'native/drafts' / WITNESS / candidate
    construction = json.loads(SOURCE.read_text())
    files = {item['path']: item for item in construction['files']}
    config = json.loads((source / 'config.json').read_text())
    selected = json.loads(files['config.json']['content'])
    # The reviewed case and recording contract stay fixed. Only the controller
    # request and its source identity change for each physical risk trigger.
    for key in ('candidate_id', 'tracks_sha256', 'camera_policy',
                'ego_requested_speed_mps', 'lead_requested_speed_mps',
                'lane_change_end_x_m', 'requested_lateral_apex_y_m',
                'requested_nominal_body_gap_m'):
        selected[key] = config[key]
    files['config.json']['content'] = encoded(selected)
    files['requested-tracks.jsonl']['content'] = (source / 'requested-tracks.jsonl').read_text()
    manifest = json.loads(files['manifest.json']['content'])
    manifest['entries'] = [{'case_id': selected['case_id'],
        'candidate_id': candidate, 'config_sha256': sha(files['config.json']['content']),
        'tracks_sha256': sha(files['requested-tracks.jsonl']['content'])}]
    files['manifest.json']['content'] = encoded(manifest)
    construction['status'] = 'draft_selected_cpu'
    construction['mechanisms']['fallback_request'] = {
        'fallback1': 'lower paired vehicle speed to reduce closing dynamics',
        'fallback2': 'elevate overview sensor to recover occluded body context',
        'fallback3': 'lengthen right entry to reduce lateral steering demand',
    }[candidate]
    output = ROOT / 'selected-fallbacks' / WITNESS / candidate / 'construction.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded(construction))
    print(candidate, sha(output.read_text()))
