"""Exercise the pinned source-bound caravan completion assessor on CPU fixtures."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work' / 'c228508-physical-proof'
SCRATCH.mkdir(parents=True, exist_ok=True)
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if not output_root.is_relative_to(REPO / '.runtime-work'):
    raise ValueError('Runtime output root must be scratch')
sys.path.insert(0, str(REPO / 'runtime'))
sys.path.insert(0, str(ROOT / 'native'))
from engineering import CANDIDATES, commanded_centers
from scenario_pipeline.worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangle(x, y, half):
    return [[x - half, y - 1], [x - half, y + 1], [x + half, y + 1], [x + half, y - 1]]


def rows(folder, suffix, candidate, enter=True):
    config = {'law_id': 'NRS-484B-127-3', 'cell_id': 'C228508',
              'duration_s': 30, 'rate_hz': 20}
    (folder / 'config.json').write_text(json.dumps(config) + '\n')
    (folder / 'caravan_context.json').write_text(json.dumps({
        'public_highway_status_verified': False,
        'outside_business_district_verified': False,
        'caravan_membership_verified': False,
        'trailer_coupling_verified': False}) + '\n')
    mapping = []
    history = []
    trace = []
    for index in range(600):
        frame = 1000 + index
        time_s = (index + 1) / 20
        centers = commanded_centers(suffix, candidate, index)
        lead = centers['lead']
        combination = centers['ego_combination']
        entrant = centers['potential_entrant']
        lane = -1 if enter and index >= 120 else -2
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s})
        history.append({'frame': frame, 'time_s': time_s, 'participants': {
            'subject': {'body_vertices_m': rectangle(lead, -1.75, 2.25), 'lane_id': -1},
            'rear': {'body_vertices_m': rectangle(combination, -1.75, 4.5), 'lane_id': -1},
            'entrant': {'body_vertices_m': rectangle(entrant, -1.75 if lane == -1 else -5.25, 3),
                        'lane_id': lane}}})
        trace.append({'frame': frame, 'time_s': time_s})
    for name, content in (('video_frames.jsonl', mapping), ('caravan_history.jsonl', history),
                          ('trace.jsonl', trace)):
        (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in content))
    return config


positive = {}
negative = {}
for suffix in ('probe_a', 'probe_b'):
    for candidate in ('primary', 'fallback1'):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            folder = Path(temporary)
            cfg = rows(folder, suffix, candidate)
            result = assess_physical(folder, cfg, target_checks=[{'matched': True}])
            if not result['setup_confirmed'] or not result['maneuver_completed']:
                raise AssertionError((suffix, candidate, result['physical_checks']))
            positive[suffix + '-' + candidate] = {
                'setup': result['physical_checks']['setup']['status'],
                'target': result['physical_checks']['target']['status'],
                'maneuver': result['physical_checks']['maneuver']['status'],
                'source_sha256': result['physical_checks']['maneuver']['sources']}
with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
    folder = Path(temporary)
    cfg = rows(folder, 'probe_a', 'primary', enter=False)
    result = assess_physical(folder, cfg, target_checks=[{'matched': True}])
    if result['maneuver_completed']:
        raise AssertionError('No-entry caravan fixture accepted')
    negative['no_entry'] = result['physical_checks']['maneuver']['status']
    (folder / 'video_frames.jsonl').unlink()
    result = assess_physical(folder, cfg, target_checks=[{'matched': True}])
    if result['setup_confirmed'] or result['maneuver_completed']:
        raise AssertionError('Missing original frame map accepted')
    negative['missing_frame_map'] = result['physical_checks']['maneuver']['status']

proof = {'format': 'c228508-pinned-caravan-physical-fixture-proof-v1',
         'assessor_sha256': sha(REPO / 'runtime/scenario_pipeline/worker_exchange/native_output.py'),
         'positive_fixtures': positive, 'negative_fixtures': negative,
         'native_execution_claimed': False, 'legal_verdict_claimed': False}
path = ROOT / 'physical-fixture-proof.json'
path.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'proof_sha256': sha(path), 'positives': len(positive),
                  'negatives': len(negative)}))
