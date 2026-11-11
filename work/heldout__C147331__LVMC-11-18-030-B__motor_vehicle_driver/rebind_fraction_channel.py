"""Bind original-derived dimensionless fraction stream into exact sweep sources."""
import hashlib
import json
from pathlib import Path

from batch_pipeline.store import digest as stage_digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROPOSALS = HERE / 'proposals'
POINTS = {'passing_excursion-0000': .4,
          'passing_excursion-0001': .8,
          'passing_excursion-0002': .6}
CHANNEL = {
    'name': 'lane_crossing_fraction', 'unit': 'fraction',
    'method': 'absolute original ego-center lateral displacement from retained lane center divided by original lane width',
    'sampling_rate_hz': 20, 'time_window': 'all original frames',
    'reference_frame': 'retained original lane ground plane',
    'uncertainty': 'Native body corners and local waypoint lane slice; no adjacent-lane identity inferred',
}

def read(path): return json.loads(path.read_text())
def write(path, value): path.write_text(json.dumps(value, indent=2) + '\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def append_channel(description):
    names = [row['name'] for row in description['channels']]
    if CHANNEL['name'] not in names:
        description['channels'].append(dict(CHANNEL))

cases_path = PROPOSALS / 'cases.json'
cases = read(cases_path)
spec = next(s for s in cases['sweep_specs'] if s['sweep_id'].endswith('__passing_excursion'))
spec['status'] = 'complete'
spec.pop('missing_inputs', None)
append_channel(spec['recording_description'])
spec['rationale'] = 'Three fixed dimensionless lateral target points with retained original source fraction stream; lawful passing remains unresolved.'
spec['axes'][0]['feasibility_evidence'] = 'Case-specific synthetic CPU fixtures yield exact source-derived lateral fractions 0.4/0.8/0.6; Native physical realization remains subject to capture and completion review.'
frozen = {k: v for k, v in spec.items() if k not in ('spec_version','planned_case_count','selection_order')}
spec['spec_version'] = stage_digest(frozen)
for case in cases['cases']:
    if case['case_id'].rsplit('__',1)[-1] not in POINTS:
        continue
    append_channel(case['recording_description'])
    case['sweep_spec_version'] = spec['spec_version']
    case['sweep_measurements'] = [{'observable': a['observable'], 'unit': a['unit'],
                                    'measurement': a['measurement']} for a in spec['axes']]
write(cases_path, cases)
judgment_path = PROPOSALS / 'judgment_passing.json'
judgment = read(judgment_path)
judgment['observable_requirements']['sweep_dimensions'] = [{
    'name': 'lane_crossing_fraction', 'unit': 'fraction',
    'description': 'Original ego-center lateral excursion divided by original lane width.'}]
write(judgment_path, judgment)
index_path = PROPOSALS / 'semantic-index.json'
index = read(index_path)
index['stages']['cases']['sha256'] = sha(cases_path)
index['stages']['judgment_observables'][0]['sha256'] = sha(judgment_path)
write(index_path, index)

delivery_path = HERE / 'delivery-construction-manifest.json'
manifest = read(delivery_path)
for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    for name, target in [('construction', entry)] + [('construction', c) for c in entry['candidates']]:
        path = HERE / target[name]
        construction = read(path)
        for file in construction['files']:
            if file['path'] in ('runner.py','lane_finalizer.py'):
                file['content'] = (HERE / file['path']).read_text()
            elif file['path'] == 'config.json' and suffix in POINTS:
                config = json.loads(file['content'])
                config['engineering']['crossing_fraction'] = POINTS[suffix]
                config['case']['recording_description'] = next(c['recording_description'] for c in cases['cases'] if c['case_id'] == entry['case_id'])
                file['content'] = json.dumps(config, indent=2) + '\n'
        if suffix in POINTS:
            construction['recording_description'] = next(c['recording_description'] for c in cases['cases'] if c['case_id'] == entry['case_id'])
        write(path, construction)
        target['construction_sha256'] = sha(path)
    if suffix in POINTS:
        entry.setdefault('acquisition', {})['lane_crossing_fraction'] = {
            'entrypoint': 'lane_finalizer.py', 'method': CHANNEL['method'],
            'evidence': 'marked_lane_sources.jsonl original ego corners and lane polygon/width/heading'}
write(delivery_path, manifest)
print('semantic index',sha(index_path),'delivery manifest',sha(delivery_path))
