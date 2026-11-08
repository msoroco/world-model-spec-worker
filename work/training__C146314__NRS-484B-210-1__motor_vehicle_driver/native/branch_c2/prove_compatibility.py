"""Exact copied paragraph (c)(2) CPU positives and tamper negatives."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from build_offline import HERE, sha
from check import check


def require_rejected(bundle):
    try:
        check(bundle)
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError('tampered c2 bundle accepted')


def run():
    manifest = json.loads((HERE/'offline/manifest.json').read_text())
    positives = negatives = 0
    for entry in manifest['entries']:
        bundle = HERE/entry['bundle']
        if any(sha(bundle/name) != digest for name, digest in entry['file_sha256'].items()):
            raise ValueError('copied bytes differ')
        check(bundle)
        positives += 1
        result = subprocess.run([sys.executable, str(bundle/'capture.py'),
                                 '--check', '--bundle', str(bundle)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode or json.loads(result.stdout)['delivery_ready']:
            raise ValueError('copied Native capture preflight')
        positives += 1
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in range(5):
                bad = root/str(n)
                shutil.copytree(bundle, bad)
                cfg = json.loads((bad/'config.json').read_text())
                if n == 0:
                    plan = json.loads((bad/'case-plan.json').read_text())
                    plan['source_law']['text'] = plan['source_law']['text'].replace(
                        'past any private way', 'past a private way')
                    (bad/'case-plan.json').write_text(json.dumps(plan)+'\n')
                elif n == 1:
                    cfg['private_way_requested'] = not cfg['private_way_requested']
                    (bad/'config.json').write_text(json.dumps(cfg)+'\n')
                elif n == 2:
                    road = (bad/'unmarked-pass.xodr').read_text().replace(
                        'type="shoulder"', 'type="driving"')
                    (bad/'unmarked-pass.xodr').write_text(road)
                    cfg['road_sha256'] = sha(bad/'unmarked-pass.xodr')
                    (bad/'config.json').write_text(json.dumps(cfg)+'\n')
                elif n == 3:
                    road = (bad/'unmarked-pass.xodr').read_text().replace(
                        'x="50" y="-3.5"', 'x="52" y="-3.5"')
                    (bad/'unmarked-pass.xodr').write_text(road)
                    cfg['road_sha256'] = sha(bad/'unmarked-pass.xodr')
                    (bad/'config.json').write_text(json.dumps(cfg)+'\n')
                else:
                    lines = (bad/'requested-tracks.jsonl').read_text().splitlines()
                    row = json.loads(lines[60])
                    row['ego_y_m'] += 1
                    lines[60] = json.dumps(row)
                    (bad/'requested-tracks.jsonl').write_text('\n'.join(lines)+'\n')
                    cfg['tracks_sha256'] = sha(bad/'requested-tracks.jsonl')
                    (bad/'config.json').write_text(json.dumps(cfg)+'\n')
                require_rejected(bad)
                negatives += 1
    proof = {'format': 'c146314-paragraph-c2-copied-proof-v1',
             'positives': positives, 'negatives': negatives,
             'original_native_observed': False, 'delivery_ready': False}
    (HERE/'offline/proof-compatibility.json').write_text(json.dumps(proof, indent=2)+'\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(run()))
