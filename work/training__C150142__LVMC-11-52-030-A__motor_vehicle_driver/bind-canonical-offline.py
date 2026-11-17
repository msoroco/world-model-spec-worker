"""Bind all freshly run exact offline logs into the partial canonical manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
TAG = 'canonical-v3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    matrix = json.loads((ROOT / ('merged-offline-matrix-' + TAG + '.json')).read_text())
    records = {(r['case_id'], r['candidate']): r for r in matrix['records']}
    if len(records) != 120 or len(manifest['cases']) != 30:
        raise ValueError('Exact offline matrix is incomplete')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        slug = case_id.removeprefix(ROOT.name + '__')
        for candidate in [{'id': 'primary', 'construction': entry['construction'],
                           'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']]:
            name = candidate['id']
            row = records[(case_id, name)]
            source = REPO / '.runtime-work' / (
                'c150142-merged-' + slug + '-' + name + '-offline-' + TAG) / 'offline.log'
            if (not row['offline_passed'] or
                    row['construction_sha256'] != candidate['construction_sha256'] or
                    sha(source) != row['offline_log_sha256']):
                raise ValueError('Changed exact offline candidate: ' + slug + '/' + name)
            relative = Path('selected-offline') / slug / (name + '.log')
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            candidate['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                           'work/' + ROOT.name + '/execution-manifest.json --case '
                           + case_id + ' --candidate ' + name + ' --output '
                           '.runtime-work/c150142-merged-' + slug + '-' + name +
                           '-offline-' + TAG,
                'exit_code': 0,
                'construction_sha256': candidate['construction_sha256'],
                'log': relative.as_posix(),
                'log_sha256': sha(target)}
        # The synthetic primary wrapper above is not a manifest member; assign
        # it directly from the verified matrix and copied source log.
        primary_log = ROOT / 'selected-offline' / slug / 'primary.log'
        entry['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                       'work/' + ROOT.name + '/execution-manifest.json --case '
                       + case_id + ' --candidate primary --output '
                       '.runtime-work/c150142-merged-' + slug + '-primary-offline-' + TAG,
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': ('selected-offline/' + slug + '/primary.log'),
            'log_sha256': sha(primary_log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                                   allow_nan=False) + '\n')
    print(json.dumps({'cases': 30, 'offline_proofs_bound': 120,
                      'manifest_sha256': sha(MANIFEST),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
