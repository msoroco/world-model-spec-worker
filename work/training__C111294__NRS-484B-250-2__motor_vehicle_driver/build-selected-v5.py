"""Add measured source-observation streams to canonical selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TERMS = ('st.intersection', 'st.lane_enters', 'drv.entering_intersection',
         'drv.arrival_order', 'rel.bearing', 'drv.yields_to',
         'dev.traffic_signal', 'drv.turning', 'ego_body', 'other_body')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def recording():
    return {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Retained source-joined actor body, trace and authored road context',
         'time_window': '30 s / 600 frames',
         'reference_frame': 'source video/native frame and authored road',
         'uncertainty': '50 ms frame bracket; original physical and legal review pending'}
        for name in TERMS],
        'context_inputs': [],
        'limitations': [
            'Synthetic CPU fixture is not original Native motion or reviewed pixels',
            'Public-highway and official-device governance, turn intent, subsection 4 and right-of-way remain unverified']}


def build():
    description = recording()
    finalizer = (HERE / 'native/finalize_observations.py').read_text()
    manifest = json.loads((HERE / 'selected-v4-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2'):
            source = HERE / 'selected-v4' / suffix / candidate / 'construction.json'
            construction = json.loads(source.read_text())
            construction['recording_description'] = description
            construction['measurement_plan']['source_observation_channels'] = list(TERMS)
            target_file = next(item for item in construction['files'] if item['path'] == 'finalize.py')
            target_file['content'] = finalizer.replace('__CASE__', entry['case_id'])
            target = HERE / 'selected-v5' / suffix / candidate / 'construction.json'
            write(target, construction)
            if candidate == 'primary':
                entry['construction'] = str(target.relative_to(HERE))
                entry['construction_sha256'] = sha(target)
            else:
                choice = next(item for item in entry['candidates'] if item['id'] == candidate)
                choice['construction'] = str(target.relative_to(HERE))
                choice['construction_sha256'] = sha(target)
    manifest['status'] = 'selected_cpu_in_progress'
    path = HERE / 'selected-v5-manifest.json'
    write(path, manifest)
    print(json.dumps({'manifest_sha256': sha(path), 'channels': len(TERMS),
                      'candidate_constructions': 6}))


if __name__ == '__main__':
    build()
