"""Copy exact current-runtime diagnostic compatibility receipts into this package."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-draft-execution-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, target):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text('\n'.join(lines) + '\n')


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    for variant, item in [('primary', entry), *[(c['id'], c) for c in entry['candidates']]]:
        scratch = REPO / '.runtime-work' / f'c422978-selected-{suffix}-{variant}-compat-v5'
        proof = json.loads((scratch / 'compatibility.json').read_text())
        assert proof['passed'] and proof['candidate_id'] == variant
        target = HERE / f'selected-{suffix}-{variant}-compatibility.json'
        log = HERE / f'selected-{suffix}-{variant}-compatibility-analysis.log'
        negative = HERE / f'selected-{suffix}-{variant}-negative-analysis.log'
        copy_clean(scratch / 'compatibility-analysis.log', log)
        copy_clean(scratch / 'negative-analysis.log', negative)
        proof['log_sha256'] = digest(log)
        proof['negative_log_sha256'] = digest(negative)
        target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        item['compatibility'] = {
            'receipt': target.name, 'sha256': digest(target),
            'log': log.name, 'negative_log': negative.name,
        }
    entry['negative'] = {'log': f'selected-{suffix}-primary-negative-analysis.log'}
    entry['acquisition'] = {
        name: {
            'entrypoint': 'finalize.py',
            'method': 'derive from retained synthetic diagnostic Native rows; original capture pending',
            'evidence': ['native-observed.jsonl', 'trace.jsonl', 'video_frames.jsonl'],
        }
        for name in ('ego_pose', 'ego_speed', 'drive_within_sidewalk_area',
                     'subject_pose_body_speed', 'sidewalk_occupancy')
    }
MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(digest(MANIFEST))
