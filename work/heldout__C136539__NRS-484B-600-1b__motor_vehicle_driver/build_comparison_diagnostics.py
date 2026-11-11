"""Exercise all planned comparisons on retained diagnostic original sources."""

import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from exposure_comparison_audit import PAIRS, audit
from exposure_case_setup import case_settings


root = Path(__file__).resolve().parent
repo = root.parents[1]
out = root / 'comparisons'
out.mkdir(exist_ok=True)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
write = lambda path, value: path.write_text(json.dumps(value, indent=2) + '\n')
source_files = ('config.json', 'trace.jsonl', 'video_frames.jsonl',
                'exposed_actor_footprints.jsonl')
names = sorted({name for pair in PAIRS.values() for name in pair[:2]})
attempts = {}
for name in names:
    source = repo / f'.runtime-work/c136539-{name}-compat-passage-a'
    target = repo / f'.runtime-work/c136539-{name}-comparison-diagnostic-a'
    if target.exists():
        raise ValueError('Retain prior diagnostic comparison fixture: ' + name)
    target.mkdir()
    for filename in source_files:
        shutil.copyfile(source / filename, target / filename)
    config = json.loads((target / 'config.json').read_text())
    context = json.loads((source / 'alley_context.json').read_text())
    xodr = ET.parse(source / 'road.xodr').getroot()
    lane_ids = {int(lane.attrib['id']) for lane in xodr.findall('.//lane[@type="driving"]')}
    if -1 not in lane_ids or context['road_id'] != 1:
        raise ValueError('Diagnostic route geometry differs from declared fixed scene')
    scene = {'case_id': config['selected_case_id'],
             'exact_settings': case_settings(config),
             'map_name': context['native_map_name'],
             'road_id': context['road_id'], 'lane_id': -1,
             'fixture_scope': 'diagnostic OpenDRIVE scene identity; not a Native scene receipt'}
    write(target / 'construction-probe.json', scene)
    write(target / 'fixture-provenance.json',
          {'kind': 'synthetic_fixture', 'source': str(source.relative_to(repo)),
           'no_native_physical_claim': True})
    attempts[name] = target

index = {'format': 'worker-exposure-comparison-diagnostic-proofs',
         'scope': 'diagnostic original-source comparison behavior only; Native fixed-scene and physical outcomes unverified',
         'script': 'exposure_comparison_audit.py',
         'script_sha256': sha(root / 'exposure_comparison_audit.py'),
         'pairs': []}
for comparison_id, (left_name, right_name, _) in PAIRS.items():
    left, right = attempts[left_name], attempts[right_name]
    result = audit(comparison_id, left, right)
    result_path = out / f'{comparison_id}-result.json'
    write(result_path, result)
    log = out / f'{comparison_id}-positive.log'
    write(log, {'comparison_id': comparison_id, 'status': 'pass',
                'result_sha256': sha(result_path),
                'source_fixture': [str(left.relative_to(repo)), str(right.relative_to(repo))],
                'physical_acceptance_claimed': False})
    scene_path = right / 'construction-probe.json'
    scene = json.loads(scene_path.read_text())
    scene['road_id'] = 2
    write(scene_path, scene)
    try:
        audit(comparison_id, left, right)
    except ValueError as error:
        if 'Comparison fixed road geometry changed' not in str(error):
            raise
        negative = str(error)
    else:
        raise ValueError('Changed fixed road geometry was accepted')
    scene['road_id'] = 1
    write(scene_path, scene)
    neg_log = out / f'{comparison_id}-negative.log'
    neg_log.write_text(negative + '\n')
    index['pairs'].append({'comparison_id': comparison_id,
                           'result': str(result_path.relative_to(root)), 'result_sha256': sha(result_path),
                           'positive_log': str(log.relative_to(root)), 'positive_log_sha256': sha(log),
                           'negative_log': str(neg_log.relative_to(root)), 'negative_log_sha256': sha(neg_log)})
write(root / 'comparison-diagnostic-proofs.json', index)
print('four diagnostic source comparisons pass; four fixed-road tamper negatives rejected')
