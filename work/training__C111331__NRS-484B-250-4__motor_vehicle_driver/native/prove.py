"""Independent pair audit and rehashed malformed-source negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(folder):
    return subprocess.run([sys.executable, 'check.py'], cwd=folder,
                          text=True, capture_output=True)


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    if len(manifest['cases']) != 2 or manifest['status'] != 'draft_not_selected':
        raise ValueError('two unselected cases required')
    scratch = Path(os.environ['TMPDIR']) / 'mutations'
    scratch.mkdir(parents=True, exist_ok=True)
    rows = {}
    positives = []
    negatives = {}
    for index, entry in enumerate(manifest['cases'], 1):
        suffix = entry['case_id'].split('__')[-1]
        output = ROOT / '.runtime-work' / 'c111331-2504-tmp' / ('offline-' + str(index))
        construction = HERE / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise ValueError('construction hash differs')
        result = run(output)
        if result.returncode or not (output / 'offline.log').is_file():
            raise ValueError('current offline materialization/check failed: ' + result.stderr)
        positives.append({'case': suffix, 'construction_sha256': sha(construction),
                          'offline_log_sha256': sha(output / 'offline.log')})
        rows[suffix] = [json.loads(line) for line in (output / 'request.jsonl').read_text().splitlines()]
        if suffix == 'controlled_2':
            for kind, expected in (('route', 'controlled route'),
                                   ('signal', 'signal/source'),
                                   ('stop_point', 'stop-point hierarchy'),
                                   ('missing_source', 'FileNotFoundError')):
                folder = scratch / kind
                folder.mkdir(exist_ok=True)
                for name in ('assignment-source.json', 'case-plan.json', 'request.jsonl',
                             'config.json', 'check.py'):
                    shutil.copyfile(output / name, folder / name)
                if kind == 'missing_source':
                    (folder / 'request.jsonl').unlink()
                else:
                    altered = [dict(row) for row in rows[suffix]]
                    if kind == 'route':
                        altered[120]['ego_center_xy_m'] = [-10, -1.75]
                        altered[120]['ego_front_x_m'] = -8
                    elif kind == 'signal':
                        altered[120]['signal_display_requested'] = 'green'
                    else:
                        altered[120]['marked_stop_line_x_m'] = -11
                    path = folder / 'request.jsonl'
                    path.write_text(''.join(json.dumps(row) + '\n' for row in altered))
                    cfg = json.loads((folder / 'config.json').read_text())
                    cfg['rows_sha256'] = sha(path)
                    (folder / 'config.json').write_text(json.dumps(cfg) + '\n')
                rejected = run(folder)
                if rejected.returncode == 0 or expected not in rejected.stderr:
                    raise ValueError('negative not rejected as expected: ' + kind + ' ' + rejected.stderr)
                negatives[kind] = expected
    good, bad = rows['controlled_1'], rows['controlled_2']
    if ([r['other_center_xy_m'] for r in good] != [r['other_center_xy_m'] for r in bad] or
            any(a['signal_display_requested'] != b['signal_display_requested'] for a, b in zip(good, bad))):
        raise ValueError('controlled signal/other vehicle changed')
    changed = [i for i, (a, b) in enumerate(zip(good, bad))
               if a['ego_center_xy_m'] != b['ego_center_xy_m']]
    if not changed or good[210]['ego_front_x_m'] != -13 or bad[120]['ego_front_x_m'] <= -12:
        raise ValueError('requested stop/no-stop contrast differs')
    proof = {'format': 'c111331-2504-current-offline-proof-v1',
             'assignment_sha256': sha(ROOT / 'inputs' / CASE.name / 'assignment.json'),
             'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
             'positives': positives, 'negatives': negatives,
             'changed_ego_request_frames': len(changed),
             'other_vehicle_fixed': True, 'signal_request_fixed': True,
             'physical_stop_observed': False, 'official_inoperative_signal_verified': False,
             'legal_verdict': None, 'delivery_ready': False}
    target = HERE / 'current-offline-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positives': len(positives), 'negatives': len(negatives),
                      'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
