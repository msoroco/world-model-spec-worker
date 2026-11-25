"""Stage exact review-context constructions without changing selected proofs."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RETURN_ROOT = ROOT.parents[0]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def stage(entry, construction_reference, proposal):
    source = ROOT / construction_reference
    construction = json.loads(source.read_text())
    case_id = entry['case_id']
    suffix = case_id.split('__')[-1]
    recording = proposal[case_id]['recording_description']
    construction['recording_description'] = recording
    finalizer = ('officer_reference_saved_finalizer.py'
                 if 'officer-reference' in source.name else 'saved_finalizer.py')
    draft_source = ROOT / ('review_draft_' + finalizer)
    for file in construction['files']:
        if file['path'] == finalizer:
            file['content'] = draft_source.read_text()
            file.pop('source', None)
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['case']['recording_description'] = recording
            file['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            config_source = ROOT / 'review-draft/sources' / (source.stem + '-config.json')
            config_source.parent.mkdir(parents=True, exist_ok=True)
            config_source.write_text(file['content'])
            file['source'] = str(config_source)
        if file['path'] == 'tests/test_officer_reference_saved_finalizer.py':
            old = "frames.append({'video_frame': i, 'carla_frame': fid, 'time_s': time_s})"
            new = ("frames.append({'video_frame': i, 'carla_frame': fid, 'time_s': time_s, "
                   "'camera_frames': {name: fid for name in finalizer.CAMERAS}})")
            if old not in file['content']:
                raise ValueError('Officer fixture frame shape changed')
            file['content'] = file['content'].replace(old, new)
            file.pop('source', None)
    helper = ROOT / 'original_camera_review.py'
    if any(file['path'] == helper.name for file in construction['files']):
        raise ValueError('Review helper already in source bundle')
    construction['files'].append({'path': helper.name, 'content': helper.read_text(),
                                  'source': str(helper)})
    target = ROOT / 'review-draft' / source.name
    write_json(target, construction)
    return str(target.relative_to(ROOT)), sha(target)


def main():
    selected = json.loads((ROOT / 'execution-manifest.json').read_text())
    cases = json.loads((ROOT / 'proposals/cases.json').read_text())
    proposal = {case['case_id']: case for case in cases['cases']}
    staged = []
    for entry in selected['cases']:
        primary, primary_hash = stage(entry, entry['construction'], proposal)
        row = {'case_id': entry['case_id'], 'construction': primary,
               'construction_sha256': primary_hash,
               'measurement_contract': entry['measurement_contract'],
               'measurement_procedure': entry['measurement_procedure'],
               'fixture_recipe': entry['fixture_recipe'], 'candidates': []}
        for alternate in entry['candidates']:
            path, digest = stage(entry, alternate['construction'], proposal)
            row['candidates'].append({'id': alternate['id'],
                                      'construction': path,
                                      'construction_sha256': digest})
        staged.append(row)
    manifest = {'format': 'worker-offline-manifest',
                'runtime_manifest_sha256': selected['runtime_manifest_sha256'],
                'cases': staged}
    write_json(ROOT / 'review-draft-manifest.json', manifest)
    print('staged', len(staged), 'cases and',
          sum(len(row['candidates']) for row in staged), 'fallbacks')


if __name__ == '__main__':
    main()
