"""Create a fresh diagnostic saved-source copy with current manifest binding."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
DROP = {'result.json','analysis-report.json','channels','traffic_spec','converted',
        'compatibility.json','processing.json','feedback.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', choices=('condition_a','condition_b'), required=True)
    parser.add_argument('--candidate', choices=('primary','fallback1'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = REPO/'.runtime-work'/f'c111325-final-compat-{args.condition}-{args.candidate}'
    output = Path(args.output).resolve()
    if REPO/'.runtime-work' not in output.parents or output.exists():
        raise ValueError('Fresh saved source belongs under .runtime-work')
    manifest_path = FOLDER/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith(args.condition))
    choice = entry if args.candidate == 'primary' else entry['candidates'][0]
    if json.loads((source/'compatibility.json').read_text())['construction_sha256'] != choice['construction_sha256']:
        raise ValueError('Compatibility source differs from current selected construction')
    output.mkdir(parents=True)
    for path in source.iterdir():
        if path.name in DROP or path.name.startswith(('source-','final-decode','primary','annotated')):
            continue
        target = output/path.name
        if path.is_dir():
            shutil.copytree(path,target)
        else:
            shutil.copyfile(path,target)
    selection = {'format': 'worker-candidate-selection',
                 'case_id': entry['case_id'], 'candidate_id': args.candidate,
                 'construction_sha256': choice['construction_sha256'],
                 'manifest_sha256': sha(manifest_path)}
    (output/'candidate-selection.json').write_text(json.dumps(selection, indent=2)+'\n')
    print(json.dumps({'source': str(output), 'case_id': entry['case_id'],
                      'candidate_id': args.candidate, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
